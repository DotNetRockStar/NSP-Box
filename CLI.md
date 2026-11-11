# Command line

NSP Box includes a command-line tool, `nspbox`, with the same packaging engine as the
app. It runs on Windows, macOS and Linux, needs no desktop session or Tk, and never
modifies your source files or overwrites an existing output.

| Download | Command-line binary |
|---|---|
| Windows | `nspbox.exe` (console program beside `NSP-Box.exe`) |
| macOS | `nspbox` beside `NSP-Box.app` |
| Linux | `nspbox` beside `NSP-Box` |
| Source | `python src/cli.py …` (Python 3.11+, `pip install Pillow zstandard`) |

On macOS, the first run of a downloaded unsigned binary may be blocked. Allow it in
**System Settings → Privacy & Security**, or run `xattr -d com.apple.quarantine nspbox`.

## Commands

```text
nspbox scan  FOLDER [--dlc] [--title-id ID]
nspbox build FOLDER [-o OUT.nsp] [-s N] [--title T] [--display-version V]
                    [--artwork IMG [--artwork-fit | --artwork-crop L T R B]]
                    [--no-package-folder] [--no-verify]
nspbox dlc   FOLDER [-o OUT.nsp] [-s N] [--title-id ID] [--dlc-version N] [--base-game GAME.nsp] [--no-verify]
nspbox nup pack     FOLDER  [-o OUT.nup] [--preset Fast|Balanced|Smaller] [--include base,updates,dlc]
                            [--no-latest-snapshot] [--title T] [--artwork IMG] [--no-large-files-raw] [--no-verify]
nspbox nup from-nsp GAME.nsp [-o OUT.nup] [--preset …] [--include …] [--no-verify]
nspbox nup extract  ARCHIVE.nup [-o NEW_FOLDER] [--package N …] [--include …]
nspbox nup to-nsp   ARCHIVE.nup [-o OUT.nsp | NEW_FOLDER] [--package N] [--include …] [--no-verify]
nspbox nup inspect  ARCHIVE.nup [--verify]
nspbox nup verify   ARCHIVE.nup
nspbox --version
```

Every command accepts `--json` (print the full result as JSON on stdout) and `-q`
(hide progress). Run `nspbox <command> -h` for details.

- `scan` lists the snapshots found in a folder with their index, title ID and version.
  `build -s N` selects one; the default `0` is the highest version.
- `build` writes a package folder by default, like the app: `Out/Game.nsp` becomes
  `Out/Game/Game.nsp` with `main.npdm` and a JSON report. Use `--no-package-folder`
  for only the NSP. Without `-o`, the NSP is named after the title, beside the folder.
- NUP commands save beside the source when `-o` is omitted, numbering the name
  (`Game (2).nup`) instead of replacing a previous result.
- Progress goes to stderr; results go to stdout. Exit status: `0` success, `1` error,
  `2` invalid arguments, `130` cancelled.
- **Ctrl+C** cancels cleanly: the unfinished output is removed, exactly as with the
  app's Cancel button.

## Examples

```sh
# See what is in a dump, then package the newest snapshot with artwork.
nspbox scan "/Volumes/Games/My Game"
nspbox build "/Volumes/Games/My Game" -o ~/Packed/"My Game.nsp" --artwork cover.png

# Compress a base + updates + DLC bundle, then check it.
nspbox nup pack "/Volumes/Games/My Game" --preset Smaller
nspbox nup verify "/Volumes/Games/My Game.nup"

# Machine-readable output for scripts.
nspbox build "D:\Dumps\My Game" -o "D:\Packed\My Game.nsp" --no-package-folder --json -q
```

## Earlier command-line forms

The original single-command options still work unchanged, from `nspbox` and from the
app binary: `--package FOLDER --output OUT.nsp [...]` (see [BUILD.md](BUILD.md)) and
`--nup-operation pack|nsp-to-nup|extract|nup-to-nsp|inspect|verify --input … [--output …]`.
On Windows, `NSP-Box.exe` is a windowed program and prints nothing; use `nspbox.exe`
for console output.

## Platform notes

- **exFAT, FAT32 and network drives** are supported for outputs on every system. On
  macOS and Linux the final file is committed with an exclusive rename, or by reserving
  the name first where the filesystem lacks that, so an existing file is never replaced.
- **Folder names** `exefs`, `romfs` and `control` are matched without regard to letter
  case on every system, so dumps with `ExeFS`/`RomFS` work on Linux too.
- **macOS Finder metadata** (`.DS_Store` and AppleDouble `._*` files, identified by their
  file signatures) is never packaged; skipped files are listed as `ignored_os_metadata`
  in the JSON result and report.
