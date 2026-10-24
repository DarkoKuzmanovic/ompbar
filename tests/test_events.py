from ompbar.events import NDJSONParser


def test_parser_handles_chunk_boundaries_and_unicode() -> None:
    parser = NDJSONParser()
    first, errors = parser.feed(
        b'{"type":"session","id":"one"}\n{"type":"message_update","delta":"caf'
    )
    assert first == [{"type": "session", "id": "one"}]
    assert errors == []

    second, errors = parser.feed("é".encode() + b'"}\n')
    assert second == [{"type": "message_update", "delta": "café"}]
    assert errors == []


def test_parser_reports_bad_lines_and_keeps_reading() -> None:
    parser = NDJSONParser()
    events, errors = parser.feed(b'{bad}\n{"type":"agent_end"}\n')
    assert events == [{"type": "agent_end"}]
    assert len(errors) == 1
    assert errors[0].startswith("Invalid omp event:")


def test_parser_flushes_unterminated_final_record() -> None:
    parser = NDJSONParser()
    assert parser.feed(b'{"type":"session"}') == ([], [])
    assert parser.finish() == ([{"type": "session"}], [])


def test_parser_reports_huge_numbers_and_deep_nesting() -> None:
    parser = NDJSONParser()
    huge = b'{"n":' + b"9" * 5000 + b"}"
    deep = b"[" * 100_000 + b"]" * 100_000
    events, errors = parser.feed(huge + b"\n" + deep + b'\n{"type":"agent_end"}\n')
    assert events == [{"type": "agent_end"}]
    assert len(errors) == 2
