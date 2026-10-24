import json
from typing import Any


class NDJSONParser:
    """Incrementally decode omp's newline-delimited JSON event stream."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> tuple[list[dict[str, Any]], list[str]]:
        self._buffer.extend(chunk)
        events: list[dict[str, Any]] = []
        errors: list[str] = []
        while True:
            end = self._buffer.find(b"\n")
            if end < 0:
                break
            line = bytes(self._buffer[:end])
            del self._buffer[: end + 1]
            self._decode(line, events, errors)
        return events, errors

    def finish(self) -> tuple[list[dict[str, Any]], list[str]]:
        """Decode a final unterminated record after the process exits."""
        line = bytes(self._buffer)
        self._buffer.clear()
        events: list[dict[str, Any]] = []
        errors: list[str] = []
        self._decode(line, events, errors)
        return events, errors

    @staticmethod
    def _decode(line: bytes, events: list[dict[str, Any]], errors: list[str]) -> None:
        if not line.strip():
            return
        try:
            value = json.loads(line)
        # ValueError also covers JSONDecodeError, UnicodeDecodeError and huge ints.
        except (ValueError, RecursionError) as exc:
            errors.append(f"Invalid omp event: {exc}")
            return
        if not isinstance(value, dict):
            errors.append("Invalid omp event: expected a JSON object")
            return
        events.append(value)
