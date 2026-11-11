# Build from source

Targets: Windows 10/11 x64, macOS 11+ (arm64 and x64, built on each architecture), and
64-bit Linux (glibc 2.35+). CPython **3.11.9**. No Nintendo data or keys are needed to
build or run the synthetic tests. Native probe rebuilding is documented in
[EMULATOR_PATCH.md](EMULATOR_PATCH.md); ordinary PyInstaller builds use the included
payload and need no C compiler.

`python -m PyInstaller --noconfirm --clean Packager.spec` produces, under `dist/`:

| System | App | Command line |
|---|---|---|
| Windows | `NSP-Box.exe` (windowed, one file) | `nspbox.exe` (console) |
| macOS | `NSP-Box.app` | `nspbox` |
| Linux | `NSP-Box` (one file) | `nspbox` |

`python package_release.py` then assembles the allowlisted portable archive for the
current system under `release/` (`--skip-source` omits the source ZIP). The
[release workflow](.github/workflows/release.yml) runs the same steps on Windows,
macOS arm64, macOS x64 and Linux x64 and publishes all archives together.

The test list is the same on every system:

```text
test_engine test_ui test_artwork test_performance_safety test_nsp test_compatibility
test_emulator_patch test_dlc test_file_drops test_nup test_nup_ui test_nup_optimization
test_nup_polish test_portable
```

GUI tests (`test_ui`, `test_nup_ui`, the GUI case in `test_dlc`) need a desktop session;
on a headless Linux machine use `xvfb-run -a`. The Windows native-drop test only runs
on Windows. Everything else, including the command line, needs no Tk at all.

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest test_engine test_ui test_artwork test_performance_safety test_nsp test_compatibility test_emulator_patch test_dlc test_file_drops test_nup test_nup_ui test_nup_optimization test_nup_polish test_portable
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean Packager.spec
.\.venv\Scripts\python.exe frozen_smoke.py; .\.venv\Scripts\python.exe frozen_nup_smoke.py; .\.venv\Scripts\python.exe frozen_cli_smoke.py
```

### macOS and Linux (shell)

Use a Python 3.11 that includes Tk: the python.org installer on macOS, or your
distribution's `python3.11` plus `python3.11-tk`/`tk` on Linux. Homebrew's Python needs
`brew install python-tk@3.11`. Linux GUI builds also need `binutils` (for PyInstaller)
and `libxcursor1` for drag and drop.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest test_engine test_ui test_artwork test_performance_safety test_nsp test_compatibility test_emulator_patch test_dlc test_file_drops test_nup test_nup_ui test_nup_optimization test_nup_polish test_portable
.venv/bin/python -m PyInstaller --noconfirm --clean Packager.spec
.venv/bin/python frozen_smoke.py && .venv/bin/python frozen_nup_smoke.py && .venv/bin/python frozen_cli_smoke.py
```

macOS builds are ad-hoc signed. To sign with a Developer ID for notarization, set
`NSPBOX_CODESIGN_IDENTITY` (and `NSPBOX_ENTITLEMENTS=packaging/macos/entitlements.plist`)
before running PyInstaller; the release workflow does this, then notarizes and staples,
when the `MACOS_*`/`APPLE_*` repository secrets are configured.

Source and tests are provided as a separate release ZIP; the portable archives do not
duplicate them. Keep `DISCLAIMER.md`, the root license, notices, and `licenses/`
directory with any redistributed release. Dependency version pinning makes the build
inputs identifiable; timestamps, Python installation details and toolchain/runtime
differences mean binaries are not claimed to be bit-for-bit reproducible.

Run the GUI from source:

```powershell
.\.venv\Scripts\python.exe src\app.py
```

The command line from source (any system, no Tk required) — see [CLI.md](CLI.md):

```sh
python src/cli.py scan "/path/to/My Game Dump"
python src/cli.py build "/path/to/My Game Dump" -o "/path/to/Packed/My Game.nsp"
```

Optional command-line packaging:

```powershell
.\.venv\Scripts\python.exe src\app.py --package "D:\My Game Dump" --output "D:\Packed\My Game.nsp" --artwork "D:\Art\cover.png" --title "My Game"
.\.venv\Scripts\python.exe src\app.py --package "D:\My Game Dump" --output "D:\Packed\My Game.nsp" --format nsp
```

