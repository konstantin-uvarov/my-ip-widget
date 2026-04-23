# My IP Widget

## Build

Build the exe with PyInstaller:

```
pyinstaller MyIPWidget.spec
```

## Smart App Control (SAC)

Windows 11 with Smart App Control (SAC) in enforcement mode blocks executables that lack cloud reputation. Key findings:

- **Self-signed certificates do not work with SAC.** SAC treats a self-signed cert as an untrusted root (`VerificationError: 18`) and blocks the exe — worse than leaving it unsigned.
- **WDAC supplemental policies do not work.** The deployed SAC policy has `Allow Supplemental Policies` disabled (bit 17 = 0) and requires signed policies (bit 6 = 0), so custom supplemental policies are silently rejected.
- **Developer Mode bypass was removed in Windows 11 24H2.** Previously, Developer Mode + unsigned exe would bypass SAC; this workaround was patched by Microsoft in 24H2 (KB5074105 / KB5079391 era).
- **SAC is no longer a one-way switch (as of Windows 11 24H2).** You can now disable SAC and re-enable it later without reinstalling Windows.

### What works

1. **Disable SAC:** Settings → Privacy & Security → Windows Security → App & Browser Control → Smart App Control → Off.
   - This is now fully reversible — you can re-enable SAC at any time from the same settings page.

### What would also work (not currently used)

- A commercially-trusted code signing certificate (e.g. Certum ~€50/yr) would give the exe cloud reputation and pass SAC without disabling it.
