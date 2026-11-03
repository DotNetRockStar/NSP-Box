# DLC packaging — NSP Box

The **DLC** tab packages a complete extracted add-on RomFS into a separate
plaintext NSP. It does not change or merge into your base-game package.
No ExeFS, game executable, artwork or external `main.npdm` is needed for DLC.
The existing **Game** tab and **Emulator patch** feature remain available.

## Build and use

1. Select the DLC folder, a title/version folder, or its `romfs` directory.
   Dropping the folder into the app while the DLC tab is selected also works.
2. Choose the snapshot. Confirm the **original DLC title ID** and numeric DLC
   version. These normally come from a layout such as
   `dlc/0400111122221001/0/romfs/...`. An unnamed folder requires its original
   title ID; do not invent an ID or rename a base/update snapshot as DLC.
3. Optionally select the base game's plaintext NSP. The app checks the
   Program ID and control metadata's DLC base ID without copying or hashing the
   full base-game payload. Encrypted inputs are not supported.
4. Choose an NSP output filename and leave verification on. Click **Build DLC NSP**.
5. Close the running game. In your emulator, use **File → Install Files to NAND**
   (wording varies), and select the DLC package. Check the game's
   **Properties → Add-ons** and enable the DLC, then launch the base game again.
   Remove installed DLC through the emulator's content-management controls.

A DLC NSP is an add-on package, not a standalone game. Install it and launch the
base game. Some emulator versions can scan external DLC folders instead, but
this varies between forks. The app does not install content or edit emulator
profiles automatically. NSP Box creates NSP packages only.

## What is generated and what is unverified

The package contains one Data NCA (type 4) with a RomFS/IVFC integrity tree and
one Meta NCA containing an AddOnContent CNMT (type 0x82). The Data content record
uses type 2/index 0; its size, ID and SHA-256 are generated from the actual NCA.
The CNMT links to the base application ID derived from the original DLC title
ID, using the emulator's add-on ID convention. A 24-byte extended header stores
that application ID, with unknown required-application-version, accessibility
flags and data-patch ID left at zero. Metadata is minimal, unsigned emulator
metadata; it does not reconstruct the original signed content metadata.

This release supports a single data RomFS per DLC title/version. Multiple
DLCs/versions can be selected and built separately. Split multi-content DLC,
DataPatch/BKTR differences, encrypted containers and retail-console installation
are outside its scope. Version 0 is used when no numeric version folder exists;
enter the original numeric version when known. Use the matching base-game
update: the tool cannot infer the original version requirement from loose files.

NSP streams directly to output and shares the game packager's wrapper.
Verification checks all RomFS files, integrity trees, NCA hashes and CNMT mapping.
No companion or report file is created in DLC mode. Existing outputs and inputs
are preserved; unfinished output is removed on cancellation or failure.

The user installed the generated Bananza DLC NSP on PokeDinner 2.0.0 and confirmed
that the game successfully recognized it. Container/source verification also
passed for all 8,000 extracted files and the base-game title mapping. This is a
user-confirmed result for one game/build, not a guarantee for other DLC or forks.
Packaging cannot add unimplemented emulator services. Existing plaintext-key
setup and base-game memory/emulator-patch requirements still apply.

Format references:
[Eglantine content registration](https://github.com/Djihads80/Eglantine/blob/nx2/src/core/file_sys/registered_cache.cpp),
[add-on service](https://github.com/Djihads80/Eglantine/blob/nx2/src/core/hle/service/aoc/addon_content_manager.cpp),
[title-ID helpers](https://github.com/Djihads80/Eglantine/blob/nx2/src/core/file_sys/common_funcs.h),
[CNMT fields](https://switchbrew.org/wiki/CNMT).

Use only your own lawfully obtained content that you are authorized to use.
Piracy is not supported. No game/DLC files, keys, firmware or emulator binaries
are included in the app/source downloads. See [DISCLAIMER.md](DISCLAIMER.md).
