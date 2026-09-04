#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from ep172_pipeline import MANIFEST, decode_literal, visible_spans
import ep172_pipeline_v5 as pipeline_v5

base = pipeline_v5.base
MONSTERS = base.MONSTERS
PROPER_NAMES = base.PROPER_NAMES
split = base.split
needs = base.needs

ALL_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')
HANGUL_RE = re.compile(r'[\uac00-\ud7a3]')
MOJIBAKE_RE = re.compile(
    r'(?:\ufffd|Ã[¡-¿]|Â[¡-¿]|¾ö|Ã»³|ÀåÄ|µé|Æ´|±Ô¸|¿¡|°ø±|¥Ø|¥â|ZX(?:QH|H)?\d+QXZ)'
)
ENGLISH_RE = re.compile(
    r"\b(the|this|that|these|those|you|your|you're|you'll|you've|we|we're|our|they|their|"
    r"is|are|was|were|will|would|should|could|can't|cannot|have|has|had|does|did|didn't|"
    r"and|but|if|then|when|where|what|why|how|who|with|without|from|into|inside|outside|"
    r"before|after|again|already|still|here|there|now|today|tomorrow|please|thank|thanks|"
    r"sorry|hello|welcome|enter|create|cancel|leave|wait|talk|look|come|help|find|found|"
    r"need|must|seems|seem|place|room|garden|farm|security|manager|visitor|adventurer|"
    r"party|leader|quest|instance|dungeon|research|laboratory|warning|failed|available|"
    r"access|open|closed|dangerous|ready|right|left|over|under|about|because|around|through|"
    r"something|someone|anything|everything|nothing|really|only|same|uppermost|leaves|"
    r"freezing|trap|potato|chips)\b",
    re.I,
)
ALPHA = r'A-Za-zÀ-ÿ'


def all_tokens(line: str):
    return [(m.start(), m.end(), m.group(0), decode_literal(m.group(0))) for m in ALL_STRING_RE.finditer(line)]


def source_visible_indexes(line: str, tokens):
    spans = visible_spans(line)
    return {
        idx for idx, (s, e, _raw, _decoded) in enumerate(tokens)
        if any(s >= vs and e <= ve for vs, ve in spans)
    }


def mask_all_strings(line: str):
    new = line
    for m in reversed(list(ALL_STRING_RE.finditer(line))):
        new = new[:m.start()] + '"<STRING>"' + new[m.end():]
    body = new.rstrip('\n')
    nl = '\n' if new.endswith('\n') else ''
    parts = body.split('\t')
    if len(parts) >= 4 and parts[1].strip() == 'monster':
        parts[2] = '<MONSTER_DISPLAY>'
        body = '\t'.join(parts)
    return body + nl


def signature(text: str):
    return {
        'colors': re.findall(r'\^[0-9A-Fa-f]{6}', text),
        'info': re.findall(r'<INFO>.*?</INFO>', text),
        'navi_tags': re.findall(r'</?NAVI>', text),
        'printf': re.findall(r'%[-+0-9.*]*[sdiufgxX]', text),
        'escapes': re.findall(r'\\[nrt]', text),
    }


def clean_english(text: str):
    clean = re.sub(r'<INFO>.*?</INFO>', ' ', text)
    clean = re.sub(r'</?NAVI>|\^[0-9A-Fa-f]{6}', ' ', clean)
    for name in sorted(PROPER_NAMES, key=len, reverse=True):
        clean = re.sub(
            r'(?<![' + ALPHA + '])' + re.escape(name) + r'(?![' + ALPHA + '])',
            ' ', clean,
        )
    return clean


def needs_translation(text: str):
    if HANGUL_RE.search(text):
        return True
    return any((not protected) and needs(part) for protected, part in split(text))


def standalone_count(text: str, name: str):
    pat = r'(?<![' + ALPHA + '])' + re.escape(name) + r'(?![' + ALPHA + '])'
    return len(re.findall(pat, text))


def validate_visible(fail, stats, relative, line_no, source: str, translated: str):
    if signature(source) != signature(translated):
        stats['control_token_mismatches'] += 1
        fail(
            'control_tokens_changed', relative, line=line_no,
            before=source, after=translated,
            before_signature=signature(source), after_signature=signature(translated),
        )

    if needs_translation(source) and source == translated:
        stats['untranslated_visible_literals'] += 1
        fail('visible_literal_untranslated', relative, line=line_no, text=translated)

    if MOJIBAKE_RE.search(translated):
        stats['mojibake_or_placeholders'] += 1
        fail('mojibake_or_placeholder', relative, line=line_no, text=translated)

    if HANGUL_RE.search(translated):
        stats['hangul_visible_residuals'] += 1
        fail('hangul_visible_residual', relative, line=line_no, text=translated)

    if ENGLISH_RE.search(clean_english(translated)):
        stats['english_visible_residuals'] += 1
        fail('english_visible_residual', relative, line=line_no, text=translated)

    # Só verifica nomes que existiam como tokens independentes no texto-fonte.
    # Assim "Est" não gera falso positivo dentro de "Este/Estamos/Estás" e
    # "Magi" não gera falso positivo dentro de "Magical".
    for name in PROPER_NAMES:
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
    sp = source_line.rstrip('\n').split('\t')
    dp = stage_line.rstrip('\n').split('\t')
    if len(sp) < 4 or sp[1].strip() != 'monster':
        return
    if len(dp) < 4 or dp[1].strip() != 'monster':
        return
    expected = MONSTERS.get(sp[2], sp[2])
    if dp[2] != expected:
        stats['unlocalized_monster_names'] += 1
        fail(
            'monster_display_name_invalid', relative, line=line_no,
            source=sp[2], expected=expected, actual=dp[2],
        )


def main():
    if len(sys.argv) != 3:
        raise SystemExit('uso: ep172_validate_v5.py <upstream_dir> <stage_dir>')

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

        for line_no, (sl, dl) in enumerate(zip(src_lines, dst_lines), 1):
            st = all_tokens(sl)
            dt = all_tokens(dl)

            if len(st) != len(dt):
                stats['structure_mismatches'] += 1
                fail(
                    'string_literal_count_changed', relative, line=line_no,
                    upstream=len(st), stage=len(dt),
                )
                continue

            if mask_all_strings(sl) != mask_all_strings(dl):
                stats['structure_mismatches'] += 1
                fail(
                    'script_structure_line_changed', relative, line=line_no,
                    upstream=mask_all_strings(sl).rstrip('\n'),
                    stage=mask_all_strings(dl).rstrip('\n'),
                )

            visible = source_visible_indexes(sl, st)
            stats['visible_occurrences'] += len(visible)

            for idx, (src_token, dst_token) in enumerate(zip(st, dt)):
                _ss, _se, sraw, sdecoded = src_token
                _ds, _de, draw, ddecoded = dst_token
                if idx in visible:
                    validate_visible(fail, stats, relative, line_no, sdecoded, ddecoded)
                elif sraw != draw:
                    stats['internal_reference_mismatches'] += 1
                    fail(
                        'internal_string_reference_changed', relative, line=line_no,
                        literal_index=idx + 1, before=sdecoded, after=ddecoded,
                    )

            validate_monster_line(fail, stats, relative, line_no, sl, dl)

    proof = stage / 'UPSTREAM_COMMIT.txt'
    if not proof.exists() or proof.read_text(encoding='utf-8').strip() != 'e985006171d2eb320ee512a653f4c83aea3d81b6':
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
