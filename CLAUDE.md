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
- **Developer Mode alone does not help** when the exe is signed with a self-signed cert.

### What works

1. **Do not sign the exe.** Leave it unsigned after building with PyInstaller.
2. **Enable Windows Developer Mode:** Settings → System → For developers → Developer Mode → On.

With Developer Mode enabled and the exe unsigned, SAC allows locally-built executables to run.

### What would also work (not currently used)

- A commercially-trusted code signing certificate (e.g. Certum ~€50/yr) would give the exe cloud reputation and pass SAC without Developer Mode.
- Disabling SAC entirely (one-way — cannot be re-enabled without Windows reinstall).
