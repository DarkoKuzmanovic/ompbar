from pathlib import Path

from ompbar.prompts import parse_prompt


def test_prompt_without_directory_keeps_conversation_cwd(tmp_path: Path) -> None:
    result = parse_prompt("  Explain this change  ", tmp_path)
    assert result.prompt == "Explain this change"
    assert result.cwd == tmp_path
    assert result.error == ""


def test_prompt_expands_home_and_accepts_leading_directory(tmp_path: Path) -> None:
    result = parse_prompt(f"@{tmp_path} inspect the source", tmp_path)
    assert result.prompt == "inspect the source"
    assert result.cwd == tmp_path.resolve()
    assert result.error == ""


def test_prompt_resolves_relative_directory_from_conversation_cwd(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "project"
    folder.mkdir()
    result = parse_prompt("@project explain", tmp_path)
    assert result.prompt == "explain"
    assert result.cwd == folder.resolve()


def test_missing_directory_is_reported_without_changing_cwd(tmp_path: Path) -> None:
    result = parse_prompt("@missing inspect", tmp_path)
    assert result.prompt == "inspect"
    assert result.cwd == tmp_path
    assert result.error == f"Folder not found: {tmp_path / 'missing'}"


def test_directory_token_requires_a_question(tmp_path: Path) -> None:
    result = parse_prompt(f"@{tmp_path}", tmp_path)
    assert result.prompt == ""
    assert result.cwd == tmp_path.resolve()
    assert result.error == "Add a question after the folder token."


def test_empty_prompt_is_rejected(tmp_path: Path) -> None:
    result = parse_prompt("   ", tmp_path)
    assert result.prompt == ""
    assert result.cwd == tmp_path
    assert result.error == "Enter a question."


def test_unknown_user_home_is_an_inline_error(tmp_path: Path) -> None:
    result = parse_prompt("@~ompbar_no_such_user question", tmp_path)
    assert result.cwd == tmp_path
    assert result.error.startswith("Folder not found:")
