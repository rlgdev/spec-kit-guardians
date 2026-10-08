"""Shared helpers: errors, the project root, text I/O that keeps line endings, version ranges, subprocesses."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

EXIT_OK = 0        # aligned / configured
EXIT_FINDINGS = 1  # verify found a FAIL (configure: a FAIL remains after it ran)
EXIT_ERROR = 2     # cannot run

SPECIFY_DIR = ".specify"
EXTENSIONS_YML = Path(SPECIFY_DIR) / "extensions.yml"
SIBLINGS = ("scopeguard", "archiguard", "auditguard")
GUARDIANS = SIBLINGS + ("guardians",)
NAMES = {"scopeguard": "scopeGuard", "archiguard": "archiGuard", "auditguard": "auditGuard", "guardians": "Guardians"}
PRESETS = {"archiguard": "archiguard-templates", "scopeguard": "scopeguard-templates"}


class GuardiansError(Exception):
    """A problem that stops the command (exit 2)."""


def find_root(start: Optional[Path] = None) -> Path:
    """The nearest directory, from `start` upwards, that contains .specify/."""
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / SPECIFY_DIR).is_dir():
            return candidate
    raise GuardiansError(f"no Spec Kit project found from {here} (no {SPECIFY_DIR}/ directory): "
                         "run from the project root or pass --root")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_raw(path: Path) -> str:
    """The text with its own line endings (no newline translation): what the line edits read, so a file that uses
    CRLF (Spec Kit writes .specify/extensions.yml with the platform's ending) is written back with CRLF."""
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 and keep the text's own line endings (newline='' disables translation)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def eol_of(text: str) -> str:
    """The line ending most lines of the text use: CRLF or LF (LF on a tie)."""
    return "\r\n" if 2 * text.count("\r\n") > text.count("\n") else "\n"


def split_lines(text: str) -> Tuple[List[str], str]:
    """Lines without their endings, plus the ending to put back (the one most lines use)."""
    return text.replace("\r\n", "\n").split("\n"), eol_of(text)


def join_lines(lines: Sequence[str], eol: str) -> str:
    return eol.join(lines)


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def strip_comment(line: str) -> str:
    """Drop a trailing `# comment` that is not inside quotes."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line


def version_tuple(version: str) -> Tuple[int, ...]:
    parts = []
    for piece in re.split(r"[.\-+]", str(version).strip().lstrip("v")):
        match = re.match(r"^\d+", piece)
        if not match:
            break
        parts.append(int(match.group(0)))
    return tuple(parts) or (0,)


def version_satisfies(version: str, constraint: str) -> bool:
    """The siblings' specifier subset: comma-separated clauses with >= <= == != > < ~=."""
    if not constraint:
        return True
    have = version_tuple(version)
    for clause in str(constraint).split(","):
        clause = clause.strip()
        match = re.match(r"^(>=|<=|==|!=|>|<|~=)?\s*([0-9][0-9A-Za-z.\-+]*)$", clause)
        if not match:
            continue
        op, target = match.group(1) or "==", version_tuple(match.group(2))
        width = max(len(have), len(target))
        a = have + (0,) * (width - len(have))
        b = target + (0,) * (width - len(target))
        keep = max(1, len(target) - 1)
        ok = {">=": a >= b, "<=": a <= b, "==": a == b, "!=": a != b, ">": a > b, "<": a < b,
              "~=": a >= b and a[:keep] == b[:keep]}[op]
        if not ok:
            return False
    return True


def run(cmd: Sequence[str], cwd: Path, timeout: int = 120) -> Tuple[int, str, str]:
    """Run a command and return (exit code, stdout, stderr); never raises for a non-zero exit."""
    try:
        proc = subprocess.run(list(cmd), cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except OSError as exc:
        return EXIT_ERROR, "", f"could not run {cmd[0]}: {exc}"
    except subprocess.TimeoutExpired:
        return EXIT_ERROR, "", f"timed out after {timeout}s: {' '.join(str(c) for c in cmd)}"
    return proc.returncode, proc.stdout, proc.stderr


def configure_stdout() -> None:
    """UTF-8 output with replacement on every platform (Windows consoles default to a legacy code page)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
