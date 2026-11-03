# Build from source

Target: Windows 10/11 x64, CPython **3.11.9 x64**. No Nintendo data or keys are needed to build or run the synthetic tests.

This release targets Windows x64 only; no Linux download is included.

Include `test_emulator_patch` in the unittest command. Native probe rebuilding is documented in [EMULATOR_PATCH.md](EMULATOR_PATCH.md); ordinary PyInstaller builds use the included payload and need no C compiler.

From this source directory in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe test_engine.py
.\.venv\Scripts\python.exe test_ui.py
.\.venv\Scripts\python.exe test_artwork.py
.\.venv\Scripts\python.exe test_performance_safety.py
.\.venv\Scripts\python.exe test_nsp.py
.\.venv\Scripts\python.exe test_compatibility.py
.\.venv\Scripts\python.exe test_emulator_patch.py
.\.venv\Scripts\python.exe test_dlc.py
.\.venv\Scripts\python.exe test_file_drops.py
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean Packager.spec
```

The EXE is created under `dist/`. Source and tests are provided as a separate release ZIP; the portable ZIP does not duplicate them. Keep `DISCLAIMER.md`, the root license, notices, and `licenses/` directory with any redistributed release. Dependency version pinning makes the build inputs identifiable; timestamps, Python installation details and toolchain/runtime differences mean binaries are not claimed to be bit-for-bit reproducible.

Run the GUI from source:

```powershell
.\.venv\Scripts\python.exe src\app.py
```

Optional command-line packaging:

```powershell
.\.venv\Scripts\python.exe src\app.py --package "D:\My Game Dump" --output "D:\Packed\My Game.nsp" --artwork "D:\Art\cover.png" --title "My Game"
.\.venv\Scripts\python.exe src\app.py --package "D:\My Game Dump" --output "D:\Packed\My Game.nsp" --format nsp
```

`--snapshot 0` selects the first detected candidate (highest numeric folder version). `--display-version` sets the NACP display label; the snapshot folder's numeric version is retained for CNMT. Output must end in `.nsp`. XCI creation is not supported. The old `--format nsp` argument is accepted for command-line compatibility but is no longer shown as a format choice. Package-folder output is enabled by default; `--package-folder` explicitly selects it. Use `--no-package-folder` to save only the NSP. `--skip-verification` disables the full readback comparison. The windowed EXE accepts these arguments too, but does not provide console output; enable `--package-folder` for a JSON report or local `.error.txt` diagnostic.

## Files

- `src/app.py`: Tk GUI, queue-driven worker and command-line entry point.
- `src/ui.py`: rounded antialiased components, cached bundled icons, time-based motion, and Windows shell drop integration.
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
- `test_compatibility.py`: missing-entry setup, existing-key preservation, exact backups, idempotence and invalid-entry refusal.

CLI artwork is center-cropped by default. `--artwork-fit` keeps the whole image; `--artwork-crop LEFT TOP RIGHT BOTTOM` supplies a square box in normalized 0–1 coordinates of the EXIF-oriented image. These options are mutually exclusive and require `--artwork`.
- `Packager.spec`: PyInstaller one-file build configuration.

The app has no network code. `pip` requires network access when installing build dependencies, unless they are already available locally. The shipped EXE does not require it.

DLC-only command-line example (no artwork or companion):

```powershell
.\.venv\Scripts\python.exe src\app.py --dlc --package "D:\My Game Dump\dlc" --output "D:\Packed\DLC.nsp" --base-game "D:\Packed\Game.nsp"
```

`--base-game` is optional and checks plaintext game headers/control metadata only. `--dlc-title-id` supplies the original DLC ID if absent from folder names; `--dlc-version` overrides its numeric dump version. The DLC mode always writes just the NSP.
