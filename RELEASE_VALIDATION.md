# Validation and compatibility

## NSP Box 4.0

The final release runs the full source suite and frozen NSP/NUP checks in CI.
All 19 focused Game/NUP UI and selection/conversion tests passed locally. Source choices
are hidden before inspection and show only available groups for base-only, DLC-only,
base/update/DLC folders and multi-package NUP archives. Editing/clearing the path,
invalid scans and operation changes remove stale choices; hidden groups cannot
enter the output. The latest-snapshot control appears only for folder inputs with
updates, and explains merging selected base content with the newest update.

## NUP transition checks

All 14 existing Game/NUP UI tests passed. A local six-transition profile reduced
median panel-resize drawing work from 12.49 ms to 0.03 ms; 95th-percentile animation
frame intervals fell from 54.28 ms to 26.48 ms on this machine. These are local UI
measurements, not a guaranteed frame rate on other hardware. Only the two NUP cards
use the reusable rounded caps; other panels retain their existing rendering.

## Selection and presentation checks

The full source suite passed 95 unit/UI/native cases after the polish changes,
with an additional focused UI case for checkbox-filtered extraction. Selection
checks exercise all seven nonempty Base / Updates / DLC combinations before
snapshot merging, standalone update flags, filtered NSP exports, automatic numbered
outputs and no destination dialogs. Custom title/cover tests verify a NUP keeps
original filesystem bytes and carries its intentional presentation overrides through
NSP reconstruction, including a source with existing control metadata.

The startup-modal regression was replaced with the required no-modal/persistent
guidance check. Notes setup buttons, reversible reveal animation, the minimum window
layout, cropper integration and existing Game/DLC behavior are checked. Native-support
wording for PokeDinner 2.5.0 is based on its upstream release notes; no new emulator
binary patch profile or game/FPS test is claimed. No game outputs were generated.

## NUP format and optimization checks

The local preview passed 90 combined unit/UI/native tests, including the existing
67-test baseline, 15 NUP/backend/UI cases and eight optimization/large-file cases. Both directions of reference-tool
interoperability passed at NUP commit 744fb7e. Synthetic checks cover all presets,
raw fallback, size threshold, cross-file dedup, Unicode/empty files, updates/DLC,
selected extraction and metadata retention, malformed/corrupt input refusal,
cancellation cleanup, exact NPDM/NACP/content round trips and responsive tab controls.
The frozen app also exercises all six NUP operations, plus the existing nine NSP
cases and four native file drops. These are format/UI checks, not gameplay tests.
No real game data is included in this build or its fixtures. See NUP.md.

The decoder error was reproduced with a valid 10 MB frame requiring a 2 MiB window;
the corrected decoder verifies and extracts it. Regression checks count compressor
calls and unique-extent verification, distinguish matching prefixes from matching
files, ensure fast NSP inspection avoids payload hashes while conversion detects
corruption, and reject changed cached files/directories. Structural 40/96 GiB NSP
and virtual 40 GiB NUP tests exercise 64-bit sizes without writing huge fixtures.
No full real-game output above 32 GiB has been generated for validation.

A local synthetic comparison with 3.2.0 used 128 identical 1 MiB files. Packing plus
verification measured 0.287 s → 0.092 s; indexing a 32 MiB plaintext NSP measured
0.043 s → 0.0012 s. These are small synthetic, warm-cache observations, not promised
whole-game conversion times or a benchmark against Eglantine.

## NSP Box 3.1

The release requires all **67 unit/UI/native tests**, **nine frozen NSP packaging
cases** and a **four-drop frozen native file-drop/clean-shutdown check**. Fixtures
are synthetic and contain no game data. PNG, WEBP, ICO and AVIF artwork are checked
in single-file and package-folder game modes, plus a separate DLC NSP case.

The drag-and-drop crash in issue #2 was reproduced on Windows in the real Tk
mainloop before the fix. Native callbacks now queue paths without calling Tcl/Tk;
normal Tk timers handle the dropped files. Regression coverage includes repeated
folder/image drops and Unicode WEBP filenames.

The Game/DLC tabs and emulator patch dialog were inspected visually. UI checks
cover minimum-size control visibility, artwork paste/crop, tab transitions, icon
cache reuse, gradient layering, reduced-motion behavior and timer cleanup.
The ambient layer shares one Tk image across canvases and pauses when minimized.
All 22 PNG assets have RGBA transparency and no embedded PNG metadata.

## Emulator patch checks

All 17 exact Windows x64 GUI/CLI profiles have patch/remove restoration coverage.
The ten added executable variants passed exact restoration and 60 isolated native
hook cases. Standard Eglantine 98/build-99 and PokeDinner 2.1.0a startup comparisons
selected 31.25 MHz with the patch, matching their external-companion paths.
Unmodified PGO CLI startup failed with 0xC0000008 in the test environment, so full
PGO startup or gameplay compatibility is not claimed. No emulator binaries ship
with NSP Box. See [supported targets and limits](EMULATOR_PATCH.md).

Selevet performance build 4 normal/30 FPS archives contain one shared executable
and passed SHA-256 checks against their release metadata. Both passed byte-exact
patch restoration with all non-executable files unchanged, 12 combined isolated
native hook cases and six real GUI startup comparisons using disposable profiles.
Patched companion-free startup matched the external-NPDM path at 31.25 MHz;
unpatched/no-companion startup selected 19.2 MHz. No games or FPS were tested.
Six additional forward-matching checks cover linker displacement changes, mode
register/stack changes, reader ABI selection and refusal of unknown reader slots.
Synthetic regression tests cover the Selevet wrapper's live-file/R13 mode behavior,
guarded preservation of pre-existing duplicate unwind records, and patch-dialog
layout with the expanded compatibility list.

## Real-world limits

A user installed a Bananza DLC NSP in PokeDinner 2.0.0 and confirmed in-game
recognition. This is one successful test, not universal DLC compatibility.
Actual game data and original title IDs are required; generated metadata cannot
recreate missing game services or original required-update information.

Set emulator memory to 12 GiB before testing Switch 2 packages. Without the patch,
an external exact `main.npdm` can still be needed for the checked loader's early
Switch 2 memory/clock selection. 12 GiB alone may boot with incorrect timing and
reduced performance. Integrity checks do not guarantee booting, gameplay or FPS.

Shipped binary targets are Windows x64, macOS arm64/x64 and Linux x64. The
macOS and Linux builds were validated locally (macOS 26 arm64; Linux arm64 in a
container under Xvfb) with the full synthetic suite, frozen NSP/DLC/NUP/CLI smoke
tests and GUI start-up; the x64 macOS/Linux and Windows binaries are validated by
the release workflow on their runners. A clean installation without Python and
every graphics driver/emulator configuration have not been tested. This is experimental software with limited real-world testing; please
[report reproducible problems](https://github.com/smarkyie/NSP-Box/issues/new).
