import shutil
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFileDialog

from .events import NDJSONParser
from .paths import resolve_default_cwd, resolve_omp_executable
from .prompts import parse_prompt

OMP = resolve_omp_executable()
DISCARDED = "Discarded by New conversation."


class BarController(QObject):
    answerTextChanged = Signal()
    statusTextChanged = Signal()
    elapsedTextChanged = Signal()
    cwdChanged = Signal()
    busyChanged = Signal()
    sessionIdChanged = Signal()
    errorTextChanged = Signal()
    turnFinished = Signal(str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self._cwd = resolve_default_cwd()
        self._answer_text = ""
        self._current_answer = ""
        self._status_text = "Ready"
        self._elapsed_text = ""
        self._busy = False
        self._session_id = ""
        self._error_text = ""
        self._window = None
        self._process: QProcess | None = None
        self._parser: NDJSONParser | None = None
        self._stderr = bytearray()
        self._turn_started = 0.0
        self._cancelled = False
        self._discard_current = False
        self._clock = QTimer(self)
        self._clock.setInterval(250)
        self._clock.timeout.connect(self._update_elapsed)

    @Property(str, notify=answerTextChanged)
    def answerText(self) -> str:
        return self._answer_text

    @Property(str, notify=statusTextChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=elapsedTextChanged)
    def elapsedText(self) -> str:
        return self._elapsed_text

    @Property(str, notify=cwdChanged)
    def cwd(self) -> str:
        return str(self._cwd)

    @Property(str, notify=cwdChanged)
    def cwdLabel(self) -> str:
        return self._cwd.name or str(self._cwd)

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=sessionIdChanged)
    def sessionId(self) -> str:
        return self._session_id

    @Property(str, notify=errorTextChanged)
    def errorText(self) -> str:
        return self._error_text

    def set_window(self, window) -> None:
        self._window = window

    def snapshot(self) -> dict[str, object]:
        return {
            "answer": self._answer_text,
            "session_id": self._session_id,
            "cwd": str(self._cwd),
            "busy": self._busy,
            "status": self._status_text,
            "error": self._error_text,
        }

    @Slot(str)
    def submit(self, raw_prompt: str) -> None:
        if self._busy:
            self._set_error("Wait for the current answer or stop it first.")
            return
        parsed = parse_prompt(raw_prompt, self._cwd)
        if parsed.error:
            self._set_error(parsed.error)
            return
        self._set_error("")
        changed_conversation = parsed.cwd != self._cwd and self._switch_cwd(parsed.cwd)
        if not parsed.cwd.is_dir():
            self._set_error(f"Folder not found: {parsed.cwd}")
            return
        if not OMP.is_file():
            self._set_error(f"omp was not found at {OMP}")
            return

        separator = "\n\n---\n\n" if self._answer_text else ""
        self._answer_text += f"{separator}**You:** {parsed.prompt}\n\n**omp:** "
        self._current_answer = ""
        self.answerTextChanged.emit()
        self._stderr.clear()
        self._parser = NDJSONParser()
        self._cancelled = False
        self._discard_current = False
        self._turn_started = time.monotonic()
        self._set_elapsed("0:00")
        self._set_status(
            f"New conversation in {parsed.cwd.name or parsed.cwd}"
            if changed_conversation
            else "Starting omp…"
        )
        self._set_busy(True)
        self._clock.start()

        process = QProcess(self)
        self._process = process
        process.setWorkingDirectory(str(parsed.cwd))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._process_finished)
        process.errorOccurred.connect(self._process_error)
        args = [
            "-p",
            "--mode",
            "json",
            "--approval-mode=write",
            "--allow-home",
            "--cwd",
            str(parsed.cwd),
        ]
        if self._session_id:
            args.extend(["-r", self._session_id])
        args.append("--")
        args.append(parsed.prompt)
        process.start(str(OMP), args)
        process.closeWriteChannel()

    @Slot()
    def cancel(self) -> None:
        if not self._process or not self._busy:
            return
        self._cancelled = True
        self._set_status("Stopping…")
        self._process.terminate()
        process = self._process
        QTimer.singleShot(1200, lambda: self._kill_if_running(process))

    @Slot()
    def newConversation(self) -> None:
        if self._busy:
            self._discard_current = True
            self.cancel()
        self._session_id = ""
        self.sessionIdChanged.emit()
        self._answer_text = ""
        self._current_answer = ""
        self.answerTextChanged.emit()
        self._cwd = resolve_default_cwd()
        self.cwdChanged.emit()
        self._set_error("")
        self._set_status("Ready")
        self._set_elapsed("")

    @Slot()
    def copyAnswer(self) -> None:
        if self._current_answer:
            QGuiApplication.clipboard().setText(self._current_answer)

    @Slot()
    def openInTerminal(self) -> None:
        if not self._session_id:
            self._set_error("Send a message first to create an omp session.")
            return
        self._set_error("")
        tern = shutil.which("tern")
        if tern is None:
            local_tern = Path.home() / ".local" / "bin" / "tern"
            if local_tern.is_file():
                tern = str(local_tern)
        if tern:
            program = tern
        else:
            program = shutil.which("konsole") or ""
            if not program:
                self._set_error("Neither tern nor konsole is available.")
                return
        args = ["-e", str(OMP), "-r", self._session_id]
        if not QProcess.startDetached(program, args, str(self._cwd)):
            self._set_error(f"Could not launch {program}.")

    @Slot()
    def chooseCwd(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            None, "Choose conversation folder", str(self._cwd)
        )
        if selected:
            self.setCwd(selected)

    @Slot(str)
    def setCwd(self, directory: str) -> None:
        path = Path(directory).expanduser()
        if not path.is_absolute():
            path = self._cwd / path
        path = path.resolve()
        if not path.is_dir():
            self._set_error(f"Folder not found: {path}")
            return
        if self._busy:
            self._set_error(
                "Wait for omp to finish or stop it before changing folders."
            )
            return
        if path == self._cwd:
            self._set_error("")
            return
        self._switch_cwd(path)

    def _switch_cwd(self, path: Path) -> bool:
        if path == self._cwd:
            return False
        has_conversation = bool(
            self._session_id or self._answer_text or self._current_answer
        )
        self._cwd = path
        if has_conversation:
            self._session_id = ""
            self._answer_text = ""
            self._current_answer = ""
        self._set_error("")
        self.cwdChanged.emit()
        if has_conversation:
            self.sessionIdChanged.emit()
            self.answerTextChanged.emit()
            self._set_elapsed("")
            self._set_status(f"New conversation in {path.name or path}")
        return has_conversation

    @Slot()
    def hide(self) -> None:
        if self._window is not None:
            self._window.hide()

    @Slot()
    def toggleWindow(self) -> None:
        if self._window is None:
            return
        if self._window.isVisible():
            self._window.hide()
        else:
            self._window.show()
            self._window.requestActivate()

    @Slot()
    def show(self) -> None:
        if self._window is not None:
            self._window.show()
            self._window.requestActivate()

    @Slot()
    def stop(self) -> None:
        self.cancel()

    def _read_stdout(self) -> None:
        if not self._process or not self._parser:
            return
        events, errors = self._parser.feed(bytes(self._process.readAllStandardOutput()))
        for error in errors:
            self._set_error(error)
        for event in events:
            self._handle_event(event)

    def _read_stderr(self) -> None:
        if self._process:
            self._stderr.extend(bytes(self._process.readAllStandardError()))

    def _handle_event(self, event: dict) -> None:
        if self._discard_current:
            return
        if event.get("type") == "session":
            session_id = event.get("id")
            if isinstance(session_id, str) and session_id != self._session_id:
                self._session_id = session_id
                self.sessionIdChanged.emit()
            return
        if event.get("type") == "tool_execution_start":
            name = str(event.get("toolName") or "tool")
            intent = str(event.get("intent") or "")
            self._set_status(f"{name} · {intent}" if intent else name)
            return
        if event.get("type") == "agent_start":
            self._set_status("Thinking…")
            return
        if event.get("type") == "message_update":
            update = event.get("assistantMessageEvent")
            if isinstance(update, dict):
                update_type = update.get("type")
                if update_type == "text_start":
                    if self._current_answer:
                        self._current_answer += "\n\n"
                        self._answer_text += "\n\n"
                        self.answerTextChanged.emit()
                    return
                if update_type == "text_delta":
                    delta = update.get("delta")
                    if isinstance(delta, str):
                        self._current_answer += delta
                        self._answer_text += delta
                        self.answerTextChanged.emit()
            return
        if event.get("type") == "agent_end":
            self._set_status("Finishing…")

    def _process_finished(self, exit_code: int, exit_status) -> None:
        process = self._process
        self._read_stdout()
        self._read_stderr()
        if self._parser:
            events, errors = self._parser.finish()
            for error in errors:
                if not self._discard_current:
                    self._set_error(error)
            for event in events:
                self._handle_event(event)
        stderr = bytes(self._stderr).decode("utf-8", errors="replace").strip()
        discarded = self._discard_current
        # Callers (ompbar ask) treat an empty error as success, so stopped turns need one.
        turn_error = ""
        if discarded:
            self._set_status("Ready")
            turn_error = DISCARDED
        elif self._cancelled:
            self._set_status("Stopped")
            turn_error = "Stopped before omp finished."
        elif exit_code != 0:
            self._set_error(stderr or f"omp exited with code {exit_code}.")
            self._set_status("Failed")
        else:
            # stderr on a clean exit is warnings only; the answer still succeeded.
            self._set_status("Complete")
            if not self._current_answer and not self._error_text:
                self._set_error("omp finished without a text response.")
        self._clock.stop()
        self._set_busy(False)
        self._set_elapsed("" if discarded else self._format_elapsed())
        self._process = None
        self._parser = None
        if process:
            process.deleteLater()
        self._discard_current = False
        self.turnFinished.emit(
            self._current_answer,
            self._session_id,
            turn_error or self._error_text,
        )

    def _process_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            discarded = self._discard_current
            process = self._process
            message = process.errorString() if process else "Could not start omp."
            if not discarded:
                self._set_error(message)
                self._set_status("Failed")
            else:
                self._set_status("Ready")
            self._clock.stop()
            self._set_busy(False)
            self._set_elapsed("" if discarded else self._format_elapsed())
            self._process = None
            self._parser = None
            self._discard_current = False
            if process:
                process.deleteLater()
            self.turnFinished.emit(
                "",
                self._session_id,
                DISCARDED if discarded else message,
            )

    def _kill_if_running(self, process: QProcess) -> None:
        # Only the turn that was stopped; a finished one may already be deleted.
        if (
            process is self._process
            and process.state() != QProcess.ProcessState.NotRunning
        ):
            process.kill()

    def _update_elapsed(self) -> None:
        self._set_elapsed(self._format_elapsed())

    def _format_elapsed(self) -> str:
        seconds = max(0, int(time.monotonic() - self._turn_started))
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _set_busy(self, value: bool) -> None:
        if self._busy != value:
            self._busy = value
            self.busyChanged.emit()

    def _set_status(self, value: str) -> None:
        if self._status_text != value:
            self._status_text = value
            self.statusTextChanged.emit()

    def _set_elapsed(self, value: str) -> None:
        if self._elapsed_text != value:
            self._elapsed_text = value
            self.elapsedTextChanged.emit()

    def _set_error(self, value: str) -> None:
        if self._error_text != value:
            self._error_text = value
            self.errorTextChanged.emit()
