import QtQuick
import QtQuick.Window
import QtQuick.Controls as QQC2
import QtQuick.Effects
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.layershell 1.0 as LayerShell

// ompbar quick-question overlay.
//
// A frameless layer-shell surface pinned to the top-centre of the active
// screen. It collapses to a single prompt line until there is something to
// show and grows to the full answer view as soon as a question is running.
// Visibility is driven by the backend (`bar`); this file only reacts to it.
Window {
    id: root

    // ---- geometry ---------------------------------------------------------
    readonly property int cardMaxWidth: 900
    readonly property int cardMaxHeight: Math.max(
        1, Math.floor((root.screen ? root.screen.height : 1000) * 0.6) - 2 * shadowPad
    )
    readonly property int topGap: 34            // visible gap to the screen edge
    readonly property int shadowPad: 24         // room around the card for its shadow
    readonly property int gutter: Kirigami.Units.largeSpacing * 2
    readonly property real cornerRadius: Kirigami.Units.cornerRadius * 2

    // ---- state ------------------------------------------------------------
    readonly property bool expanded: bar.answerText !== "" || bar.busy || bar.errorText !== ""
    property bool copied: false

    readonly property int cardWidth: Math.min(cardMaxWidth, (root.screen ? root.screen.width : cardMaxWidth) - 2 * shadowPad - Kirigami.Units.gridUnit * 2)
    readonly property int cardHeight: Math.min(cardMaxHeight, Math.ceil(content.implicitHeight))

    title: "ompbar"
    width: cardWidth + 2 * shadowPad
    height: cardHeight + 2 * shadowPad
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint

    // ---- layer-shell placement -------------------------------------------
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop
    LayerShell.Window.margins: Qt.margins(0, Math.max(0, root.topGap - root.shadowPad), 0, 0)
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.wantsToBeOnActiveScreen: true
    LayerShell.Window.activateOnShow: true
    LayerShell.Window.keyboardInteractivity: root.visible
        ? LayerShell.Window.KeyboardInteractivityOnDemand
        : LayerShell.Window.KeyboardInteractivityNone

    // ---- actions ----------------------------------------------------------
    function focusPrompt() {
        prompt.forceActiveFocus(Qt.ActiveWindowFocusReason)
    }

    function sendPrompt() {
        const question = prompt.text.trim()
        if (question === "" || bar.busy)
            return
        flick.follow = true
        bar.submit(question)
        prompt.clear()
    }

    function stopOrClose() {
        if (bar.busy)
            bar.cancel()
        else
            bar.hide()
    }

    function newConversation() {
        bar.newConversation()
        prompt.clear()
        flick.follow = true
        focusPrompt()
    }

    function copyAnswer() {
        if (bar.answerText === "")
            return
        bar.copyAnswer()
        copied = true
        copiedTimer.restart()
    }

    onVisibleChanged: {
        if (visible) {
            requestActivate()
            Qt.callLater(focusPrompt)
        }
    }
    onActiveChanged: {
        if (active)
            focusPrompt()
    }

    Timer {
        id: copiedTimer
        interval: 1500
        onTriggered: root.copied = false
    }

    Connections {
        target: bar
        function onBusyChanged() {
            if (bar.busy)
                flick.follow = true
            else if (root.active)
                root.focusPrompt()
        }
    }

    Shortcut {
        sequences: ["Escape"]
        onActivated: root.stopOrClose()
    }
    Shortcut {
        sequences: ["Ctrl+N"]
        onActivated: root.newConversation()
    }
    Shortcut {
        sequences: ["Ctrl+Shift+C"]
        onActivated: root.copyAnswer()
    }

    // ---- small building blocks -------------------------------------------
    component ActionButton: QQC2.ToolButton {
        property string tip
        display: QQC2.AbstractButton.IconOnly
        QQC2.ToolTip.visible: hovered || visualFocus
        QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
        QQC2.ToolTip.text: tip
        Accessible.name: tip
    }

    // ---- window chrome ----------------------------------------------------
    Rectangle {
        id: shadowCaster
        anchors.fill: card
        radius: card.radius
        color: card.color
        visible: false
    }

    MultiEffect {
        anchors.fill: shadowCaster
        source: shadowCaster
        shadowEnabled: true
        shadowColor: Qt.rgba(0, 0, 0, 1)
        shadowOpacity: 0.32
        shadowBlur: 0.7
        shadowVerticalOffset: 5
    }

    Rectangle {
        id: card

        anchors.fill: parent
        anchors.margins: root.shadowPad

        Kirigami.Theme.colorSet: Kirigami.Theme.Window
        Kirigami.Theme.inherit: false

        radius: root.cornerRadius
        color: Kirigami.Theme.backgroundColor
        border.width: 1
        border.color: dropArea.containsDrag
            ? Kirigami.Theme.highlightColor
            : Kirigami.ColorUtils.linearInterpolation(Kirigami.Theme.backgroundColor, Kirigami.Theme.textColor, 0.22)

        ColumnLayout {
            id: content

            anchors.fill: parent
            spacing: 0

            // Prompt -------------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: root.gutter - Kirigami.Units.smallSpacing
                Layout.leftMargin: root.gutter
                Layout.rightMargin: root.gutter
                spacing: Kirigami.Units.largeSpacing

                QQC2.ScrollView {
                    id: promptScroll

                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(prompt.implicitHeight, Kirigami.Units.gridUnit * 9)
                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

                    QQC2.TextArea {
                        id: prompt

                        leftPadding: 0
                        rightPadding: 0
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        placeholderText: "Ask omp anything…"
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.25
                        background: null
                        Accessible.name: "Prompt"

                        Keys.onPressed: event => {
                            const isEnter = event.key === Qt.Key_Return || event.key === Qt.Key_Enter
                            if (!isEnter || prompt.inputMethodComposing)
                                return
                            if (event.modifiers & Qt.ShiftModifier) {
                                // Plain newline (TextArea would insert U+2028 here).
                                if (prompt.selectionStart !== prompt.selectionEnd)
                                    prompt.remove(prompt.selectionStart, prompt.selectionEnd)
                                prompt.insert(prompt.cursorPosition, "\n")
                            } else {
                                root.sendPrompt()
                            }
                            event.accepted = true
                        }
                    }
                }

                QQC2.Button {
                    id: sendButton

                    readonly property bool stopMode: bar.busy

                    Layout.alignment: Qt.AlignBottom
                    Layout.minimumWidth: Kirigami.Units.gridUnit * 5.5
                    icon.name: stopMode ? "media-playback-stop" : "document-send"
                    text: stopMode ? "Stop" : "Send"
                    highlighted: !stopMode
                    enabled: stopMode || prompt.text.trim() !== ""
                    onClicked: stopMode ? bar.cancel() : root.sendPrompt()

                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    QQC2.ToolTip.text: stopMode ? "Stop answering (Esc)" : "Send (Enter)"
                }
            }

            // Folder chip · status · actions ---------------------------------
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.leftMargin: root.gutter
                Layout.rightMargin: root.gutter - Kirigami.Units.smallSpacing
                Layout.bottomMargin: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.smallSpacing

                QQC2.AbstractButton {
                    id: chip

                    Layout.maximumWidth: Kirigami.Units.gridUnit * 18
                    implicitHeight: Kirigami.Units.gridUnit * 1.7
                    implicitWidth: chipRow.implicitWidth + Kirigami.Units.largeSpacing * 2
                    enabled: !bar.busy
                    hoverEnabled: true
                    onClicked: bar.chooseCwd()

                    Accessible.name: "Working folder: " + bar.cwd
                    QQC2.ToolTip.visible: hovered || visualFocus
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                    QQC2.ToolTip.text: bar.cwd + "\nClick to choose a folder, or drop one here"

                    background: Rectangle {
                        radius: height / 2
                        color: chip.down
                            ? Qt.alpha(Kirigami.Theme.highlightColor, 0.28)
                            : chip.hovered
                                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.16)
                                : Qt.alpha(Kirigami.Theme.textColor, 0.07)
                        border.width: chip.visualFocus || dropArea.containsDrag ? 1 : 0
                        border.color: Kirigami.Theme.highlightColor
                        Behavior on color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
                    }

                    contentItem: RowLayout {
                        id: chipRow
                        spacing: Kirigami.Units.smallSpacing

                        Kirigami.Icon {
                            source: "folder"
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                            Layout.leftMargin: Kirigami.Units.smallSpacing
                        }
                        QQC2.Label {
                            Layout.fillWidth: true
                            text: bar.cwdLabel
                            elide: Text.ElideMiddle
                            color: Kirigami.Theme.textColor
                        }
                    }
                }

                QQC2.BusyIndicator {
                    Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                    Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                    Layout.leftMargin: Kirigami.Units.smallSpacing
                    running: bar.busy
                    visible: bar.busy
                }

                QQC2.Label {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.smallSpacing
                    text: bar.statusText !== ""
                        ? bar.statusText
                        : (root.expanded ? "" : "Enter to send  ·  Shift+Enter for a new line  ·  Esc to close")
                    elide: Text.ElideRight
                    maximumLineCount: 1
                    font: Kirigami.Theme.smallFont
                    color: Kirigami.Theme.textColor
                    opacity: 0.7
                }

                QQC2.Label {
                    visible: bar.elapsedText !== ""
                    text: bar.elapsedText
                    font: Kirigami.Theme.smallFont
                    color: Kirigami.Theme.textColor
                    opacity: 0.7
                    Layout.rightMargin: Kirigami.Units.smallSpacing
                }

                ActionButton {
                    icon.name: "document-new"
                    tip: "New conversation · Ctrl+N"
                    onClicked: root.newConversation()
                }
                ActionButton {
                    icon.name: root.copied ? "dialog-ok-apply" : "edit-copy"
                    tip: "Copy answer · Ctrl+Shift+C"
                    enabled: bar.answerText !== ""
                    onClicked: root.copyAnswer()
                }
                ActionButton {
                    icon.name: "utilities-terminal"
                    tip: "Continue in terminal"
                    enabled: bar.sessionId !== ""
                    onClicked: bar.openInTerminal()
                }
            }

            // Error --------------------------------------------------------
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                Layout.leftMargin: root.gutter
                Layout.rightMargin: root.gutter
                Layout.bottomMargin: Kirigami.Units.largeSpacing
                type: Kirigami.MessageType.Error
                text: bar.errorText
                visible: bar.errorText !== ""
                showCloseButton: false
            }

            Kirigami.Separator {
                Layout.fillWidth: true
                visible: root.expanded
            }

            // Answer -------------------------------------------------------
            Item {
                id: answerArea

                visible: root.expanded
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 0
                implicitHeight: visible ? Math.min(flick.contentHeight, root.cardMaxHeight) : 0
                Layout.preferredHeight: implicitHeight
                Layout.bottomMargin: Kirigami.Units.smallSpacing

                QQC2.ScrollView {
                    anchors.fill: parent
                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

                    Flickable {
                        id: flick

                        // True while the view should stick to the newest streamed text.
                        property bool follow: true
                        property bool autoScrolling: false

                        function scrollToEnd() {
                            autoScrolling = true
                            contentY = Math.max(0, contentHeight - height)
                            autoScrolling = false
                        }

                        contentWidth: width
                        contentHeight: column.implicitHeight + 2 * root.gutter
                        boundsBehavior: Flickable.StopAtBounds
                        clip: true

                        onContentHeightChanged: {
                            if (follow)
                                scrollToEnd()
                        }
                        onHeightChanged: {
                            if (follow)
                                scrollToEnd()
                        }
                        onContentYChanged: {
                            if (!autoScrolling)
                                follow = contentY >= contentHeight - height - 2
                        }

                        ColumnLayout {
                            id: column

                            x: root.gutter
                            y: root.gutter
                            width: flick.width - 2 * root.gutter
                            spacing: Kirigami.Units.largeSpacing


                            QQC2.Label {
                                visible: bar.busy && bar.answerText === ""
                                Layout.fillWidth: true
                                text: "Waiting for omp…"
                                color: Kirigami.Theme.textColor
                                opacity: 0.6
                            }

                            TextEdit {
                                id: answer

                                visible: bar.answerText !== ""
                                Layout.fillWidth: true
                                readOnly: true
                                selectByMouse: true
                                text: bar.answerText
                                textFormat: TextEdit.MarkdownText
                                wrapMode: TextEdit.Wrap
                                font: Kirigami.Theme.defaultFont
                                color: Kirigami.Theme.textColor
                                selectionColor: Kirigami.Theme.highlightColor
                                selectedTextColor: Kirigami.Theme.highlightedTextColor
                                onLinkActivated: link => Qt.openUrlExternally(link)
                                Accessible.name: "Answer"
                                Accessible.role: Accessible.StaticText

                                HoverHandler {
                                    cursorShape: answer.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.IBeamCursor
                                }
                            }
                        }
                    }
                }

                // Shown when the user has scrolled away from a streaming answer.
                QQC2.Button {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: Kirigami.Units.largeSpacing
                    visible: bar.busy && !flick.follow
                    icon.name: "go-down"
                    text: "Latest"
                    onClicked: {
                        flick.follow = true
                        flick.scrollToEnd()
                    }
                }
            }
        }

        // Dropping a folder onto the bar sets the working directory.
        DropArea {
            id: dropArea

            anchors.fill: parent
            onDropped: drop => {
                if (!drop.hasUrls || drop.urls.length === 0)
                    return
                const url = drop.urls[0].toString()
                if (!url.startsWith("file://"))
                    return
                bar.setCwd(decodeURIComponent(url.substring(7)))
                drop.accept()
                root.focusPrompt()
            }
        }
    }
}
