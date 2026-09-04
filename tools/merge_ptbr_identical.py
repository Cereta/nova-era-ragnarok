#!/usr/bin/env python3
"""Merge PT-BR visible strings only when rAthena script logic is identical.

This tool is intentionally fail-closed. It never copies a whole legacy script over a
newer base. It keeps the target file as the skeleton and replaces only string
literals used by a conservative whitelist of player-visible script commands.

Examples:
  python tools/merge_ptbr_identical.py OLD_STAGE.zip NOVA_BASE.zip OUT.zip \
      --allow-list confirmed_100.txt --report merge_report.json

  python tools/merge_ptbr_identical.py OLD_STAGE NOVA_BASE OUT_DIR \
      --report merge_report.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

# command -> visible argument policy
# "all" means every quoted string after the command is considered visible text.
VISIBLE_POLICY = {
    "mes": "all",
    "mesc": {0},
    "mesf": "all",
    "select": "all",
    "prompt": "all",
    "menu": "all",
    "dispbottom": "all",
    "announce": {0},
    "mapannounce": {1},
    "areaannounce": {5},
    "npctalk": {0},
    "message": {1},
}

COMMAND_RE = re.compile(r"\b(" + "|".join(map(re.escape, sorted(VISIBLE_POLICY, key=len, reverse=True))) + r")\b")


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    command: str
    arg_index: int


@dataclass
class LoadedText:
    text: str
    encoding: str


def read_text(path: Path) -> LoadedText:
    data = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return LoadedText(data.decode(encoding), encoding)
        except UnicodeDecodeError:
            pass
    raise UnicodeDecodeError("unknown", data, 0, len(data), f"cannot decode {path}")


def write_text(path: Path, text: str, encoding: str) -> None:
    # New/modern rAthena content should remain UTF-8 when it already is UTF-8.
    # For a legacy target encoding, preserve that target encoding and fail if the
    # imported PT-BR text cannot be represented.
    actual = "utf-8" if encoding in ("utf-8", "utf-8-sig") else encoding
    payload = text.encode(actual)
    if encoding == "utf-8-sig":
        payload = b"\xef\xbb\xbf" + payload
    path.write_bytes(payload)


def statement_spans(text: str) -> list[tuple[int, int]]:
    """Return semicolon-delimited statement spans, ignoring semicolons in strings/comments."""
    spans: list[tuple[int, int]] = []
    start = 0
    i = 0
    quote = False
    esc = False
    line_comment = False
    block_comment = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if ch == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                quote = False
            i += 1
            continue

        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch == '"':
            quote = True
            i += 1
            continue
        if ch == ";":
            spans.append((start, i + 1))
            start = i + 1
        i += 1

    if start < len(text):
        spans.append((start, len(text)))
    return spans


def quoted_spans(text: str, base: int = 0) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(text):
        if text[i] != '"':
            i += 1
            continue
        start = i
        i += 1
        esc = False
        while i < len(text):
            ch = text[i]
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                i += 1
                out.append((base + start, base + i))
                break
            i += 1
        else:
            # Unterminated string: leave it untouched. Structural comparison will fail
            # if target/source do not match exactly.
            break
    return out


def command_outside_strings(statement: str) -> tuple[str, int] | None:
    """Find the first whitelisted command outside quoted strings and comments."""
    masked = []
    i = 0
    quote = False
    esc = False
    line_comment = False
    block_comment = False
    while i < len(statement):
        ch = statement[i]
        nxt = statement[i + 1] if i + 1 < len(statement) else ""
        if line_comment:
            masked.append("\n" if ch == "\n" else " ")
            if ch == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            masked.append(" ")
            if ch == "*" and nxt == "/":
                masked.append(" ")
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if quote:
            masked.append(" ")
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                quote = False
            i += 1
            continue
        if ch == "/" and nxt == "/":
            masked.extend((" ", " "))
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            masked.extend((" ", " "))
            block_comment = True
            i += 2
            continue
        if ch == '"':
            masked.append(" ")
            quote = True
            i += 1
            continue
        masked.append(ch)
        i += 1

    match = COMMAND_RE.search("".join(masked))
    if not match:
        return None
    return match.group(1), match.end()


def top_level_arg_index(statement: str, command_end: int, token_start: int) -> int:
    """Count top-level commas between a command and a string token."""
    i = command_end
    depth = 0
    arg = 0
    quote = False
    esc = False
    while i < token_start:
        ch = statement[i]
        if quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                quote = False
            i += 1
            continue
        if ch == '"':
            quote = True
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            arg += 1
        i += 1
    return arg


def visible_spans(text: str) -> list[Span]:
    out: list[Span] = []
    for stmt_start, stmt_end in statement_spans(text):
        statement = text[stmt_start:stmt_end]
        found = command_outside_strings(statement)
        if not found:
            continue
        command, command_end = found
        policy = VISIBLE_POLICY[command]
        for abs_start, abs_end in quoted_spans(statement, stmt_start):
            rel_start = abs_start - stmt_start
            if rel_start < command_end:
                continue
            arg_index = top_level_arg_index(statement, command_end, rel_start)
            if policy == "all" or arg_index in policy:
                out.append(Span(abs_start, abs_end, command, arg_index))
    return out


def replace_spans(text: str, spans: list[Span], replacements: Iterable[str]) -> str:
    pairs = list(zip(spans, replacements))
    out: list[str] = []
    pos = 0
    for span, replacement in pairs:
        out.append(text[pos:span.start])
        out.append(replacement)
        pos = span.end
    out.append(text[pos:])
    return "".join(out)


def strip_comments_and_normalize_ws(text: str) -> str:
    """Remove comments and normalize whitespace outside strings without touching literals."""
    out: list[str] = []
    i = 0
    quote = False
    esc = False
    line_comment = False
    block_comment = False
    pending_space = False

    def flush_space() -> None:
        nonlocal pending_space
        if pending_space and out and out[-1] != " ":
            out.append(" ")
        pending_space = False

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if ch == "\n":
                line_comment = False
                pending_space = True
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                pending_space = True
                i += 2
            else:
                i += 1
            continue
        if quote:
            flush_space()
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                quote = False
            i += 1
            continue
        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch == '"':
            flush_space()
            out.append(ch)
            quote = True
            i += 1
            continue
        if ch.isspace():
            pending_space = True
            i += 1
            continue
        flush_space()
        out.append(ch)
        i += 1
    return "".join(out).strip()


def fingerprint(text: str) -> tuple[str, list[Span]]:
    spans = visible_spans(text)
    masked = replace_spans(text, spans, ['"__PTBR_VISIBLE__"'] * len(spans))
    return strip_comments_and_normalize_ws(masked), spans


def merge_one(source: LoadedText, target: LoadedText) -> tuple[str | None, dict]:
    source_fp, source_spans = fingerprint(source.text)
    target_fp, target_spans = fingerprint(target.text)

    if source_fp != target_fp:
        return None, {
            "status": "rejected",
            "reason": "structure_or_nonvisible_content_differs",
            "source_visible_strings": len(source_spans),
            "target_visible_strings": len(target_spans),
        }
    if len(source_spans) != len(target_spans):
        return None, {
            "status": "rejected",
            "reason": "visible_string_count_differs",
            "source_visible_strings": len(source_spans),
            "target_visible_strings": len(target_spans),
        }

    source_literals = [source.text[s.start:s.end] for s in source_spans]
    merged = replace_spans(target.text, target_spans, source_literals)

    # Strong postcondition: replacing text must not change the target fingerprint.
    merged_fp, merged_spans = fingerprint(merged)
    if merged_fp != target_fp or len(merged_spans) != len(target_spans):
        return None, {
            "status": "rejected",
            "reason": "post_merge_structure_changed",
            "source_visible_strings": len(source_spans),
            "target_visible_strings": len(target_spans),
        }

    changed = sum(
        1
        for src_span, dst_span in zip(source_spans, target_spans)
        if source.text[src_span.start:src_span.end] != target.text[dst_span.start:dst_span.end]
    )
    return merged, {
        "status": "imported" if changed else "identical_no_change",
        "replaced_visible_strings": changed,
        "visible_strings": len(source_spans),
    }


def find_project_root(root: Path) -> Path:
    current = root
    for _ in range(4):
        if (current / "npc").is_dir() or (current / "src").is_dir():
            return current
        children = [p for p in current.iterdir() if p.is_dir()]
        files = [p for p in current.iterdir() if p.is_file()]
        if len(children) == 1 and not files:
            current = children[0]
            continue
        break
    return root


def extract_if_zip(path: Path, temp_root: Path, label: str) -> tuple[Path, bool]:
    if path.is_dir():
        return find_project_root(path), False
    if not zipfile.is_zipfile(path):
        raise SystemExit(f"{path} is neither a directory nor a ZIP archive")
    out = temp_root / label
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        zf.extractall(out)
    return find_project_root(out), True


def load_allow_list(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    allowed: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().replace("\\", "/")
        if not line or line.startswith("#"):
            continue
        allowed.add(line.lstrip("./"))
    return allowed


def iter_candidate_files(root: Path, allowed: set[str] | None) -> Iterable[Path]:
    if allowed is not None:
        for rel in sorted(allowed):
            path = root / rel
            if path.is_file() and path.suffix.lower() == ".txt":
                yield path
        return
    yield from sorted(p for p in root.rglob("*.txt") if p.is_file())


def make_zip(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(root).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("translated", type=Path, help="translated/homologated old stage directory or ZIP")
    parser.add_argument("target", type=Path, help="current base directory or ZIP; remains the authoritative skeleton")
    parser.add_argument("output", type=Path, help="output directory or ZIP")
    parser.add_argument("--allow-list", type=Path, default=None, help="UTF-8 file containing confirmed 100%% relative paths")
    parser.add_argument("--report", type=Path, default=Path("merge_ptbr_report.json"))
    args = parser.parse_args()

    allowed = load_allow_list(args.allow_list)

    with tempfile.TemporaryDirectory(prefix="nova_era_ptbr_merge_") as td:
        temp = Path(td)
        source_root, _ = extract_if_zip(args.translated, temp, "translated")
        target_root, target_was_zip = extract_if_zip(args.target, temp, "target")
        work_root = temp / "work"
        shutil.copytree(target_root, work_root)

        report = {
            "mode": "fail_closed_translation_only",
            "source": str(args.translated),
            "target": str(args.target),
            "allow_list": str(args.allow_list) if args.allow_list else None,
            "files": [],
            "summary": {},
        }

        seen: set[str] = set()
        for source_path in iter_candidate_files(source_root, allowed):
            rel = source_path.relative_to(source_root).as_posix()
            seen.add(rel)
            target_path = target_root / rel
            entry = {"path": rel}
            if not target_path.is_file():
                entry.update(status="rejected", reason="missing_in_target")
                report["files"].append(entry)
                continue
            try:
                source = read_text(source_path)
                target = read_text(target_path)
                merged, result = merge_one(source, target)
                entry.update(result)
                entry["source_encoding"] = source.encoding
                entry["target_encoding"] = target.encoding
                if merged is not None and result["status"] == "imported":
                    out_path = work_root / rel
                    write_text(out_path, merged, target.encoding)
            except Exception as exc:  # fail closed per-file, keep base untouched
                entry.update(status="rejected", reason="exception", error=f"{type(exc).__name__}: {exc}")
            report["files"].append(entry)

        if allowed is not None:
            for rel in sorted(allowed - seen):
                report["files"].append({"path": rel, "status": "rejected", "reason": "missing_in_source_or_not_txt"})

        counts: dict[str, int] = {}
        total_replacements = 0
        for entry in report["files"]:
            counts[entry["status"]] = counts.get(entry["status"], 0) + 1
            total_replacements += int(entry.get("replaced_visible_strings", 0))
        report["summary"] = {
            "files_total": len(report["files"]),
            "status_counts": counts,
            "visible_strings_replaced": total_replacements,
        }

        report_json = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

        if args.output.suffix.lower() == ".zip" or target_was_zip:
            make_zip(work_root, args.output)
        else:
            if args.output.exists():
                shutil.rmtree(args.output)
            shutil.copytree(work_root, args.output)

        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report_json, encoding="utf-8")

    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
