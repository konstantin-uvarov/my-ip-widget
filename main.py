import ctypes
import json
import os
import sys
import threading
import time
import requests
from tkinter import *
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip
import pystray
from pystray import Icon as Icon, MenuItem as MenuItem
import darkdetect

# ── Windows API constants ────────────────────────────────────────────────────
GWL_EXSTYLE      = -20
WS_EX_TOOLWINDOW = 0x00000080   # hides from taskbar / Alt-Tab
WS_EX_APPWINDOW  = 0x00040000
WS_EX_NOACTIVATE = 0x08000000   # clicks don't activate / raise the window
HWND_BOTTOM      = 1            # z-order: behind all normal windows
SWP_NOSIZE       = 0x0001
SWP_NOMOVE       = 0x0002
SWP_NOACTIVATE   = 0x0010

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".myipwidget.json")

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath('.'), relative_path)

def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {"x": 100, "y": 100, "visible": False}

def save_config(x, y, visible):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"x": x, "y": y, "visible": visible}, f)
    except Exception:
        pass

REQUEST_TIMEOUT = 5
IMG_DIR = resource_path("assets/images")
PIRATE_FLAG = f"{IMG_DIR}/pirate_flag.png"


class Application:
    def __init__(self):
        self.stop_program = False
        self.last_ip = None
        self.current_ip = None

        config = load_config()
        self.widget_x   = config.get("x", 100)
        self.widget_y   = config.get("y", 100)
        self.is_visible = config.get("visible", False)
        self._drag_offset  = (0, 0)

        self.root = Tk()
        self.root.overrideredirect(True)
        self.root.title("MyIP Widget")
        self.root.iconbitmap(f"{IMG_DIR}\\icon.ico")

        self.detect_theme()

        self.lab1 = Label(self.root, bg=self.bg_color)
        self.lab1.bind("<Button-3>", self.hide_window)
        IP_W = 13   # max IPv4 length: 255.255.255.255
        self.lab2 = Label(self.root, bd=0, bg=self.bg_color, fg=self.fg_color,
                          highlightthickness=0, borderwidth=0,
                          width=IP_W, anchor='center')
        self.lab3 = Label(self.root, bd=0, bg=self.bg_color, fg=self.fg_color,
                          highlightthickness=0, borderwidth=0,
                          width=IP_W, anchor='center')

        self.lab1.grid(row=1, column=1)
        self.lab2.grid(row=2, column=1)
        self.lab3.grid(row=3, column=1)

        Hovertip(self.lab1, 'right-click to hide')

        # ── Tray icon ────────────────────────────────────────────────────────
        self.icon = pystray.Icon("ping")
        self.icon.icon = Image.open(PIRATE_FLAG)
        self.icon.menu = pystray.Menu(
            # default=True → triggered on double-click / single-click on the icon
            MenuItem('Copy IP', self.copy_ip, default=True),
            MenuItem(
                lambda item: 'Hide Widget' if self.is_visible else 'Show Widget',
                self.toggle_window
            ),
            MenuItem('Quit', self.quit_window),
        )
        self.icon.run_detached()

        # ── Window style / position ──────────────────────────────────────────
        self.root.attributes("-alpha", 0.7)
        self.root.attributes('-topmost', False)
        self.root.configure(bg=self.bg_color)
        self.root.geometry(f'+{self.widget_x}+{self.widget_y}')

        if not self.is_visible:
            self.root.withdraw()

        self.root.bind("<ButtonPress-1>",   self.on_drag_start)
        self.root.bind("<B1-Motion>",          self.move_window)
        self.root.bind("<ButtonRelease-1>",    self.on_drag_end)

        # Apply Win32 style after the window is fully mapped
        self.root.after(150, self.apply_window_style)

        self.thread2 = threading.Thread(target=self.update_data, daemon=True)
        self.thread2.start()

    # ── Win32 helpers ────────────────────────────────────────────────────────

    def _get_hwnd(self):
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        return hwnd if hwnd else self.root.winfo_id()

    def apply_window_style(self):
        """Remove taskbar button, prevent focus steal, sink to bottom z-order."""
        hwnd = self._get_hwnd()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        self._sink_to_bottom()

    def _sink_to_bottom(self):
        """Push window behind all normal windows (above wallpaper)."""
        hwnd = self._get_hwnd()
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_BOTTOM, 0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
        )

    # ── Theme ────────────────────────────────────────────────────────────────

    def detect_theme(self):
        theme = darkdetect.theme()
        if theme == "Dark":
            self.bg_color = "black"
            self.fg_color = "white"
        else:
            self.bg_color = "white"
            self.fg_color = "black"

    # ── Widget movement & position persistence ───────────────────────────────

    def on_drag_start(self, event):
        self._drag_offset = (event.x_root - self.root.winfo_x(),
                             event.y_root - self.root.winfo_y())

    def move_window(self, event):
        ox, oy = self._drag_offset
        self.root.geometry(f'+{event.x_root - ox}+{event.y_root - oy}')
        self._sink_to_bottom()

    def on_drag_end(self, event):
        self.widget_x = self.root.winfo_x()
        self.widget_y = self.root.winfo_y()
        save_config(self.widget_x, self.widget_y, self.is_visible)

    # ── Show / Hide ──────────────────────────────────────────────────────────

    def toggle_window(self, icon=None, item=None):
        if self.is_visible:
            self.root.after(0, self._hide)
        else:
            self.root.after(0, self._show)

    def _show(self):
        self.is_visible = True
        self.root.deiconify()
        self.root.after(50, self.apply_window_style)
        save_config(self.root.winfo_x(), self.root.winfo_y(), True)

    def _hide(self):
        self.is_visible = False
        self.root.withdraw()
        save_config(self.root.winfo_x(), self.root.winfo_y(), False)

    def hide_window(self, event):
        self._hide()

    # ── Clipboard ────────────────────────────────────────────────────────────

    def copy_ip(self, icon=None, item=None):
        if self.current_ip:
            self.root.after(0, lambda: self._copy_to_clipboard(self.current_ip))

    def _copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    # ── Quit ─────────────────────────────────────────────────────────────────

    def quit_window(self, icon=None, item=None):
        save_config(self.root.winfo_x(), self.root.winfo_y(), self.is_visible)
        self.stop_program = True
        self.icon.icon = None
        self.icon.title = None
        self.icon.stop()
        self.root.destroy()

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _truncate(text, max_chars=18):
        """Clip text to max_chars, appending … if truncated."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 1] + '\u2026'

    # ── IP fetching & UI update ──────────────────────────────────────────────

    def find_ip(self):
        try:
            req = requests.get("http://ip-api.com/json/", timeout=REQUEST_TIMEOUT)
            if req.status_code == 200:
                return req.json()
            return False
        except Exception as e:
            print(e)
            return False

    def update_data(self):
        while not self.stop_program:
            ip = self.find_ip()
            if ip:
                ip_address = ip["query"]
                self.current_ip = ip_address
                if ip_address != self.last_ip:
                    self.last_ip = ip_address
                    self.root.after(0, lambda d=ip: self._update_ui(d))
            else:
                self.current_ip = None
                self.last_ip = None
                self.root.after(0, self._update_ui_offline)
            time.sleep(5)

    def _update_ui(self, ip):
        flag_path = f"{IMG_DIR}\\flags\\{ip['countryCode']}.png"
        self.lab1.image = ImageTk.PhotoImage(image=Image.open(flag_path))
        self.lab1.config(image=self.lab1.image)
        self.lab2.config(text=self._truncate(ip["country"], 15))
        self.lab3.config(text=ip["query"])
        self.icon.icon  = Image.open(flag_path)
        self.icon.title = ip["query"]

    def _update_ui_offline(self):
        self.lab1.image = ImageTk.PhotoImage(file=PIRATE_FLAG)
        self.lab1.config(image=self.lab1.image)
        self.lab2.config(text="No Internet")
        self.lab3.config(text="")
        self.icon.icon = Image.open(PIRATE_FLAG)

    # ── Entry point ──────────────────────────────────────────────────────────

    def run(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()

        self.root.mainloop()
        os._exit(1)


if __name__ == '__main__':
    app = Application()
    app.run()
