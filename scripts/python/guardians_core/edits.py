"""The three line edits Guardians makes. Each keeps every other line, comment and line ending of the file.

- set_top_level_scalar : `integration: inline` -> `integration: embedded` (scopeGuard's config)
- append_to_list       : add paths to `edit_guard.always_readonly` (archiGuard's config)
- edit_hook_entries    : set a field (`priority`) on hook entries of .specify/extensions.yml
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .common import join_lines, split_lines, strip_comment


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _scalar(value: str) -> str:
    return value.strip().strip("'\"")


def _comment_tail(line: str) -> str:
    """The `  # comment` part of a line (with its leading spaces), or ''."""
    content = strip_comment(line)
    return line[len(content):] if len(content) < len(line) else ""


# --------------------------------------------------------------------------- #
# 1. a top-level scalar                                                         #
# --------------------------------------------------------------------------- #

def set_top_level_scalar(text: str, key: str, value: str) -> Tuple[str, Optional[str], bool]:
    """Set `key: value` at indent 0. Returns (text, previous value or None when absent, changed)."""
    lines, eol = split_lines(text)
    for i, line in enumerate(lines):
        if not line.startswith(key + ":") or _indent(line):
            continue
        content = strip_comment(line)
        old = _scalar(content[len(key) + 1:])
        if old == value:
            return text, old, False
        lines[i] = f"{key}: {value}{_comment_tail(line)}"
        return join_lines(lines, eol), old, True
    while lines and lines[-1].strip() == "":
        lines.pop()
    lines += [f"{key}: {value}", ""]
    return join_lines(lines, eol), None, True


# --------------------------------------------------------------------------- #
# 2. items of a list one level inside a top-level section                       #
# --------------------------------------------------------------------------- #

def _section_bounds(lines: List[str], section: str) -> Tuple[Optional[int], int]:
    """(index of `section:` at indent 0, index of the first line after the section)."""
    start = None
    for i, line in enumerate(lines):
        if _indent(line) == 0 and re.match(rf"^{re.escape(section)}:\s*(#.*)?$", line):
            start = i
            break
    if start is None:
        return None, len(lines)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if stripped and not stripped.startswith("#") and _indent(lines[j]) == 0:
            end = j
            break
    return start, end


def _quote(item: str) -> str:
    return json.dumps(item, ensure_ascii=False)


def append_to_list(text: str, section: str, key: str, items: List[str]) -> Tuple[str, List[str]]:
    """Append `items` to the list at `section.key`. The caller passes only the items that are missing.

    Handles a flow list (`key: [a, b]`, also spanning lines) and a block list (`- a` lines). Creates the
    key or the section when absent. Returns (text, items added).
    """
    if not items:
        return text, []
    lines, eol = split_lines(text)
    start, end = _section_bounds(lines, section)
    if start is None:
        while lines and lines[-1].strip() == "":
            lines.pop()
        lines += ["", f"{section}:", f"  {key}: [{', '.join(_quote(i) for i in items)}]", ""]
        return join_lines(lines, eol), list(items)

    key_index = None
    child_indent = 2
    for j in range(start + 1, end):
        stripped = lines[j].strip()
        if not stripped or stripped.startswith("#"):
            continue
        child_indent = _indent(lines[j]) if key_index is None and _indent(lines[j]) > 0 else child_indent
        if re.match(rf"^\s+{re.escape(key)}:(\s|$)", lines[j]):
            key_index = j
            break
    if key_index is None:
        lines.insert(start + 1, " " * child_indent + f"{key}: [{', '.join(_quote(i) for i in items)}]")
        return join_lines(lines, eol), list(items)

    key_line = lines[key_index]
    key_indent = _indent(key_line)
    rest = strip_comment(key_line).split(":", 1)[1].strip()
    if rest.startswith("["):
        # flow list: find the line holding the closing bracket (comments stripped), insert before it
        for j in range(key_index, end):
            content = strip_comment(lines[j])
            if "]" in content:
                close = content.rfind("]")
                before = content[:close].rstrip()
                inner_empty = before.endswith("[")
                addition = ("" if inner_empty else ", ") + ", ".join(_quote(i) for i in items)
                lines[j] = before + addition + content[close:] + _comment_tail(lines[j])
                return join_lines(lines, eol), list(items)
        return text, []  # unterminated flow list: leave the file alone
    if rest:
        return text, []  # a scalar where a list was expected: not ours to fix
    # block list: items are `- x` lines deeper than the key
    last_item = None
    item_indent = key_indent + 2
    for j in range(key_index + 1, end):
        stripped = lines[j].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _indent(lines[j]) <= key_indent:
            break
        if stripped.startswith("- "):
            last_item, item_indent = j, _indent(lines[j])
    insert_at = (last_item if last_item is not None else key_index) + 1
    for offset, item in enumerate(items):
        lines.insert(insert_at + offset, " " * item_indent + f"- {_quote(item)}")
    return join_lines(lines, eol), list(items)


# --------------------------------------------------------------------------- #
# 3. hook entries of .specify/extensions.yml                                    #
# --------------------------------------------------------------------------- #

Decide = Callable[[str, str, str, Optional[str]], Optional[str]]


def edit_hook_entries(text: str, field: str, decide: Decide) -> Tuple[str, List[Dict[str, Any]]]:
    """Set `field` on hook entries (`hooks:` -> `<event>:` -> `- extension: ...` items).

    `decide(extension, event, command, current)` returns the wanted value (as text) or None to leave the
    entry alone. The shape follows the siblings' `set_hook_flags`: only the matched field changes.
    Returns (text, [{extension, event, command, was, now}]).
    """
    lines, eol = split_lines(text)
    out: List[str] = []
    found: List[Dict[str, Any]] = []
    in_hooks = False
    event: Optional[str] = None
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped and _indent(line) == 0 and not stripped.startswith("#"):
            in_hooks = stripped == "hooks:"
            event = None
            out.append(line)
            i += 1
            continue
        item = re.match(r"^(\s*)-\s+(.*)$", line)
        if in_hooks and item is None:
            ev = re.match(r"^\s+([A-Za-z0-9_]+):\s*$", line)
            if ev:
                event = ev.group(1)
            out.append(line)
            i += 1
            continue
        if not (in_hooks and item and event):
            out.append(line)
            i += 1
            continue
        item_indent = len(item.group(1))
        block = [line]
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or _indent(lines[j]) > item_indent):
            block.append(lines[j])
            j += 1
        fields: Dict[str, Tuple[int, str]] = {}
        for k, bline in enumerate(block):
            body = bline.strip()[2:] if k == 0 else bline.strip()
            match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", body)
            if match and (k == 0 or _indent(bline) == item_indent + 2):
                fields[match.group(1)] = (k, match.group(2))
        ext = _scalar(fields.get("extension", (0, ""))[1])
        cmd = _scalar(fields.get("command", (0, ""))[1])
        current = _scalar(strip_comment(fields[field][1])) if field in fields else None
        want = decide(ext, event, cmd, current)
        if want is not None and want != current:
            if field in fields:
                k = fields[field][0]
                prefix = block[k][: _indent(block[k])] if k else None
                if k == 0:
                    block[0] = re.sub(rf"{field}:\s*[^\s#]*", f"{field}: {want}", block[0], count=1)
                else:
                    block[k] = f"{prefix}{field}: {want}{_comment_tail(block[k])}"
            else:
                block.insert(1, " " * (item_indent + 2) + f"{field}: {want}")
            found.append({"extension": ext, "event": event, "command": cmd, "was": current, "now": want})
        out.extend(block)
        i = j
    return join_lines(out, eol), found
