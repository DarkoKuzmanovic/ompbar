import os
import shutil
from collections.abc import Mapping
from configparser import ConfigParser, Error
from pathlib import Path


def _expand_user_path(value: str, home: Path) -> Path:
    if value == "~":
        return home
    if value.startswith("~/"):
        return home / value[2:]
    path = Path(value).expanduser()
    return path if path.is_absolute() else home / path


def resolve_default_cwd(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    home = Path(env.get("HOME") or Path.home())

    override = env.get("OMPBAR_CWD")
    if override:
        return _expand_user_path(override, home)

    config_home = env.get("XDG_CONFIG_HOME")
    config_dir = (
        _expand_user_path(config_home, home) if config_home else home / ".config"
    )
    parser = ConfigParser(interpolation=None)
    try:
        parser.read(config_dir / "ompbar" / "config.ini", encoding="utf-8")
        configured_cwd = parser.get("ompbar", "default_cwd", fallback="")
        return _expand_user_path(configured_cwd, home) if configured_cwd else home
    except (Error, UnicodeDecodeError, RuntimeError):
        # shortcut: a broken config silently means home; report it if that confuses users.
        return home


def resolve_omp_executable(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    home = Path(env.get("HOME") or Path.home())

    override = env.get("OMPBAR_OMP")
    if override:
        return _expand_user_path(override, home).resolve()

    found = shutil.which("omp", path=env.get("PATH"))
    if found:
        return Path(found).resolve()

    return (home / ".bun" / "bin" / "omp").resolve()
