# NSP Box: A Switch 2 Game Packager

[Download](https://github.com/smarkyie/NSP-Box/releases/latest) · [Build from source](BUILD.md) · [Changelog](CHANGELOG.md) · [Disclaimer](DISCLAIMER.md)

A portable Windows app that packages a complete, already-extracted ExeFS/RomFS snapshot into a plaintext NSP for compatible emulators. Choose a folder, add your own artwork, and build an NSP.

**NSP Box 3.1** adds emulator-patch support for [Selevet performance build 4](https://github.com/sylvieistaken/selevet-eglantine/releases/tag/selevet-eglantine-performance-4), both normal and 30 FPS downloads, plus fingerprint matching for compatible minor updates. Future matches are experimental and still require a unique reviewed loader and metadata reader. The app includes redesigned icons, a subtle animated blue/indigo background and smooth transitions. It retains the NSP-only Game/DLC workflows and the Windows drag-and-drop fix for [issue #2](https://github.com/smarkyie/NSP-Box/issues/2). Native drop events queue paths for Tk to handle safely during its normal event loop.

Use **Game** for complete ExeFS/RomFS snapshots and **DLC** for separate RomFS-only add-ons. A user installed the Bananza DLC NSP and confirmed that the game recognized it in PokeDinner 2.0.0. This is one successful user test, not universal DLC compatibility. See [DLC instructions](DLC.md).

The reversible **Emulator patch** panel now lists its supported Windows x64 targets: Selevet performance build 4 (normal/30 FPS GUI), Eglantine nx2 98/96, AMD Experimental 77-2 (build-99), and PokeDinner 2.1.0a/2.0.0. Standard/PGO and GUI/CLI variants are identified explicitly. Compatible Windows x64 Selevet/Eglantine/PokeDinner builds read the metadata inside an NSP, so a separate `main.npdm` beside the game is unnecessary after applying the patch and restarting. See [patch installation, removal and limits](EMULATOR_PATCH.md). Windows x64 downloads only; no Linux build is included.

**Piracy is not supported.** Use only files and artwork you have lawfully obtained and are authorized to use. No games, game artwork, firmware or Nintendo keys are provided. Nintendo Switch, Nintendo Switch 2 and related marks belong to Nintendo; game content belongs to its respective rights holders. This is an independent project, not affiliated with, sponsored by or endorsed by Nintendo. See [ownership and use notices](DISCLAIMER.md).

> **Caution — experimental software:** set emulator memory to **12 GiB** before testing Switch 2 packages. The app does not change this setting. The patch is optional and only applies to recognized compatible code; it cannot add Switch 2 emulation to an unsupported emulator. Verification checks package integrity, not booting or gameplay.

A startup caution explains this before using the GUI. **Don't show this again** stores only a local preference under `%LOCALAPPDATA%\NSPBox\preferences.json`; the same guidance remains in **Notes & compatibility**. Command-line builds do not show a dialog.

**Without the emulator patch**, retain the exact game's external `main.npdm` in its own package folder. Selecting 12 GiB alone can boot with Switch 1 timing and reduced performance. The corrected patch matches external-NPDM startup timing in the checked builds; equal FPS across all games/builds is not guaranteed.

NSP output streams directly to its destination without an intermediate container. The app includes square artwork cropping, clipboard and drag-and-drop support, progress/cancellation, and full output verification.

**Experimental build with limited real-world testing.** If anything goes wrong, [open an issue](https://github.com/smarkyie/NSP-Box/issues/new) with your app/emulator versions, reproduction steps and error messages. Do not upload game files, keys or personal paths.

## Quick start

1. Extract the entire ZIP to a writable folder.
2. Open `NSP-Box.exe`. Python is bundled; installation is not required.
3. Click **Browse folder** and select your main game dump folder, or drag the folder into the window. Pasting a folder path and pressing Enter also works.
4. Select the complete snapshot you want from the dropdown. The app reads its title ID from `main.npdm`.
5. Edit the displayed game name/version if needed. Add, drop or paste artwork, then click **Crop icon** to position it. Select an NSP destination filename in Output.
6. Leave **Verify after building** checked. **Create package folder** beneath it is on by default: a folder named after the output file contains the package, a metadata companion and JSON verification report. Uncheck it to save only the selected NSP. Then click **Build NSP**.

The app never overwrites an existing package and does not modify your source files. Cancellation removes the unfinished package. Verification works in both modes; it does not require saving a report. Allow roughly the input size plus 2% and 32 MB free disk space. Packages up to **32 GiB** are supported.

With **Create package folder** enabled, `D:\Packed\Game.nsp` is saved as `D:\Packed\Game\Game.nsp`, with `main.npdm` and `Game.nsp.report.json` beside it. The companion is an optional workaround for the checked loader's early Switch 2 memory/clock detection. Keep each game/snapshot in a separate folder if using it; a conflicting companion is refused. The exact snapshot metadata is also embedded inside the package in both modes. After applying the emulator patch, the companion is unnecessary for supported containers: the emulator reads the embedded metadata. Keep the original companion as a backup if you plan to remove the patch.

NSP is a PFS0 container with Program, Control and Meta NCAs for games, or Data and Meta NCAs for DLC. It is not compressed. Outputs are unsigned plaintext emulator repacks; this does not make them authenticated retail-console packages. Loading depends on the emulator's plaintext-content support. NSP Box does not create XCI files.

## Use the emulator patch

1. Fully close the emulator and open **Emulator patch** in the packager header.
2. Select the folder containing the Windows x64 Selevet/Eglantine/PokeDinner executables, then **Check** and **Add patch**. Matching unverified builds offer **Try patch** with an experimental warning.
3. Restart the emulator. Open your NSP from a folder without an external `main.npdm`. Existing packages already contain their metadata and do not need rebuilding.
4. For new single-file outputs, uncheck **Create package folder**. It remains on by default for compatibility with unpatched emulators.

The packager need not stay open while playing. **Remove patch** restores exact backed-up executable bytes; retain the emulator folder's `.s2gp-patch` directory while patched. If **Older patch** appears, remove it before adding the corrected patch. Re-check after emulator updates. Future releases/forks must match the reviewed loader and metadata-reader code; unmatched or ambiguous executables are not modified.

## Accepted folder layouts

Direct snapshot:

```text
My Game/
  exefs/
    main
    main.npdm
    rtld, sdk, subsdk* ... (as present in your dump)
  romfs/
    ... complete game filesystem ...
```

Main folder with snapshots:

```text
My Game/
  base/
    exefs/...
    romfs/...
  updates/
    65536/
      exefs/...
      romfs/...
```

An empty `base` folder is fine when an update folder already contains the complete mounted game filesystem. A folder containing only update differences is **not** sufficient. Completeness cannot be reliably determined from filenames; select a snapshot you know is complete.

The Game tab does not merge separate updates or DLC; DLC folders are left out of game snapshots. Use the DLC tab to create a separate add-on package for installation through a compatible emulator. Multi-program applications, patch-only/BKTR data, encrypted NSP/XCI inputs, compressed ROM packages, decryption, and authenticated cartridge reconstruction are outside this release's scope. This is a snapshot packager, not an emulator or a universal game converter.

## Artwork and metadata

Artwork is exported as a **256×256 JPEG**, suitable for the emulator library icon. New artwork starts with a centered square crop. **Crop icon** opens an editor with drag-to-position, mouse-wheel/slider zoom, a live icon preview, Reset, Apply and Cancel. **Fit whole image** retains the entire image with padding instead. Cropping never changes the original file.

Supported inputs include PNG, JPEG/JFIF, WEBP, AVIF, GIF, TIFF, BMP/DIB, Windows ICO, Mac ICNS, TGA, PPM/PGM/PBM/PNM and JPEG2000. Animated or multi-page inputs use the first frame/page; icon containers use Pillow's selected image, normally the largest available. HEIC/HEIF and SVG are not decoded by this build.

Use **Paste** or **Ctrl+V** to add a copied bitmap, copied artwork file, or local image-file path. Ordinary text pastes in text fields continue to work normally. You can also drag one artwork file into the app. Clipboard images are held in temporary PNG files until the app closes; the app reads the clipboard only when you request a paste. Copying a URL alone does not download its image.

The app embeds the selected crop in the game NSP. No game artwork ships with this app.

If a standard `control.nacp` is present at the snapshot/main root or under `control/`, the app preserves it and updates uncompressed title text and the display version. Otherwise it generates basic control metadata. Generated fields are not a recreation of all original save-size, network, language, or DLC settings. A folder version such as `327680` is a numeric dump version, not necessarily a human-readable game version.

## Eglantine plaintext compatibility entries

Some Eglantine builds require key entries even when NCA headers and sections are plaintext. This package includes `compatibility/plaintext-repack.keys`, containing **locally generated placeholders**, not Nintendo keys. They cannot decrypt retail content. The app does not install them or change emulator configuration automatically.

If Eglantine reports **0007-0015** or a missing key for this app's plaintext images, close it and use **Notes & compatibility → Set up emulator keys folder…**. Select that profile's `keys` folder, commonly `%APPDATA%\eden\keys` or `user\keys` beside a portable emulator. Setup adds only missing plaintext placeholders to `prod.keys_autogenerated`, preserves existing entries and never writes `prod.keys`. An existing autogenerated file is backed up before appending; invalid existing entries are reported rather than replaced. Restart the emulator afterwards.

Manual export remains available:

1. Close Eglantine and open its user keys folder, commonly `%APPDATA%\eden\keys`.
2. If `prod.keys_autogenerated` does not exist, copy `plaintext-repack.keys` there and rename the copy to `prod.keys_autogenerated`.
3. If that file already exists, keep it. Back it up before editing and add **only missing** placeholder entries. Keep all real keys in `prod.keys`; that file takes precedence in the checked Eglantine loader.
4. Restart Eglantine.

The GUI's export button saves another copy without overwriting anything. Setup runs only when explicitly selected, never during scanning/building. These placeholders support this app's plaintext repacks; they do not replace your own retail keys for encrypted games. Eglantine forks can differ; consult the fork's documentation if its key-loading rules differ.

## Portability and privacy

- Windows 10/11 x64; no administrator rights, Python installation, emulator installation, or network connection required.
- The one-file EXE unpacks its bundled runtime into the Windows temporary directory at launch and cleans it up on normal exit.
- No telemetry, upload or automatic downloading. Emulator setup runs only when explicitly selected; builds do not change emulator configuration.
- When package-folder output is enabled, paths appear in its local JSON report. Review or remove reports before sharing them if you do not want to disclose local folder names.
- This release is unsigned. No claim of Nintendo authentication or endorsement is made.

## Source and redistribution

Full application source, icon assets and synthetic tests are available in the separate source ZIP on the [release page](https://github.com/smarkyie/NSP-Box/releases/latest). The portable ZIP contains the app, documentation and required license notices; it does not duplicate the source. In this repository, application modules are under `src/` and tests are at the root. The original application code is released under the MIT license in `LICENSE.txt`; third-party components retain their own licenses under `licenses/` and `THIRD_PARTY_NOTICES.md`.

You may redistribute the app and source with the required license notices. The software was developed with AI assistance. This package includes no Nintendo code, game data, game cover artwork, console firmware, tickets, certificates, or Nintendo cryptographic keys. Use your own extracted data and artwork; redistribution rights for input/output content are separate from the app's license.

See `TECHNICAL_NOTES.md` for implementation details and `BUILD.md` in the source ZIP to rebuild the EXE. See `GITHUB_RELEASES.md` for publishing future versions.
