#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from ep172_pipeline import MANIFEST, visible_spans
import ep172_pipeline_v6 as pipeline

base = pipeline.base
MONSTERS = base.MONSTERS
PROPER_NAMES = base.PROPER_NAMES

ALL_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')
HANGUL_RE = re.compile(r'[\uac00-\ud7a3]')
MOJIBAKE_RE = re.compile(
    r'(?:\ufffd|Ã[¡-¿]|Â[¡-¿]|¾ö|Ã»³|ÀåÄ|µé|Æ´|±Ô¸|¿¡|°ø±|¥Ø|¥â|モ|ZX(?:QH|H)?\d+QXZ)'
)

# Marcadores de inglês de alta confiança. Evitamos homógrafos/termos já
# naturalizados em PT-BR, como "come" e "chip(s)", para não gerar falso positivo.
ENGLISH_RE = re.compile(
    r"\b(the|this|that|these|those|you|your|you're|you'll|you've|we|we're|our|they|their|"
    r"is|are|was|were|will|would|should|could|can't|cannot|have|has|had|does|did|didn't|"
    r"but|if|then|when|where|what|why|how|who|with|without|from|into|inside|outside|"
    r"before|after|again|already|still|here|there|today|tomorrow|please|thank|thanks|"
    r"sorry|hello|welcome|enter|create|cancel|leave|wait|talk|look|help|find|found|"
    r"need|must|seems|seem|place|room|garden|farm|security|manager|visitor|adventurer|"
    r"party|leader|quest|instance|dungeon|research|laboratory|warning|failed|available|"
    r"access|open|closed|dangerous|ready|right|left|over|under|about|because|around|through|"
    r"something|someone|anything|everything|nothing|really|only|same|uppermost|leaves|"
    r"freezing|trap|communication|master|while|currently|since|ordered|safety|mentioned|"
    r"vice|president|mansion|cleaning|robot|unauthorized|user|terminated|anyway|anyways|"
    r"smiling|brightly|carrying|donation|bag|voice|skills|country|device|facilities|public|"
    r"instructions|facility|recorded|abnormal|usage|accumulate|removed|network|report|"
    r"weekly|similarity|mode|sleep|target|detected|project|storage|warehouse|guest)\b",
    re.I,
)

ALPHA = r'A-Za-zÀ-ÿ'
PRESERVE_NAMES = {
    name for name in PROPER_NAMES
    if base.GLOSSARY.get(name, name) == name
}


def all_tokens(line: str):
    return [
        (m.start(), m.end(), m.group(0), pipeline.decode_literal_v6(m.group(0)))
        for m in ALL_STRING_RE.finditer(line)
    ]


def source_visible_indexes(line: str, tokens):
    spans = visible_spans(line)
    return {
        idx for idx, (start, end, _raw, _decoded) in enumerate(tokens)
        if any(start >= vs and end <= ve for vs, ve in spans)
    }


def mask_all_strings(line: str):
    new = line
    for match in reversed(list(ALL_STRING_RE.finditer(line))):
        new = new[:match.start()] + '"<STRING>"' + new[match.end():]
    body = new.rstrip('\n')
    newline = '\n' if new.endswith('\n') else ''
    parts = body.split('\t')
    if len(parts) >= 4 and parts[1].strip() == 'monster':
        parts[2] = '<MONSTER_DISPLAY>'
        body = '\t'.join(parts)
    return body + newline


def signature(text: str):
    return {
        'colors': re.findall(r'\^[0-9A-Fa-f]{6}', text),
        'info': re.findall(r'<INFO>.*?</INFO>', text),
        'navi_tags': re.findall(r'</?NAVI>', text),
        'printf': re.findall(r'%[-+0-9.*]*[sdiufgxX]', text),
        'escapes': re.findall(r'\\[nrt]', text),
    }


def strip_nonlinguistic(text: str):
    clean = re.sub(r'<INFO>.*?</INFO>', ' ', text)
    clean = re.sub(r'</?NAVI>|\^[0-9A-Fa-f]{6}', ' ', clean)
    for name in sorted(PRESERVE_NAMES, key=len, reverse=True):
        clean = re.sub(
            r'(?<![' + ALPHA + '])' + re.escape(name) + r'(?![' + ALPHA + '])',
            ' ', clean,
        )
    return clean


def has_english_residual(text: str) -> bool:
    return bool(ENGLISH_RE.search(strip_nonlinguistic(text)))


def source_requires_translation(text: str) -> bool:
    if HANGUL_RE.search(text):
        return True
    if has_english_residual(text):
        return True
    for protected, part in pipeline.split_v6(text):
        if protected:
            continue
        _lead, core, _trail = pipeline.edge_parts(part)
        if core and pipeline.needs_v6(core):
            return True
    return False


def standalone_count(text: str, name: str):
    pattern = r'(?<![' + ALPHA + '])' + re.escape(name) + r'(?![' + ALPHA + '])'
    return len(re.findall(pattern, text))


