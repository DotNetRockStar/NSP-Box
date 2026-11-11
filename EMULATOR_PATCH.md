# NSP Box — experimental emulator patch

**PokeDinner 2.5.0 and newer builds with native NSP support do not need this patch
or an external `main.npdm`.** Thank you to **Franseven**, the creator of PokeDinner,
for integrating support. The [2.5.0 release notes](https://git.eden-emu.dev/Franseven/PokeDinner-a-Eglantine-Fork/releases/tag/2.5.0)
list native Switch 2 NSP and NUP support. Older PokeDinner builds listed below still
use the reversible patch. The native-support notice is based on upstream release
notes; it does not add a new binary patch profile or claim gameplay validation.

Open **Emulator patch** in the NSP Box header. Select the folder containing the
Windows x64 emulator executable, close that emulator, then use **Add patch** (or
**Try patch** for an unverified match). Restart it normally. To undo, select the
same folder and choose **Remove patch**, even if the patched emulator cannot boot.
The packager does not need to remain open when playing.

**Version 2.0 includes the corrected PokeDinner probe from local testing.** Its real VFS read method
uses a different table slot from standard Eglantine. The original probe called
the wrong method, so a normal startup still selected 19.2 MHz even with 12 GiB.
The corrected probe selects 31.25 MHz, matching the external-file startup path.
If the panel shows **Older patch**, remove it with this app and then add the new
patch. Original 1.5.0 backups/payloads remain supported for safe removal.

NSP Box emits NSP packages only. The native compatibility probe retains support for older containers so existing patch backups and legacy packages remain usable.

For a new single-file NSP package, uncheck **Create package folder**. Existing packages
already contain their own NPDM and do not need to be rebuilt for this patch.
For testing, use a directory without an external `main.npdm`, keeping your original
package and companion as a backup. This feature is experimental; verify actual
booting, rendering and performance yourself before relying on companion-free use.

## Recognized builds and future updates

The patch panel shows this list directly. Release-provided Windows x64 assets checked through **2026-11-02**:

| Target | Supported variants |
|---|---|
| [Selevet performance build 4](https://github.com/sylvieistaken/selevet-eglantine/releases/tag/selevet-eglantine-performance-4) (`8b076b1`) | Normal + 30 FPS downloads, GUI |
| [Eglantine nx2 build 98](https://github.com/Djihads80/Eglantine/releases/tag/build-98) (`adae763`) | Standard + PGO, GUI and CLI |
| [Eglantine AMD Experimental 77-2, tag build-99](https://github.com/Djihads80/Eglantine/releases/tag/build-99) (`a42b4d4`) | Standard + PGO, GUI and CLI |
| [Eglantine nx2 build 96](https://github.com/Djihads80/Eglantine/releases/tag/build-96) (`e96917c`) | Standard + PGO, GUI and CLI |
| [PokeDinner 2.1.0a](https://git.eden-emu.dev/Franseven/PokeDinner-a-Eglantine-Fork/releases/tag/2.1.0a) (pre-release; asset named 2.1.0) | GUI and CLI |
| [PokeDinner 2.0.0](https://git.eden-emu.dev/Franseven/PokeDinner-a-Eglantine-Fork/releases/tag/2.0.0) | Previously checked GUI and CLI |

Build 99 is the AMD experimental release, not the regular nx2 build 99. Both latest tracks are listed separately. All targets require their recognized executable bytes or a unique reviewed-code match. Support means patch recognition/detection and reversible installation; it is not a promise of game compatibility or performance.

The ten newly checked executables passed exact apply/remove restoration and **60 isolated native hook cases** (Switch 1/2 NCA, NSP and legacy-container metadata). Real CLI startup comparisons passed for standard Eglantine 98, AMD 77-2/build-99 standard and PokeDinner 2.1.0a: the patch selected the same **31.25 MHz** guest counter as an external companion. PGO native-hook/restore checks passed, but the unmodified PGO CLI also exited with Windows invalid-handle error `0xC0000008` during these startup attempts. Full PGO startup/gameplay is therefore not claimed; those failures did not require a patch to reproduce.

Selevet's two archives contain the same executable. Their frame-limit difference
is in `nx2_switches.txt`; NSP Box changes neither that file nor the 30 FPS option.
Both archives passed exact patch/remove restoration, 12 combined isolated hook
cases and six real GUI startup comparisons using temporary profiles and synthetic
NSPs. The corrected startup selected 31.25 MHz without an external NPDM, matching
the companion path. These are mode/timing checks, not game-boot or FPS benchmarks.
Selevet's existing folded duplicate unwind records are retained in their original
order; only identical pre-existing ranges with matching stack-unwind codes are
accepted, and new or partial overlaps are refused.

The same menu also scans other executable names and future builds automatically.
It compares normalized loader-code fingerprints: relative addresses may move,
while stack layout, instruction shape and detection behavior must match a
reviewed implementation. It also follows the metadata-load call and validates
that reader's code before selecting its actual GetSize/Read virtual-method slots.
Each match must be unique and begin at a Windows
unwind-function boundary. A new matching build is labeled **experimental** and
can be tried without adding a version-specific menu entry. File naming or a
version string alone is never enough to approve a patch.

Selevet minor-update matching has checks for masked linker displacement changes,
changed result registers/stack layouts and supported/unknown VFS reader slots.
A matching future build is still labeled **experimental** and can be restored from
its exact backup. A new version number alone does not establish compatibility.

This does not guarantee every future release or fork. A compiler/loader rewrite,
different architecture, signed executable or unmatched code can require a patcher
update. No match means no executable edits. The patch cannot add Switch 2
emulation to an emulator that does not implement it. Linux ELF/AppImage and
macOS/Android binaries are not supported by this Windows x64 patch. NSP Box itself runs on macOS and Linux; there the dialog
can still patch a Windows x64 emulator folder (for example one used under Wine), and
never modifies macOS or Linux emulator builds.

## What changes

Some builds choose Switch 2 mode by looking for `main.npdm` beside the opened
file, before inspecting a container. The patch adds a read-only native probe of
the existing VFS file. It follows the packager's plaintext HFS0/PFS0 containers,
Program NCA and ExeFS to identify the embedded NPDM's Switch 2 ACID layout.
The emulator's existing Switch 2 memory, clock and hardware-mode path then runs.
It does not force Switch 1 games into Switch 2 mode; unsupported inputs use the
original detection code. Probe reads are bounded to 1 MiB / 8,192 calls with
offset, count and nesting checks. Encrypted retail containers are not decoded.

A small read/execute section and Windows unwind records are added to each
recognized executable, and a reviewed detection hook redirects to it. No DLL,
launcher or extra metadata file is required beside the game. No game, save,
firmware, key, registry, emulator setting or global environment variable is edited.
Existing key configuration requirements still apply.

## Backups and removal

`<emulator folder>/.s2gp-patch/` stores exact originals (`*.exe.original`), a hash
manifest and an OS-managed operation lock. The manifest is saved before any
executable changes. A partial failure rolls back already replaced executables.
If the packager process exits mid-operation, OS locks release and the next run
can recognize each original/patched file independently for recovery.

Removal checks both the current patched executable and its backup before
restoring exact original bytes. Original backups are retained after removal.
If you overwrite or modify the emulator after patching, removal refuses to
overwrite those newer changes. Re-select/re-check after installing an update;
do not mix backups between folders or delete `.s2gp-patch` while patched.
The emulator must be closed; an in-use file can prevent replacement.

## Validation and its limits

Synthetic native probe checks cover both Windows C++ VFS ABIs, Switch 1 and
Switch 2 metadata, NSP/NCA and malformed/truncated input. The actual patched
GUI and CLI hook code was executed in isolated mappings of all six recognized
executables, with synthetic VFS callbacks. Transaction tests cover exact restore,
repeat apply/remove, partial failures, changed backups, manifest path rejection,
locks and forward-match ambiguity. These are detection/transaction checks,
**not a game-boot or performance benchmark**. Installed emulators were not altered.

The original simulated-VFS tests missed PokeDinner's different read slot. The new
real-startup integration check reproduces that failure and checks the corrected
path using actual emulator file objects:

| PokeDinner 2.0.0 startup | Guest counter |
|---|---:|
| Original, manual 12 GiB, no external NPDM | 19,200,000 Hz |
| Original 1.5.0 patch, no external NPDM | 19,200,000 Hz |
| Original emulator with external NPDM | 31,250,000 Hz |
| Corrected patch in 2.0, no external NPDM | 31,250,000 Hz |

Standard Eglantine build 96 also passes the original/companion/corrected startup
comparison. The PGO package could not start its unmodified CLI in this test
environment before writing a log; its reviewed ABI and native probe checks remain
covered, but a full PGO startup comparison is not claimed here. These checks use
null rendering and deliberately invalid synthetic executables; expected ROM-load
failure after mode selection is not a gameplay failure. No FPS comparison is claimed.

## Source and rebuilding

`src/emulator_patch.py` handles recognition, PE updates, backups and restoration;
`src/emulator_dialog.py` provides the UI. `native/container_probe.c` is the original
MIT-licensed probe; `src/emulator_payloads.py` contains its compressed compiled
images. Loader fingerprints contain hashes, normalization masks and generic ABI
prologue anchors, rather than full emulator functions. No upstream emulator
binary or proprietary game code is bundled.

To regenerate the native payload with a build Python environment:

```sh
python -m pip install ziglang==0.16.0 pefile==2024.8.26 capstone==5.0.9
python native/build_probe.py --zig /path/to/zig
```

`native/build_patterns.py --help` documents the four reviewed inputs, including Selevet performance build 4, for rebuilding the reviewed fingerprints
from your own corresponding emulator executables. A changed implementation needs
new source review, hook execution and restore testing before adding a pattern.
Normal app users do not need a compiler or these development dependencies.

Reproduce the real-startup regression with an installed compatible Windows CLI:

```powershell
python native/check_emulator_startup.py --emulator-folder "D:\Emulators\PokeDinner"
```

This stages temporary runtime copies, generates small synthetic metadata/container
fixtures, disables rendering and preserves only diagnostic logs. It neither
copies game images nor modifies the installed emulator or its real profile.

Source references:
[Eglantine core startup](https://github.com/Djihads80/Eglantine/blob/e96917cd0e68851ec389dd519f03b52adc11d493/src/core/core.cpp),
[VFS interface](https://github.com/Djihads80/Eglantine/blob/e96917cd0e68851ec389dd519f03b52adc11d493/src/core/file_sys/vfs/vfs.h),
[NPDM parsing](https://github.com/Djihads80/Eglantine/blob/e96917cd0e68851ec389dd519f03b52adc11d493/src/core/file_sys/program_metadata.cpp).
Eglantine/PokeDinner and their contributors retain their own source licenses;
this independent patch is not endorsed by those projects or Nintendo.
