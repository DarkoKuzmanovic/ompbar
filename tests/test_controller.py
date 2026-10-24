import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QGuiApplication

from ompbar import controller as controller_module

# Stub omp: behaviour is picked by the prompt (the last argument).
STUB = f"""#!{sys.executable}
import json, sys, time
prompt = sys.argv[-1]
def say(text):
    event = {{"type": "message_update",
             "assistantMessageEvent": {{"type": "text_delta", "delta": text}}}}
    print(json.dumps(event), flush=True)
if prompt == "slow":
    say("partial")
    time.sleep(10)
elif prompt == "late":
    time.sleep(1.5)
    say("ok")
elif prompt == "warn":
    say("ok")
    print("omp: warning: deprecated config key", file=sys.stderr)
else:
    say("ok")
"""


@pytest.fixture
def bar(tmp_path, monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    omp = tmp_path / "omp"
    omp.write_text(STUB)
    omp.chmod(0o755)
    monkeypatch.setattr(controller_module, "OMP", omp)
    monkeypatch.setenv("OMPBAR_CWD", str(tmp_path))
    return controller_module.BarController()


def run_turn(bar, action, timeout_ms=8000):
    """Run action, then spin the event loop until turnFinished; return its args."""
    result = []
    loop = QEventLoop()

    def done(*args):
        result.append(args)
        loop.quit()

    bar.turnFinished.connect(done)
    QTimer.singleShot(timeout_ms, loop.quit)
    action()
    if not result:
        loop.exec()
    bar.turnFinished.disconnect(done)
    assert result, "turn did not finish"
    return result[0]


def test_stderr_on_successful_turn_is_not_an_error(bar):
    answer, _, error = run_turn(bar, lambda: bar.submit("warn"))
    assert (answer, error) == ("ok", "")
    assert bar.errorText == ""


def test_cancelled_turn_reports_an_error(bar):
    def start_and_stop():
        bar.submit("slow")
        QTimer.singleShot(300, bar.cancel)

    _, _, error = run_turn(bar, start_and_stop)
    assert error


def test_discarded_turn_reports_an_error(bar):
    def start_and_reset():
        bar.submit("slow")
        QTimer.singleShot(300, bar.newConversation)

    _, _, error = run_turn(bar, start_and_reset)
    assert error


def test_stop_timer_does_not_kill_the_next_turn(bar):
    def start_and_stop():
        bar.submit("slow")
        QTimer.singleShot(300, bar.cancel)

    run_turn(bar, start_and_stop)
    # The stopped turn exits at once; the next one must outlive the 1.2 s kill timer.
    answer, _, error = run_turn(bar, lambda: bar.submit("late"))
    assert (answer, error) == ("ok", "")