def validate_visible(fail, stats, relative, line_no, source: str, translated: str):
    if signature(source) != signature(translated):
        stats['control_token_mismatches'] += 1
        fail(
            'control_tokens_changed', relative, line=line_no,
            before=source, after=translated,
            before_signature=signature(source), after_signature=signature(translated),
        )

    if source_requires_translation(source) and source == translated:
        stats['untranslated_visible_literals'] += 1
        fail('visible_literal_untranslated', relative, line=line_no, text=translated)

    if MOJIBAKE_RE.search(translated):
        stats['mojibake_or_placeholders'] += 1
        fail('mojibake_or_placeholder', relative, line=line_no, text=translated)

    if HANGUL_RE.search(translated):
        stats['hangul_visible_residuals'] += 1
        fail('hangul_visible_residual', relative, line=line_no, text=translated)

    if has_english_residual(translated):
        stats['english_visible_residuals'] += 1
        fail('english_visible_residual', relative, line=line_no, text=translated)

    # Nomes técnicos/personagens que não têm forma localizada no glossário
    # precisam continuar como tokens independentes, nunca grudados.
    for name in PRESERVE_NAMES:
        before = standalone_count(source, name)
        if not before:
            continue
        after = standalone_count(translated, name)
        if after < before:
            stats['proper_name_boundary_errors'] += 1
            fail(
                'proper_name_missing_or_glued', relative, line=line_no,
                name=name, expected_occurrences=before,
                found_occurrences=after, text=translated,
            )


def validate_monster_line(fail, stats, relative, line_no, source_line: str, stage_line: str):
    source_parts = source_line.rstrip('\n').split('\t')
    stage_parts = stage_line.rstrip('\n').split('\t')
    if len(source_parts) < 4 or source_parts[1].strip() != 'monster':
        return
    if len(stage_parts) < 4 or stage_parts[1].strip() != 'monster':
        return
    expected = MONSTERS.get(source_parts[2], source_parts[2])
    if stage_parts[2] != expected:
        stats['unlocalized_monster_names'] += 1
        fail(
            'monster_display_name_invalid', relative, line=line_no,
            source=source_parts[2], expected=expected, actual=stage_parts[2],
        )


def main():
    if len(sys.argv) != 3:
        raise SystemExit('uso: ep172_validate_v6.py <upstream_dir> <stage_dir>')

    upstream = Path(sys.argv[1]).resolve()
    stage = Path(sys.argv[2]).resolve()
    failures = []
    warnings = []
    stats = {
        'files': 0,
        'visible_occurrences': 0,
        'english_visible_residuals': 0,
        'untranslated_visible_literals': 0,
        'mojibake_or_placeholders': 0,
        'hangul_visible_residuals': 0,
        'control_token_mismatches': 0,
        'structure_mismatches': 0,
        'internal_reference_mismatches': 0,
        'unlocalized_monster_names': 0,
        'proper_name_boundary_errors': 0,
    }

    def fail(kind, file, **data):
        failures.append({'kind': kind, 'file': file, **data})

    for relative in MANIFEST:
        src = upstream / relative
        dst = stage / relative
        if not src.exists() or not dst.exists():
            fail('missing_file', relative, upstream_exists=src.exists(), stage_exists=dst.exists())
            continue
        stats['files'] += 1

        try:
            src_text = src.read_text(encoding='utf-8', errors='strict')
            dst_text = dst.read_text(encoding='utf-8', errors='strict')
        except UnicodeDecodeError as exc:
            fail('invalid_utf8', relative, error=str(exc))
            continue

        if src.suffix.lower() != '.txt':
            if src_text != dst_text:
                stats['structure_mismatches'] += 1
                fail('non_text_manifest_file_changed', relative)
            continue

        src_lines = src_text.splitlines(keepends=True)
        dst_lines = dst_text.splitlines(keepends=True)
        if len(src_lines) != len(dst_lines):
            stats['structure_mismatches'] += 1
            fail('line_count_changed', relative, upstream=len(src_lines), stage=len(dst_lines))
            continue

        for line_no, (source_line, stage_line) in enumerate(zip(src_lines, dst_lines), 1):
            source_tokens = all_tokens(source_line)
            stage_tokens = all_tokens(stage_line)

            if len(source_tokens) != len(stage_tokens):
                stats['structure_mismatches'] += 1
                fail(
                    'string_literal_count_changed', relative, line=line_no,
                    upstream=len(source_tokens), stage=len(stage_tokens),
                )
                continue

            if mask_all_strings(source_line) != mask_all_strings(stage_line):
                stats['structure_mismatches'] += 1
                fail(
                    'script_structure_line_changed', relative, line=line_no,
                    upstream=mask_all_strings(source_line).rstrip('\n'),
                    stage=mask_all_strings(stage_line).rstrip('\n'),
                )

            visible = source_visible_indexes(source_line, source_tokens)
            stats['visible_occurrences'] += len(visible)

            for idx, (src_token, dst_token) in enumerate(zip(source_tokens, stage_tokens)):
                _ss, _se, source_raw, source_decoded = src_token
                _ds, _de, stage_raw, stage_decoded = dst_token
                if idx in visible:
                    validate_visible(
                        fail, stats, relative, line_no,
                        source_decoded, stage_decoded,
                    )
                elif source_raw != stage_raw:
                    stats['internal_reference_mismatches'] += 1
                    fail(
                        'internal_string_reference_changed', relative, line=line_no,
                        literal_index=idx + 1, before=source_decoded, after=stage_decoded,
                    )

            validate_monster_line(fail, stats, relative, line_no, source_line, stage_line)

    proof = stage / 'UPSTREAM_COMMIT.txt'
    expected_commit = 'e985006171d2eb320ee512a653f4c83aea3d81b6'
    if not proof.exists() or proof.read_text(encoding='utf-8').strip() != expected_commit:
        fail('upstream_proof_invalid', 'UPSTREAM_COMMIT.txt')

    report = {
        'status': 'PASS' if not failures else 'FAIL',
        'stats': stats,
        'failures': failures,
        'warnings': warnings,
        'failure_count': len(failures),
        'warning_count': len(warnings),
    }
    (stage / 'VALIDACAO_EP17_2.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    Path('ep172_validation_summary.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps({
        'status': report['status'],
        'stats': stats,
        'failures': len(failures),
        'warnings': len(warnings),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
