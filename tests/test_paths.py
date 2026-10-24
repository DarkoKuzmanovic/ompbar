from pathlib import Path

from ompbar.paths import resolve_default_cwd, resolve_omp_executable


def test_environment_directory_overrides_config_and_expands_home(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    config_home = tmp_path / "config"
    config_dir = config_home / "ompbar"
    config_dir.mkdir(parents=True)
    (config_dir / "config.ini").write_text(
        "[ompbar]\ndefault_cwd = ~/from-config\n", encoding="utf-8"
    )

    result = resolve_default_cwd(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(config_home),
            "OMPBAR_CWD": "~/from-env",
        }
    )

    assert result == home / "from-env"


def test_config_directory_overrides_home_and_expands_tilde(tmp_path: Path) -> None:
    home = tmp_path / "home"
    config_home = tmp_path / "config"
    config_dir = config_home / "ompbar"
    config_dir.mkdir(parents=True)
    (config_dir / "config.ini").write_text(
        "[ompbar]\ndefault_cwd = ~/projects/demo\n", encoding="utf-8"
    )

    result = resolve_default_cwd(
        {"HOME": str(home), "XDG_CONFIG_HOME": str(config_home)}
    )

    assert result == home / "projects" / "demo"


def test_missing_config_falls_back_to_home(tmp_path: Path) -> None:
    home = tmp_path / "home"

    result = resolve_default_cwd({"HOME": str(home), "XDG_CONFIG_HOME": str(tmp_path)})

    assert result == home


def test_omp_environment_override_expands_home(tmp_path: Path) -> None:
    home = tmp_path / "home"

    result = resolve_omp_executable(
        {"HOME": str(home), "PATH": "", "OMPBAR_OMP": "~/custom/bin/omp"}
    )

    assert result == home / "custom" / "bin" / "omp"


def test_omp_uses_path_then_bun_fallback(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "omp"
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)

    assert (
        resolve_omp_executable({"HOME": str(home), "PATH": str(bin_dir)}) == executable
    )
    assert resolve_omp_executable({"HOME": str(home), "PATH": ""}) == (
        home / ".bun" / "bin" / "omp"
    )


def test_broken_config_falls_back_to_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    config = tmp_path / "config" / "ompbar" / "config.ini"
    config.parent.mkdir(parents=True)
    env = {"HOME": str(home), "XDG_CONFIG_HOME": str(tmp_path / "config")}
    for text in (
        "default_cwd = ~/no-section-header\n",
        "[ompbar]\ndefault_cwd = ~ompbar_no_such_user/x\n",
    ):
        config.write_text(text, encoding="utf-8")
        assert resolve_default_cwd(env) == home
