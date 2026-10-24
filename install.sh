#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
APP_DIR=$DATA_HOME/ompbar
BIN_DIR=$HOME/.local/bin
APP_ID=org.ompbar.desktop
SHORTCUT=Meta+Alt+Space
SHORTCUT_KEY=402653216 # Qt::META | Qt::ALT | Qt::Key_Space

for tool in python3 kwriteconfig6 kreadconfig6 qdbus6 gdbus kbuildsycoca6; do
    command -v "$tool" >/dev/null 2>&1 || {
        printf 'Required command not found: %s\n' "$tool" >&2
        exit 1
    }
done
python3 -c 'import PySide6' || {
    printf 'System Python PySide6 is required.\n' >&2
    exit 1
}

current=$(kreadconfig6 --file "$HOME/.config/kglobalshortcutsrc" \
    --group services --group "$APP_ID" --key _launch)
if [ "$current" != "$SHORTCUT" ]; then
    available=$(qdbus6 org.kde.kglobalaccel /kglobalaccel \
        org.kde.KGlobalAccel.isGlobalShortcutAvailable \
        "$SHORTCUT_KEY" "$APP_ID")
    if [ "$available" != true ]; then
        printf '%s is already in use; installer left KDE shortcut settings untouched.\n' "$SHORTCUT" >&2
        exit 1
    fi
fi

install -d "$APP_DIR/src/ompbar" "$BIN_DIR" \
    "$DATA_HOME/applications" "$HOME/.config/autostart"
cp -a "$ROOT/src/ompbar/." "$APP_DIR/src/ompbar/"
install -m 755 "$ROOT/bin/ompbar" "$BIN_DIR/ompbar"
install -m 644 "$ROOT/data/org.ompbar.desktop" "$DATA_HOME/applications/$APP_ID"
install -m 644 "$ROOT/data/ompbar-autostart.desktop" \
    "$HOME/.config/autostart/ompbar.desktop"
kbuildsycoca6 --desktopfile "$APP_ID"

kwriteconfig6 --file "$HOME/.config/kglobalshortcutsrc" \
    --group services --group "$APP_ID" --key _launch "$SHORTCUT" --notify
gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
    --method org.kde.KGlobalAccel.doRegister \
    "['$APP_ID', '_launch', 'ompbar', 'ompbar']" >/dev/null
gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
    --method org.kde.KGlobalAccel.setShortcut \
    "['$APP_ID', '_launch', 'ompbar', 'ompbar']" "[$SHORTCUT_KEY]" 2 >/dev/null

printf 'Installed ompbar. Global shortcut: %s\n' "$SHORTCUT"
printf 'Run %s toggle to show it now.\n' "$BIN_DIR/ompbar"
