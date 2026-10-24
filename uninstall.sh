#!/bin/sh
set -eu

DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
APP_ID=org.ompbar.desktop
if [ -x "$HOME/.local/bin/ompbar" ]; then
    "$HOME/.local/bin/ompbar" quit >/dev/null 2>&1 || true
fi
if command -v gdbus >/dev/null 2>&1; then
    gdbus call --session --dest org.kde.kglobalaccel --object-path /kglobalaccel \
        --method org.kde.KGlobalAccel.unRegister \
        "['$APP_ID', '_launch', 'ompbar', 'ompbar']" >/dev/null 2>&1 || true
fi
if command -v kwriteconfig6 >/dev/null 2>&1; then
    kwriteconfig6 --file "$HOME/.config/kglobalshortcutsrc" \
        --group services --group "$APP_ID" --key _launch --delete --notify
fi
rm -f "$HOME/.local/bin/ompbar" \
    "$DATA_HOME/applications/$APP_ID" \
    "$HOME/.config/autostart/ompbar.desktop"
rm -rf "$DATA_HOME/ompbar"
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null
fi
printf 'Uninstalled ompbar.\n'