`--snapshot 0` selects the first detected candidate (highest numeric folder version). `--display-version` sets the NACP display label; the snapshot folder's numeric version is retained for CNMT. Output must end in `.nsp`. XCI creation is not supported. The old `--format nsp` argument is accepted for command-line compatibility but is no longer shown as a format choice. Package-folder output is enabled by default; `--package-folder` explicitly selects it. Use `--no-package-folder` to save only the NSP. `--skip-verification` disables the full readback comparison. The windowed EXE accepts these arguments too, but does not provide console output; enable `--package-folder` for a JSON report or local `.error.txt` diagnostic.

## Files

- `src/app.py`: Tk GUI and queue-driven worker; command-line arguments are handed to `src/cli.py`.
- `src/cli.py`: the `nspbox` command line (`scan`, `build`, `dlc`, `nup …`) plus the original `--package` interface. Never imports Tk.
- `src/portable.py`: operating-system differences: no-replace commits (exFAT-safe), case-insensitive `exefs`/`romfs` lookup, macOS metadata filtering, folder opening, settings paths and reduced-motion detection.
- `src/ui.py`: rounded antialiased components, cached bundled icons, time-based motion, and file drops (Windows shell hook; TkDND on macOS/Linux).
- `src/ambient.py`: low-resolution ambient gradient, shared background surfaces, minimized-window pause and reduced-motion handling.
- `src/assets/`: app/UI PNG artwork and asset provenance notes, included in frozen and source builds.
- `src/artwork.py`: supported formats, EXIF/first-frame decoding, crop geometry, full-image fitting and 256×256 JPEG encoding.
- `src/crop_dialog.py`: interactive square crop, panning, zoom slider/wheel and live preview.
- `src/engine.py`: snapshot discovery, metadata/artwork handling, build orchestration and verification.
- `src/container_format.py`: streaming PFS0/HFS0/RomFS/NCA writers.
- `src/verify_format.py`: independent bounded reader and integrity checks.
- `src/startup_notice.py`: legacy notice/preference helper, retained for older-source compatibility; the GUI no longer opens a startup notice.
- `src/compatibility.py`: explicit, non-destructive setup for plaintext-repack placeholder entries.
- `test_engine.py`: synthetic Unicode/multi-version round trip, artwork handling, cancellation cleanup, no-overwrite and invalid-input cases.
- `test_ui.py`: synthetic end-to-end UI build, native shell folder/artwork drops, original control retention, motion interpolation and minimum-size visibility checks. Run on Windows with a desktop session available.
- `test_artwork.py`: codec decoding, square positioning, source preservation, fit mode and invalid-crop tests.
- `test_performance_safety.py`: source reread avoidance, corruption/mutation detection and mapping cleanup.
- `test_nsp.py`: NSP container/artwork/metadata round trips, CLI, cancellation, corruption, refusal cases and no-extra-source-pass checks.
- `test_portable.py`: cross-platform commits (including the exFAT fallback), folder-name case, macOS metadata, case-colliding extraction and the command line.
- `frozen_cli_smoke.py`: exercises the built `nspbox` binary without a desktop session.
- `test_compatibility.py`: missing-entry setup, existing-key preservation, exact backups, idempotence and invalid-entry refusal.

CLI artwork is center-cropped by default. `--artwork-fit` keeps the whole image; `--artwork-crop LEFT TOP RIGHT BOTTOM` supplies a square box in normalized 0–1 coordinates of the EXIF-oriented image. These options are mutually exclusive and require `--artwork`.
- `Packager.spec`: PyInstaller one-file build configuration.

The app has no network code. `pip` requires network access when installing build dependencies, unless they are already available locally. The shipped EXE does not require it.

DLC-only command-line example (no artwork or companion):

```powershell
.\.venv\Scripts\python.exe src\app.py --dlc --package "D:\My Game Dump\dlc" --output "D:\Packed\DLC.nsp" --base-game "D:\Packed\Game.nsp"
```

`--base-game` is optional and checks plaintext game headers/control metadata only. `--dlc-title-id` supplies the original DLC ID if absent from folder names; `--dlc-version` overrides its numeric dump version. The DLC mode always writes just the NSP.
