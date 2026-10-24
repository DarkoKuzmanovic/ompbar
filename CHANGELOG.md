# Changelog

All notable changes to ompbar are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Stopping an answer no longer kills the next question if it starts within 1.2 seconds.
- `ompbar ask` now fails when the turn is stopped or discarded by New conversation, instead of returning a partial or empty answer as success.
- Warnings omp prints on stderr no longer turn a successful answer into an error.
- A rejected question (for example a missing `@folder`) stays in the prompt box instead of being erased.
- Oversized numbers or deeply nested JSON in omp output or control requests are reported as invalid instead of crashing the reader.
- A malformed `config.ini` or an unknown `~user` folder falls back to the home folder instead of stopping the bar from starting.
- An `@~unknownuser` folder token or folder choice shows "Folder not found" instead of raising an error.
- Continue in terminal now reports when the terminal fails to launch.
- `install.sh` checks PySide6 in `/usr/bin/python3`, the interpreter the launcher actually runs.
- The desktop and autostart entries pass `desktop-file-validate` and work when the home folder path contains spaces.
- The layer-shell top margin is applied; `Qt.margins()` does not exist in QML and was silently dropped.

## [0.1.0] - 2026-10-24

### Added

- Resident KDE Plasma 6 Wayland quick-question bar for the `omp` coding agent.
- Session follow-ups, folder switching, terminal continuation, tool-approval safeguards, and KDE shortcut installation.
- Qt-free unit tests, Ruff linting and formatting, CI, MIT license, and project documentation.
