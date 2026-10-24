import re
from dataclasses import dataclass
from pathlib import Path

DIRECTORY_PREFIX = re.compile(r"^@(\S+)(?:\s+(.*))?$", re.DOTALL)


@dataclass(frozen=True)
class ParsedPrompt:
    prompt: str
    cwd: Path
    error: str = ""


def parse_prompt(text: str, cwd: Path) -> ParsedPrompt:
    """Resolve an optional leading @directory token into the turn's working folder.

    Relative folders resolve against ``cwd``; a missing folder or an empty
    question after the token comes back as ``error``.
    """
    value = text.strip()
    if not value:
        return ParsedPrompt("", cwd, "Enter a question.")

    match = DIRECTORY_PREFIX.fullmatch(value)
    if match is None:
        return ParsedPrompt(value, cwd)

    question = (match.group(2) or "").strip()
    try:
        requested = Path(match.group(1)).expanduser()
    except RuntimeError:  # ~name for a user that does not exist
        return ParsedPrompt(question, cwd, f"Folder not found: {match.group(1)}")
    directory = requested if requested.is_absolute() else cwd / requested
    directory = directory.resolve()
    if not directory.is_dir():
        return ParsedPrompt(question, cwd, f"Folder not found: {directory}")
    if not question:
        return ParsedPrompt("", directory, "Add a question after the folder token.")
    return ParsedPrompt(question, directory)
