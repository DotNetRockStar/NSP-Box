"""Operating-system differences shared by the packagers (Windows, macOS and Linux).

Everything here is deliberately small and dependency-free so the command line,
the GUI and the tests all get identical behaviour on every platform.
"""
from pathlib import Path
import ctypes, errno, os, subprocess, sys, unicodedata

# ---------------------------------------------------------------------------
# Commit a finished temporary file/folder to its final name, never replacing.
# ---------------------------------------------------------------------------
# Windows MoveFile refuses an existing destination on NTFS and exFAT alike.
# POSIX rename(2) silently replaces, so macOS/Linux use the kernel's exclusive
# rename where the filesystem supports it, and otherwise reserve the name with
# an exclusive create before renaming over that private placeholder. exFAT,
# FAT32 and many network shares support neither hard links nor exclusive
# rename, which is why the old os.link() commit failed there.

_UNSUPPORTED = {errno.EINVAL, errno.ENOSYS, errno.EPERM, errno.EXDEV,
                getattr(errno, 'ENOTSUP', errno.EOPNOTSUPP), errno.EOPNOTSUPP}
_LINUX_RENAME_NOREPLACE = 1
_DARWIN_RENAME_EXCL = 0x4
_AT_FDCWD = -100
_libc = None

def _c_library():
    global _libc
    if _libc is None:
        try:_libc = ctypes.CDLL(None, use_errno=True)
        except OSError:_libc = False
    return _libc or None

def _exclusive_rename(source, target):
    """Kernel no-replace rename. True on success, False when unsupported."""
    libc = _c_library()
    if libc is None:return False
    try:
        if sys.platform.startswith('linux'):
            call = libc.renameat2
            call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            call.restype = ctypes.c_int
            result = call(_AT_FDCWD, os.fsencode(source), _AT_FDCWD, os.fsencode(target), _LINUX_RENAME_NOREPLACE)
        elif sys.platform == 'darwin':
            call = libc.renamex_np
            call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            call.restype = ctypes.c_int
            result = call(os.fsencode(source), os.fsencode(target), _DARWIN_RENAME_EXCL)
        else:return False
    except AttributeError:return False  # Older C library without the call.
    if result == 0:return True
    code = ctypes.get_errno()
    if code == errno.EEXIST:raise FileExistsError(code, os.strerror(code), str(target))
    if code in _UNSUPPORTED:return False
    raise OSError(code, os.strerror(code), str(source))

def _reserved_rename(source, target):
    """Atomically reserve `target`, then rename over that private placeholder."""
    if Path(source).is_dir():
        os.mkdir(target)  # Fails if anything already uses the name.
        reserved = os.stat(target)
    else:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:reserved = os.fstat(descriptor)
        finally:os.close(descriptor)
    try:
        current = os.lstat(target)
        if (current.st_dev, current.st_ino) != (reserved.st_dev, reserved.st_ino):
            raise FileExistsError(errno.EEXIST, 'Output was replaced during commit', str(target))
        os.rename(source, target)
    except BaseException:
        try:
            current = os.lstat(target)
            if (current.st_dev, current.st_ino) == (reserved.st_dev, reserved.st_ino):
                (os.rmdir if Path(source).is_dir() else os.unlink)(target)
        except OSError:pass
        raise

def commit_no_replace(source, target):
    """Move a finished temporary file or folder into place without replacing anything.

    Raises FileExistsError when `target` already exists, on every platform.
    `source` and `target` must be on the same filesystem (siblings in practice).
    """
    source = Path(source);target = Path(target)
    if os.name == 'nt':
        source.rename(target);return
    if _exclusive_rename(source, target):return
    if not source.is_dir():
        try:
            os.link(source, target)
        except FileExistsError:raise
        except OSError as error:
            if error.errno not in _UNSUPPORTED and error.errno != errno.EMLINK:raise
        else:
            source.unlink();return
    _reserved_rename(source, target)

