import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from .controller import BarController

SERVER_NAME = f"ompbar-{os.getuid()}"
LOCK_PATH = str(Path(tempfile.gettempdir()) / f"ompbar-{os.getuid()}.lock")


def _write_response(socket: QLocalSocket, payload: dict) -> None:
    socket.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    socket.flush()


class ControlServer:
    def __init__(self, controller: BarController) -> None:
        self.controller = controller
        self.server = QLocalServer()
        self.buffers: dict[QLocalSocket, bytearray] = {}
        self.waiting_asks: list[QLocalSocket] = []
        self.server.newConnection.connect(self._accept)
        self.controller.turnFinished.connect(self._finish_asks)

    def listen(self) -> bool:
        if self.server.listen(SERVER_NAME):
            return True
        QLocalServer.removeServer(SERVER_NAME)
        return self.server.listen(SERVER_NAME)

    def _accept(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            self.buffers[socket] = bytearray()
            socket.readyRead.connect(lambda sock=socket: self._read(sock))
            socket.disconnected.connect(lambda sock=socket: self._discard(sock))

    def _read(self, socket: QLocalSocket) -> None:
        buffer = self.buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        while True:
            end = buffer.find(b"\n")
            if end < 0:
                return
            line = bytes(buffer[:end])
            del buffer[: end + 1]
            try:
                request = json.loads(line)
            except (ValueError, RecursionError):
                _write_response(socket, {"ok": False, "error": "Invalid request."})
                continue
            self._handle(socket, request)

    def _handle(self, socket: QLocalSocket, request: object) -> None:
        if not isinstance(request, dict):
            _write_response(socket, {"ok": False, "error": "Invalid request."})
            return
        command = request.get("command")
        if command == "toggle":
            self.controller.toggleWindow()
            _write_response(socket, {"ok": True, "visible": self._visible()})
        elif command == "show":
            self.controller.show()
            _write_response(socket, {"ok": True, "visible": self._visible()})
        elif command == "status":
            _write_response(
                socket,
                {"ok": True, "visible": self._visible(), **self.controller.snapshot()},
            )
        elif command == "new":
            self.controller.newConversation()
            _write_response(socket, {"ok": True})
        elif command == "open-terminal":
            self.controller.openInTerminal()
            error = self.controller.errorText
            if error:
                _write_response(socket, {"ok": False, "error": error})
            else:
                _write_response(socket, {"ok": True})
        elif command == "quit":
            _write_response(socket, {"ok": True})
            QTimer.singleShot(0, QApplication.quit)
        elif command == "ask":
            if self.controller.busy:
                _write_response(
                    socket, {"ok": False, "error": "ompbar is already answering."}
                )
                return
            prompt = request.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                _write_response(socket, {"ok": False, "error": "A prompt is required."})
                return
            self.waiting_asks.append(socket)
            self.controller.show()
            self.controller.submit(prompt)
            if not self.controller.busy:
                self.waiting_asks.remove(socket)
                _write_response(
                    socket,
                    {
                        "ok": False,
                        "error": self.controller.errorText
                        or "The prompt could not be started.",
                        **self.controller.snapshot(),
                    },
                )
        else:
            _write_response(socket, {"ok": False, "error": "Unknown command."})

    def _finish_asks(self, answer: str, session_id: str, error: str) -> None:
        for socket in self.waiting_asks:
            if socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
                _write_response(
                    socket,
                    {
                        "ok": not bool(error),
                        "answer": answer,
                        "session_id": session_id,
                        "cwd": self.controller.cwd,
                        "error": error,
                    },
                )
        self.waiting_asks.clear()

    def _visible(self) -> bool:
        window = self.controller._window
        return bool(window and window.isVisible())

    def _discard(self, socket: QLocalSocket) -> None:
        self.buffers.pop(socket, None)
        if socket in self.waiting_asks:
            self.waiting_asks.remove(socket)
        socket.deleteLater()


def _send_request(request: dict, timeout_ms: int = 5000) -> dict | None:
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(300):
        return None
    socket.write((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
    if not socket.waitForBytesWritten(3000):
        return None
    deadline = time.monotonic() + timeout_ms / 1000
    response = bytearray()
    while time.monotonic() < deadline:
        remaining = max(1, int((deadline - time.monotonic()) * 1000))
        if not socket.waitForReadyRead(remaining):
            if socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
                break
            continue
        response.extend(bytes(socket.readAll()))
        end = response.find(b"\n")
        if end >= 0:
            try:
                return json.loads(response[:end])
            except (ValueError, RecursionError):
                return {"ok": False, "error": "ompbar returned an invalid response."}
    if socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
        return {"ok": False, "error": "ompbar disconnected before replying."}
    return {"ok": False, "error": "Timed out waiting for ompbar."}


def _start_daemon() -> None:
    lock = QLockFile(LOCK_PATH)
    lock.setStaleLockTime(30000)
    if not lock.tryLock(0):
        return
    lock.unlock()
    subprocess.Popen(
        [sys.executable, "-m", "ompbar", "--daemon-process"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def request(command: str, prompt: str = "", *, wait_ms: int = 900000) -> dict:
    response = _send_request({"command": command, "prompt": prompt}, wait_ms)
    if response is not None:
        return response
    _start_daemon()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = _send_request({"command": command, "prompt": prompt}, wait_ms)
        if response is not None:
            return response
        time.sleep(0.08)
    return {"ok": False, "error": "Could not start the ompbar daemon."}


def run_daemon() -> int:
    lock = QLockFile(LOCK_PATH)
    lock.setStaleLockTime(30000)
    if not lock.tryLock(0):
        return 0

    app = QApplication(sys.argv[:1])
    app.setApplicationName("ompbar")
    app.setOrganizationName("ompbar")
    app.setQuitOnLastWindowClosed(False)
    controller = BarController()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bar", controller)
    qml = Path(__file__).with_name("qml") / "Main.qml"
    engine.load(str(qml))
    roots = engine.rootObjects()
    if not roots:
        return 1
    window = roots[0]
    controller.set_window(window)
    window.setProperty("visible", False)
    server = ControlServer(controller)
    if not server.listen():
        return 1
    app.aboutToQuit.connect(server.server.close)
    return app.exec()
