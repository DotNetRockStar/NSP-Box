# Release notes

## 3.1.0 — 2026-11-02

- **Selevet support:** the emulator patcher now supports Selevet Eglantine performance build 4, including both normal and 30 FPS Windows downloads.
- **Future-build matching:** minor Selevet updates can be recognized when the reviewed loader and metadata-reader fingerprints still match. Unverified matches are labeled experimental; changed or ambiguous hooks are refused.
- **Settings preserved:** adding or removing the metadata patch keeps `nx2_switches.txt` and the existing 30 FPS setting unchanged. Exact original executable backups remain available for removal.
- **Supported-build list:** added Selevet and adjusted the patch dialog so its full compatibility list remains visible.
- **Validation:** both Selevet downloads passed byte-exact patch removal, isolated native hook checks and real startup timing comparisons. Patched startup without a companion matched the external-NPDM path at 31.25 MHz. These checks do not establish gameplay compatibility or FPS gains.

**Experimental build with limited real-world testing.** Please [open an issue](https://github.com/smarkyie/NSP-Box/issues/new) with your NSP Box/emulator versions, steps and error messages if something goes wrong. Remove personal information from logs and never upload games or keys.

## 3.0.0 — 2026-11-01

- **New branding:** NSP Box, with redesigned icons and a new app logo.
- **Smoother UI:** subtle animated background, fluid transitions, and improved spacing.
- **NSP-only packaging:** removed XCI output from games and DLC.
- **Dedicated DLC tab:** create separate DLC NSPs for compatible emulators. Thanks [@ryzendew](https://github.com/ryzendew) for requesting separate packages in [#1](https://github.com/smarkyie/NSP-Box/issues/1).
- **Expanded patch support:** Eglantine build 98, AMD Experimental build-99, and PokeDinner 2.1.0a. Supported builds are now listed in the patch panel.
- **Fixed drag-and-drop crashes:** artwork and folder drops no longer crash the app. Thanks [@WicCaesar](https://github.com/WicCaesar) for reporting [#2](https://github.com/smarkyie/NSP-Box/issues/2).
- **Windows x64 portable release**, with source code included as a separate download.
- **Existing game packages don't need rebuilding** to use the expanded emulator patch support.

**Experimental build — limited real-world testing.** Emulator and DLC compatibility varies. Supported patched emulators can load packages without an external `main.npdm`.

**Found a problem? Please [open an issue](https://github.com/smarkyie/NSP-Box/issues/new)** with your app/emulator version, steps to reproduce, and any error messages. Your reports help improve the next build.

## 2.0.0 — 2026-11-01

- **New Emulator patch panel:** select a Windows x64 emulator folder, check compatibility, add the patch and remove it later. Eglantine build 96 standard/PGO and PokeDinner 2.0.0 GUI/CLI profiles are recognized; matching future builds and forks can be tried experimentally without a new menu entry.
- **No separate `main.npdm` needed after patching:** compatible emulators read Switch 2 metadata already embedded inside this packager's plaintext XCI/NSP. Restart the emulator after applying the patch. Existing packages do not need rebuilding, and the packager need not remain open while playing.
- To create only a single XCI/NSP, uncheck **Create package folder**. The option remains on by default for unpatched emulators; without the patch, retain each game's exact external companion in its own folder. Selecting 12 GiB alone can still use incorrect timing and reduce performance.
- Save exact executable backups, apply changes atomically and restore original bytes on removal. Unknown, ambiguous or signed executables are not modified. Keep `.s2gp-patch` while patched and re-check after emulator updates; compatibility with every fork/future build is not guaranteed.
- Include the corrected PokeDinner file-reader probe. Startup checks match the external-file path's 31.25 MHz timer; selecting 12 GiB alone and the earlier local patch used 19.2 MHz. Older local patches can be removed before applying this version. These are startup checks, not an FPS guarantee.
- Fix the clipped letters/path field below **Browse folder**, compact drop-area spacing and the square background around its rounded icon/button.
- Update the startup caution, compatibility notes, source and build instructions. Windows x64 portable app, source and SHA-256 checksums are included. **No Linux build is included.**
- This remains experimental software. No games, artwork, firmware, retail keys or emulator binaries are included. Piracy is not supported; Nintendo and other rights holders retain ownership of their content and marks.

## 1.4.4 — 2026-10-31

- Add the reported performance drop without an external `main.npdm` to the startup caution, Notes & compatibility, README and release notes.
- Recommend keeping **Create package folder** enabled and retaining its companion beside the game. The performance observation is user-reported, not a controlled benchmark.
- Refresh remembered-caution preferences so the new warning is shown after an older notice was dismissed.
- Retain the 12 GiB guidance, default-on package-folder option and single-file output when unchecked. Packaging behavior is unchanged from 1.4.3.

## 1.4.3 — 2026-10-31

- Add a styled startup caution about experimental compatibility and the emulator 12 GiB memory setting, with a local remember-dismissal option.
- Add **Create package folder** below verification, on by default. Folder output includes metadata and a verification report; uncheck it to save only the XCI/NSP.
- Add `--package-folder` for command-line builds and retain full verification in either mode.
- Clarify the reported PokeDinner 2.0.0 boot without an external companion after selecting 12 GiB. No universal gameplay compatibility is claimed.
- Add startup-dialog, dismissal, output-file and folder-mode regression coverage.

## 1.4.2 — 2026-10-31

- Add lawful-use, anti-piracy, Nintendo ownership and non-affiliation notices to the README and release downloads.
- Simplify download, build and publishing documentation; remove access-specific wording and internal development details.
- Clarify that verification checks package integrity and does not guarantee booting or gameplay. Keep the external `main.npdm` requirement prominent for the checked PokeDinner/Eglantine builds.
- Include `DISCLAIMER.md` in portable and source archives and add concise notices to generated release notes.
- Documentation and release-packaging update; game conversion behavior is unchanged from 1.4.1.

## 1.4.1 — 2026-10-31

- Emit the snapshot's exact `main.npdm` beside XCI and NSP so early detection in the checked PokeDinner/Eglantine loader selects Switch 2's memory layout and clock.
- Give each game/snapshot a separate default output folder; refuse a different existing companion and preserve files created concurrently. Record the companion hash and remind users to keep it beside the package.
- Correct generated NACP platform/error-prefix offsets, and read TitlesDataFormat at the documented offset so compressed title data is preserved.
- Add explicit **Set up emulator keys folder…** under Notes & compatibility for missing plaintext placeholders, with preservation of real keys/existing entries, backups and validation.
- Add regression tests for metadata, companion files, concurrent-file preservation and compatibility setup. Limited rendering checks used the companion workaround; standalone booting was not established.
- Add GitHub Actions builds and releases, excluding game content and local build caches.

## 1.4.0 — 2026-10-31

- Added a rounded XCI/NSP selector in Output; format changes update the destination extension, save dialog, build button and completion status.
- Added direct streaming NSP/PFS0 packaging with Download distribution metadata, correct content IDs and CNMT references; no intermediate XCI or NCA files.
- Shared all source scanning, integrity-tree construction, artwork processing and verification optimizations with XCI.
- Added format-aware CLI output (`--format xci|nsp`, or infer from the filename) and JSON reports.
- Added NSP payload/metadata/artwork round trips, no-extra-source-pass checks, cancellation, corruption, no-overwrite, format-mismatch and UI coverage.
- Preserved all existing UI features and the executable filename for compatibility. This release still packages one complete extracted snapshot; it does not merge separate patch/DLC inputs or convert existing encrypted containers.

## 1.3.0 — 2026-10-31

- Replaced repeated RomFS sibling searches with a linear pass for large file collections.
- Reused directory metadata and known file sizes to reduce filesystem queries.
- Captured source SHA-256 while writing, retaining full independent output verification without rereading all originals.
- Reused complete NCA hashes for CNMT checks and used scoped zero-copy views for output hashing.
- Added file-count feedback for scanning and RomFS table creation, plus stage timings in JSON reports.
- Added corruption, source-mutation and mmap-cleanup regression tests; documented measurements and NSP feasibility.
- Retained every existing GUI and artwork feature. Output remains XCI only.

## 1.2.0 — 2026-10-31

- Added **Crop icon**: square positioning, drag/pan, slider and wheel zoom, live 256×256 preview, reset, apply and cancel.
- Center-crop artwork by default, with **Fit whole image** retained in the editor.
- Added a Paste button and Ctrl+V for copied images and artwork files; retained normal text pasting.
- Extended the artwork picker and drop handler to WEBP, AVIF, GIF, TIFF, ICO, ICNS, TGA, portable bitmap formats and JPEG2000, alongside PNG/JPEG/BMP.
- First-frame/page decoding, EXIF orientation, alpha handling and source preservation are shared by preview and output.
- Added artwork/crop/clipboard tests and updated portable runtime checks and redistribution notes.

## 1.1.0 — 2026-10-31

- Minimal reference-inspired layout with separate game files, game details, output and cover-art cards.
- Rounded antialiased panels, input fields and buttons; supersampled original icons.
- Subtle cubic-eased button hover, panel entrance, artwork reveal, status and progress animations.
- No animations toggle; automatic respect for Windows' motion preference.
- Native Windows shell drops for game folders and artwork, alongside existing browse/path-entry controls.
- Every prior packaging control retained: snapshot selector, editable title/version, automatic title ID, artwork removal, output selection, full verification, build cancellation, output-folder access, notes and compatibility export.
- Responsive layout checked at the minimum window size; fixed shutdown callback cleanup.
- Two UI integration tests added; source, licensing and notes updated for redistribution.

## 1.0.0 — 2026-10-31

- Portable Windows x64 EXE with bundled Python/Tcl/Tk/Pillow runtime.
- Main game-folder selection and automatic discovery of sibling ExeFS/RomFS snapshots.
- Title ID detection from NPDM, editable display name and version.
- User-selected artwork, fitted to a square library icon without cropping.
- Plaintext Program/Control/Meta NCA generation and trimmed XCI/HFS0 packaging.
- Full source-payload comparison, container integrity checks and local JSON reports.
- Background progress, cooperative cancellation, removal of unfinished output and refusal to overwrite existing XCIs.
- Optional export of local plaintext compatibility placeholders. No automatic emulator changes.
- Full source code, tests, build recipe, MIT license and third-party notices included.

Initial scope is one complete mounted snapshot at a time, up to 32 GiB. Separate DLC, patch-only inputs, automatic base/update merging, and multi-program packages are not supported. Compatibility with every Switch 2 game or emulator is not established.