# ---------------------------------------------------------------------------
# Folder names: ExeFS/RomFS on case-sensitive filesystems (Linux).
# ---------------------------------------------------------------------------
def child(parent, name):
    """Return parent/name, accepting a different letter case on case-sensitive filesystems.

    Windows and macOS normally ignore case, so `parent/'romfs'` already finds
    `RomFS`. Linux does not. The exact spelling always wins; two non-exact
    variants (e.g. `RomFS` and `ROMFS`) are ambiguous and rejected.
    """
    parent = Path(parent);exact = parent/name
    if exact.exists() or exact.is_symlink():return exact
    try:matches = [p for p in parent.iterdir() if p.name.casefold() == name.casefold()]
    except OSError:return exact
    if len(matches) > 1:
        raise ValueError(f'Several folders differ only by letter case ({", ".join(sorted(p.name for p in matches))}). Keep one.')
    return matches[0] if matches else exact

# ---------------------------------------------------------------------------
# Operating-system metadata that must never be packaged as game data.
# ---------------------------------------------------------------------------
# Finder writes .DS_Store into browsed folders, and AppleDouble "._name"
# companions on exFAT/FAT/SMB volumes. Both have fixed signatures, so a game
# file that merely shares the name is never skipped.
_SIGNATURES = (('.DS_Store', b'\x00\x00\x00\x01Bud1'),)
_APPLEDOUBLE = b'\x00\x05\x16\x07'

def is_os_metadata(path):
    """True for a regular file that is macOS Finder/AppleDouble metadata."""
    name = os.path.basename(path)
    if name.startswith('._'):signature = _APPLEDOUBLE
    else:
        signature = next((s for n, s in _SIGNATURES if n == name), None)
        if signature is None:return False
    try:
        with open(path, 'rb') as f:return f.read(len(signature)) == signature
    except OSError:return False

# ---------------------------------------------------------------------------
# Filename comparison for extraction targets.
# ---------------------------------------------------------------------------
def folds_names(directory):
    """True when `directory` treats names differing only by case as the same file.

    Probed rather than guessed: macOS APFS/HFS+ and exFAT on any OS fold case,
    while typical Linux filesystems do not.
    """
    directory = Path(directory)
    if os.name == 'nt':return True
    probe = directory/('.nspbox-case-' + os.urandom(6).hex())
    try:
        with open(probe, 'xb'):pass
    except OSError:return sys.platform == 'darwin'
    try:return (directory/probe.name.upper()).exists()
    finally:
        try:probe.unlink()
        except OSError:pass

def name_key(name, fold):
    """Collision key: case-folded and Unicode-normalised where the filesystem does so."""
    return unicodedata.normalize('NFC', name).casefold() if fold else name

# ---------------------------------------------------------------------------
# Desktop integration.
# ---------------------------------------------------------------------------
def open_folder(path):
    """Open a folder in Explorer, Finder or the Linux desktop's file manager."""
    path = str(path)
    if sys.platform == 'win32':
        os.startfile(path)  # type: ignore[attr-defined]
        return
    command = ['open', path] if sys.platform == 'darwin' else ['xdg-open', path]
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

def prefers_reduced_motion():
    """The OS-wide 'reduce motion' / 'animations off' preference, where readable.

    Windows: SPI_GETCLIENTAREAANIMATION. macOS: Accessibility > Display > Reduce
    motion. Linux: GNOME/Cinnamon/Budgie 'enable-animations'. Unknown -> False.
    """
    try:
        if sys.platform == 'win32':
            enabled = ctypes.c_int(1)
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):  # type: ignore[attr-defined]
                return not enabled.value
            return False
        if sys.platform == 'darwin':
            result = subprocess.run(['defaults', 'read', 'com.apple.universalaccess', 'reduceMotion'],
                                    capture_output=True, text=True, timeout=2)
            return result.returncode == 0 and result.stdout.strip() == '1'
        result = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.interface', 'enable-animations'],
                                capture_output=True, text=True, timeout=2)
        return result.returncode == 0 and result.stdout.strip() == 'false'
    except (OSError, subprocess.SubprocessError, AttributeError, ValueError):
        return False

def config_dir(app='NSPBox'):
    """Per-user settings folder: %LOCALAPPDATA%, ~/Library/Application Support or XDG."""
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA') or Path.home())/app
    if sys.platform == 'darwin':
        return Path.home()/'Library'/'Application Support'/app
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/app

def emulator_keys_dir(emulator='eden'):
    """Default emulator keys folder, used only as a file-picker starting point."""
    if sys.platform == 'win32':
        return Path(os.environ.get('APPDATA') or Path.home())/emulator/'keys'
    if sys.platform == 'darwin':
        return Path.home()/'Library'/'Application Support'/emulator/'keys'
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local'/'share')/emulator/'keys'
