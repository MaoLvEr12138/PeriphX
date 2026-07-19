from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _Line:
    indent: int
    text: str


def load_simple_yaml(text: str) -> Any:
    lines = _prepare_lines(text)
    if not lines:
        return {}
    value, next_index = _parse_block(lines, 0, lines[0].indent)
    if next_index != len(lines):
        raise ValueError("unexpected trailing YAML content")
    return value


def _prepare_lines(text: str) -> list[_Line]:
    lines: list[_Line] = []
    for raw in text.splitlines():
        stripped = _strip_comment(raw).rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        if "\t" in stripped[:indent]:
            raise ValueError("tabs are not supported in YAML input")
        lines.append(_Line(indent=indent, text=stripped[indent:]))
    return lines


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    result: list[str] = []
    for char in line:
        if char == "'" and not in_double:
            in_single = not in_single
            result.append(char)
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            result.append(char)
            continue
        if char == "#" and not in_single and not in_double:
            break
        result.append(char)
    return "".join(result)


def _parse_block(lines: list[_Line], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index

    line = lines[index]
    if line.indent < indent:
        return {}, index

    if line.text.startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_dict(lines, index, indent)


def _parse_dict(lines: list[_Line], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError(f"unexpected indentation at line: {line.text}")
        if line.text.startswith("- "):
            break

        key, sep, raw_value = line.text.partition(":")
        if not sep:
            raise ValueError(f"expected key/value pair: {line.text}")
        key = key.strip()
        raw_value = raw_value.strip()
        index += 1

        if raw_value:
            result[key] = _parse_scalar(raw_value)
            continue

        if index < len(lines) and lines[index].indent > indent:
            nested, index = _parse_block(lines, index, lines[index].indent)
            result[key] = nested
        else:
            result[key] = None
    return result, index


def _parse_list(lines: list[_Line], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent != indent or not line.text.startswith("- "):
            break

        item_text = line.text[2:].strip()
        index += 1

        if not item_text:
            if index < len(lines) and lines[index].indent > indent:
                nested, index = _parse_block(lines, index, lines[index].indent)
                result.append(nested)
            else:
                result.append(None)
            continue

        if ":" in item_text:
            item: dict[str, Any] = {}
            key, sep, raw_value = item_text.partition(":")
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value:
                item[key] = _parse_scalar(raw_value)
            else:
                if index < len(lines) and lines[index].indent > indent:
                    nested, index = _parse_block(lines, index, lines[index].indent)
                    item[key] = nested
                else:
                    item[key] = None

            if index < len(lines) and lines[index].indent > indent:
                nested, index = _parse_block(lines, index, lines[index].indent)
                if not isinstance(nested, dict):
                    raise ValueError("list item continuation must be a mapping")
                item.update(nested)

            result.append(item)
            continue

        result.append(_parse_scalar(item_text))

        if index < len(lines) and lines[index].indent > indent:
            nested, index = _parse_block(lines, index, lines[index].indent)
            if not isinstance(result[-1], dict):
                raise ValueError("scalar list item cannot have nested block")
            result[-1].update(nested)

    return result, index


def _parse_scalar(value: str) -> Any:
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]

    normalized = value.replace("_", "")
    if normalized.startswith("0x") or normalized.startswith("0X"):
        try:
            return int(normalized, 16)
        except ValueError:
            return value
    try:
        return int(normalized, 10)
    except ValueError:
        return value
