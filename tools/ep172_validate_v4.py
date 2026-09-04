#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from ep172_pipeline import MANIFEST, decode_literal, visible_spans
from ep172_pipeline_v4 import MONSTERS, PROPER_NAMES, split, needs

MOJIBAKE_RE = re.compile(r"[¾öÃ»³ÀåÄ¡µ½Æ´ë¹§±Ô¸¿°øÇ¤ð¢¥]|ZX(?:QH|H)?\d+QXZ")
HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")
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


def visible_literals(path: Path):
    out=[]
    if path.suffix.lower()!='.txt': return out
    for lineno,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        for s,e in visible_spans(line): out.append((lineno,decode_literal(line[s:e])))
    return out


def mask_visible_line(line: str):
    new=line
    for s,e in sorted(visible_spans(line),reverse=True): new=new[:s]+'"<VISIBLE>"'+new[e:]
    parts=new.rstrip('\n').split('\t')
    if len(parts)>=4 and parts[1].strip()=='monster':
        parts[2]='<MONSTER_DISPLAY>'; new='\t'.join(parts)+('\n' if new.endswith('\n') else '')
    return new


def structure_text(path: Path):
    if path.suffix.lower()!='.txt': return path.read_text(encoding='utf-8')
    return ''.join(mask_visible_line(x) for x in path.read_text(encoding='utf-8').splitlines(keepends=True))


def signature(text: str):
    return {
        'colors':re.findall(r'\^[0-9A-Fa-f]{6}',text),
        'info':re.findall(r'<INFO>.*?</INFO>',text),
        'navi_tags':re.findall(r'</?NAVI>',text),
        'printf':re.findall(r'%[-+0-9.*]*[sdiufgxX]',text),
        'escapes':re.findall(r'\\[nrt]',text),
    }


def clean_english(text: str):
    clean=re.sub(r'<INFO>.*?</INFO>',' ',text); clean=re.sub(r'</?NAVI>|\^[0-9A-Fa-f]{6}',' ',clean)
    for name in sorted(PROPER_NAMES,key=len,reverse=True):
        clean=re.sub(r'(?<![A-Za-z])'+re.escape(name)+r'(?![A-Za-z])',' ',clean)
    return clean


def needs_translation(text: str):
    if HANGUL_RE.search(text): return True
    return any((not prot) and needs(part) for prot,part in split(text))


def main():
    if len(sys.argv)!=3: raise SystemExit('uso: ep172_validate_v4.py <upstream_dir> <stage_dir>')
    upstream=Path(sys.argv[1]).resolve(); stage=Path(sys.argv[2]).resolve(); failures=[]; warnings=[]
    stats={'files':0,'visible_occurrences':0,'english_visible_residuals':0,'untranslated_visible_literals':0,
           'mojibake_or_placeholders':0,'hangul_visible_residuals':0,'control_token_mismatches':0,
           'structure_mismatches':0,'unlocalized_monster_names':0,'spacing_anomalies':0}
    def fail(kind,file,**data): failures.append({'kind':kind,'file':file,**data})

    for relative in MANIFEST:
        src=upstream/relative; dst=stage/relative
        if not src.exists() or not dst.exists(): fail('missing_file',relative,upstream_exists=src.exists(),stage_exists=dst.exists()); continue
        stats['files']+=1
        try: dst_text=dst.read_text(encoding='utf-8',errors='strict')
        except UnicodeDecodeError as exc: fail('invalid_utf8',relative,error=str(exc)); continue

        if structure_text(src)!=structure_text(dst):
            stats['structure_mismatches']+=1; fail('structure_changed',relative)

        src_lits=visible_literals(src); dst_lits=visible_literals(dst); stats['visible_occurrences']+=len(dst_lits)
        if len(src_lits)!=len(dst_lits): fail('visible_literal_count_changed',relative,upstream=len(src_lits),stage=len(dst_lits)); continue

        for idx,((sl,source),(dl,translated)) in enumerate(zip(src_lits,dst_lits),1):
            if signature(source)!=signature(translated):
                stats['control_token_mismatches']+=1; fail('control_tokens_changed',relative,literal=idx,source_line=sl,stage_line=dl,before=source,after=translated,before_signature=signature(source),after_signature=signature(translated))
            if needs_translation(source) and source==translated:
                stats['untranslated_visible_literals']+=1; fail('visible_literal_untranslated',relative,line=dl,text=translated)
            if MOJIBAKE_RE.search(translated):
                stats['mojibake_or_placeholders']+=1; fail('mojibake_or_placeholder',relative,line=dl,text=translated)
            if HANGUL_RE.search(translated):
                stats['hangul_visible_residuals']+=1; fail('hangul_visible_residual',relative,line=dl,text=translated)
            if ENGLISH_RE.search(clean_english(translated)):
                stats['english_visible_residuals']+=1; fail('english_visible_residual',relative,line=dl,text=translated)
            no_info=re.sub(r'<INFO>.*?</INFO>','',translated)
            for name in PROPER_NAMES:
                if re.search(r'[A-Za-zÀ-ÿ]'+re.escape(name),no_info) or re.search(re.escape(name)+r'[A-Za-zÀ-ÿ]',no_info):
                    stats['spacing_anomalies']+=1; fail('glued_proper_name',relative,line=dl,name=name,text=translated); break

        if '/mobs/' in '/'+relative:
            for lineno,line in enumerate(dst_text.splitlines(),1):
                parts=line.split('\t')
                if len(parts)>=4 and parts[1].strip()=='monster' and parts[2] in MONSTERS:
                    stats['unlocalized_monster_names']+=1; fail('unlocalized_monster_display_name',relative,line=lineno,text=parts[2])

    proof=stage/'UPSTREAM_COMMIT.txt'
    if not proof.exists() or proof.read_text(encoding='utf-8').strip()!='e985006171d2eb320ee512a653f4c83aea3d81b6': fail('upstream_proof_invalid','UPSTREAM_COMMIT.txt')
    report={'status':'PASS' if not failures else 'FAIL','stats':stats,'failures':failures,'warnings':warnings,'failure_count':len(failures),'warning_count':len(warnings)}
    (stage/'VALIDACAO_EP17_2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('ep172_validation_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'stats':stats,'failures':len(failures),'warnings':len(warnings)},ensure_ascii=False))
    return 0 if not failures else 1

if __name__=='__main__': raise SystemExit(main())
