# NSP Box: A Switch 2 Game Packager

Turn an extracted Switch 2 game dump (ExeFS/RomFS folders) into a plaintext **NSP** that compatible emulators can load. Package DLC as its own NSP, or compress everything into a **NUP** archive. Use the desktop app or the `nspbox` command line.

[Download](https://github.com/DotNetRockStar/NSP-Box/releases/latest) · [Command line](CLI.md) · [NUP](NUP.md) · [DLC](DLC.md) · [Emulator patch](EMULATOR_PATCH.md) · [Build from source](BUILD.md) · [Changelog](CHANGELOG.md) · [Disclaimer](DISCLAIMER.md)

> This fork adds macOS and Linux support and the `nspbox` command line to [smarkyie/NSP-Box](https://github.com/smarkyie/NSP-Box), the original project.

## TL;DR

- **Runs on:** Windows 10/11 x64, macOS 11+ (Apple silicon or Intel) and 64-bit Linux (glibc 2.35+, e.g. Ubuntu 22.04, Debian 12, Fedora 36). Portable: nothing to install, no admin rights, no network.
- **App:** open NSP Box → **Browse folder** → pick your game dump → set the name → **Build NSP**.
- **Command line:** `nspbox build "Mario Kart World" --title "Mario Kart World" -o "Mario Kart World.nsp"`
- **Emulator:** set emulator memory to **12 GiB**. Use PokeDinner 2.5.0 or newer (native Switch 2 NSP support), apply the [emulator patch](EMULATOR_PATCH.md) on Windows, or keep the game's `main.npdm` beside the NSP.
- **Your files only:** NSP Box ships no games, keys, firmware or artwork, and it never changes your source folder.

## Install

1. Download the archive for your system: `Windows-x64` (.zip), `macOS-arm64` (Apple silicon) or `macOS-x64` (Intel) (.zip), or `Linux-x64` (.tar.gz).
2. Extract it to any writable folder.
3. Open `NSP-Box.exe` (Windows), `NSP-Box.app` (macOS) or `NSP-Box` (Linux). On macOS, if the first launch is blocked, go to **System Settings → Privacy & Security → Open Anyway**.

The `nspbox` command-line tool (`nspbox.exe` on Windows) is in the same folder.

## Use the app

1. Click **Browse folder** (or drag the folder in, or paste its path and press Enter) and choose your game dump.
2. Pick the snapshot from the dropdown. The highest version is selected first.
3. Check the **game name** and version. A dump without `control.nacp` takes its name from the folder, so a folder called `base` produces a game called "base"; type the real name here.
4. Optionally add artwork (browse, drag, or paste) and click **Crop icon** to frame it.
5. Choose the output file and click **Build NSP**. Leave **Verify after building** on.

**Create package folder** (on by default) puts the NSP in its own folder with a `main.npdm` copy and a JSON report, for emulators that need `main.npdm` beside the game. Turn it off to save only the NSP.

## Command line

`nspbox` uses the same engine as the app, works without a desktop session, and never overwrites an existing file. Run `nspbox --help` or see [CLI.md](CLI.md) for every option.

### A base game: name it with `--title`

```text
Mario Kart World/
  base/
    exefs/
    romfs/
```

```sh
nspbox scan "Mario Kart World"
nspbox build "Mario Kart World" --title "Mario Kart World" -o "Mario Kart World.nsp" --no-package-folder
```

Without `--title`, a dump that has no `control.nacp` is named after the folder you pass. Pointing at `Mario Kart World/base` would give you a game called "base".

### Base game + update in one NSP, plus its DLC

```text
Donkey Kong Bananza/
  base/
    exefs/
    romfs/
  updates/
    458752/          ← update 2.1.11 (a complete game snapshot)
      exefs/
      romfs/
Donkey Kong Bananza DLC/
  040074a01bf13001/  ← DLC title ID
    0/
      romfs/
```

```sh
# Lists both snapshots; index 0 (the newest, the update) is built by default.
nspbox scan "Donkey Kong Bananza"

nspbox build "Donkey Kong Bananza" --title "Donkey Kong Bananza" --display-version "2.1.11" \
  -o "Donkey Kong Bananza.nsp" --no-package-folder

# DLC is always its own NSP. --base-game checks that it belongs to that game.
nspbox dlc "Donkey Kong Bananza DLC" --base-game "Donkey Kong Bananza.nsp" -o "Donkey Kong Bananza DLC.nsp"
```

`build` packages one complete snapshot. Use it when the update folder holds the whole game, as a dumped update usually does. If the update contains only changed files, merge it through NUP instead. `nup pack` keeps one merged latest snapshot by default.

```sh
nspbox nup pack "Donkey Kong Bananza" --title "Donkey Kong Bananza" -o "Donkey Kong Bananza.nup"
nspbox nup to-nsp "Donkey Kong Bananza.nup" -o "Donkey Kong Bananza.nsp"
```

### Other useful options

```sh
nspbox build "My Game" -s 1 -o "My Game v1.0.nsp"            # build another snapshot from scan
nspbox build "My Game" --title "My Game" --artwork cover.png    # add artwork (center-cropped)
nspbox nup verify "My Game.nup"                                 # check a NUP archive
nspbox build "My Game" -o out.nsp --no-package-folder --json -q # quiet, JSON result for scripts
```

Progress goes to stderr and results to stdout. Exit codes: `0` success, `1` error, `2` invalid arguments, `130` cancelled (Ctrl+C removes the unfinished file). Allow free space of about the game size plus 2%. Large games work: there is no 32 GiB cap.

## Running the NSP in an emulator

- Set the emulator's memory to **12 GiB** before testing Switch 2 games. NSP Box doesn't change emulator settings.
- **PokeDinner 2.5.0+** reads Switch 2 NSPs natively; nothing else is needed.
- **Older Selevet / Eglantine / PokeDinner builds on Windows x64:** apply the reversible [emulator patch](EMULATOR_PATCH.md) from the app's **Emulator patch** panel, or keep the game's own `main.npdm` beside its NSP (that's what **Create package folder** provides).
- **Error 0007-0015 or a missing key in Eglantine:** use **Notes & compatibility → Set up emulator keys folder…** to add the placeholder entries for plaintext packages. These are locally generated placeholders, not Nintendo keys.
- **DLC:** add the DLC NSP through the emulator's install/add-content option. See [DLC.md](DLC.md).

A successful build and verification means the package is intact. It doesn't guarantee that the game boots or plays well in a given emulator.

## Good to know

- **Accepted folders:** a single snapshot (`exefs/` + `romfs/`), or a main folder with `base/` and `updates/<version>/`. An update folder that holds only changed files is not a complete game on its own.
- **Not supported:** encrypted NSP/XCI inputs, decryption, XCI output, and multi-program games.
- **Artwork:** saved as a 256×256 JPEG icon. Most image formats work (PNG, JPEG, WEBP, AVIF, GIF, TIFF, ICO, ICNS …); HEIC and SVG don't.
- **Metadata:** an existing `control.nacp` is kept, with your name and version applied. Otherwise basic metadata is generated, with your name and version.
- **Privacy:** no telemetry, uploads or downloads. The optional JSON report contains local paths; review it before sharing.
- **Linux drag and drop** needs the common `libXcursor` library. Everything else works without it.

More detail: [TECHNICAL_NOTES.md](TECHNICAL_NOTES.md), [NUP.md](NUP.md), [PERFORMANCE_NOTES.md](PERFORMANCE_NOTES.md).

## Legal

**Piracy is not supported.** Use only games, files and artwork you own and are allowed to use. NSP Box includes no Nintendo code, game data, firmware, keys or game artwork. Outputs are unsigned plaintext emulator repacks, not console-installable packages. Nintendo Switch and Nintendo Switch 2 are trademarks of Nintendo. This project is independent and is not affiliated with or endorsed by Nintendo. See [DISCLAIMER.md](DISCLAIMER.md).

The application is MIT-licensed (`LICENSE.txt`); third-party components keep their own licenses (`licenses/`, `THIRD_PARTY_NOTICES.md`).

## Credits

NSP Box was created by [smarkyie](https://github.com/smarkyie/NSP-Box). Thanks to **a55uka** and the [NUP project](https://github.com/a55uka/nup) for the NUP format, **Franseven** for native NSP/NUP support in PokeDinner, and [@hlebushekhub](https://github.com/hlebushekhub) for reporting the old file-size cap.

This is experimental software with limited real-world testing. When reporting a problem, include app and emulator versions, steps and error messages, but no game files, keys or personal paths.
