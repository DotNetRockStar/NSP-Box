# Publishing releases

Downloads are available on the repository's [Releases page](https://github.com/smarkyie/NSP-Box/releases). Each release includes portable archives for Windows x64, macOS arm64, macOS x64 and Linux x64, a source ZIP and SHA-256 checksums.

## Publish a version

1. Commit changes to `main`, update `VERSION` in `src/engine.py`, and add a matching entry in `CHANGELOG.md`.
2. Open **Actions → Build and release → Run workflow**, select `main`, and run it. Alternatively, push a matching version tag.
3. On each of the four platforms the workflow runs the synthetic tests (GUI tests under Xvfb on Linux), builds the app and the `nspbox` command line, checks PNG/WEBP/ICO/AVIF artwork with NSP in single-file and package-folder modes, exercises every NUP and command-line operation and confirms the app window starts. It then assembles each portable archive; the Windows job also builds the source ZIP. A final job collects every archive, writes one `SHA256SUMS.txt` and publishes the release only if all platforms succeeded.
4. A successful job publishes a release tagged at its source commit. Existing releases are not overwritten; use a new version for updated downloads.

Release notes include lawful-use and ownership notices and the current emulator-patch instructions, memory-setting guidance and companion workaround for unpatched builds. Keep these notices and the required dependency licenses with redistributed copies.

## Release contents

`package_release.py` selects application files explicitly. Game dumps, generated game packages, local build reports, game artwork, firmware, retail keys and emulator binaries are excluded. Review the selected files and current compatibility notes before publishing.

Builds run on GitHub's Windows, macOS (`macos-14` arm64, `macos-15-intel` x64) and Ubuntu 22.04 runners using the workflow's temporary repository token. macOS apps are ad-hoc signed; optional Developer ID signing and notarization run when the `MACOS_CERTIFICATE_P12`, `MACOS_CERTIFICATE_PASSWORD`, `MACOS_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID` and `APPLE_APP_PASSWORD` secrets are configured. Pushes and pull requests also run the tests on all three systems (`.github/workflows/ci.yml`). Generated `build/`, `dist/`, `release/` and `test-work/` directories are ignored by Git. See [BUILD.md](BUILD.md) for local builds.
