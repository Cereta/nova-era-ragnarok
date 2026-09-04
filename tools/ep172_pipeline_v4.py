#!/usr/bin/env python3
from __future__ import annotations
import json, re, shutil, sys
from pathlib import Path

from ep172_pipeline import MANIFEST, visible_spans, decode_literal, encode_literal

UPSTREAM_COMMIT = "e985006171d2eb320ee512a653f4c83aea3d81b6"

GLOSSARY = {
    "Water Garden Hard":"Jardim Suspenso Avançado", "Water Garden":"Jardim Suspenso",
    "Hidden Flower Garden":"Jardim de Flores Oculto", "Security Area 1":"Área de Segurança 1",
    "Security Area 2":"Área de Segurança 2", "Farm Lost in Time":"Estufa de Pitayas",
    "Hey! Sweety":"Duelo com Sweety", "Heart Hunters":"Caçadores de Coração",
    "Heart Hunter":"Caçador de Coração", "Yggdrasil Leaf":"Folha de Yggdrasil",
    "Prontera Church":"Igreja de Prontera", "Memorial Dungeon":"Masmorra Memorial",
    "memorial dungeon":"Masmorra Memorial", "automatic dolls":"bonecas automáticas",
    "automatic doll":"boneca automática", "Automatic Dolls":"Bonecas Automáticas",
    "Automatic Doll":"Boneca Automática", "Flower Garden Manager":"Gerente do Jardim de Flores",
    "Tartaros Storage":"Armazém Tártaro", "Bookworm":"Traça-de-Livro",
    "Garden Entrance":"Entrada do Jardim", "Potato Chips":"Chips de Batata",
    "Leaves of Silva Papilla":"Folhas da Silva Papilla",
    "Broken Warehouse Manager":"Gerente de Armazém Quebrado",
    "Broken Omega Cleaner":"Limpador Ômega Quebrado", "Broken Beta Guards":"Guardas Beta Quebrados",
    "Broken Cleaner":"Limpador Quebrado", "Omega Cleaner":"Limpador Ômega",
    "Guardian Parts":"Peças do Guardião", "Broken Beta":"Beta Quebrado",
    "Heart Hunter Skirmisher":"Caçador de Coração",
}
PROPER_NAMES = {
    "Varmundt","Dew","Magi","Lasis","Mark","Est","Elena","Almond","Sweety","Luina","Cotton",
    "Silk","Sigma","Lambda","Alpha","Beta","Harad","Hetilla","Juventus","Elyumina","Oscar","Rookie",
    "Wilde","Tess","Tamarin","Aas","Ashley","Rage","Rebellion","Pitaya","Papilla","Prontera","Yggdrasil",
    "Dien","Ridsh","Kaya","Toss","Grey","Gonie","Denny","Canine","Magenta","Boiler","Mina","Alp","Lucky","Seiyu"
}
RISKY_NAMES = {"Dew","Mark","Est","Cotton","Silk","Rage","Need","Rookie"}
EXACT = {
    "Wait a sec!!":"Espere um pouco!!", "Enter":"Entrar", "Garden Entrance":"Entrada do Jardim",
    "Adventurer":"Aventureiro", "Tracker":"Rastreador", "Boss Miow":"Chefe Miow", "inside":"interior",
    "lounge":"sala de descanso", "pavilion":"pavilhão", "uppermost part of the warehouse":"parte mais alta do armazém",
    "freezing trap":"armadilha congelante", "see me":"me vê", "same party":"mesmo grupo", "party":"grupo",
    "party leader":"líder do grupo",
}
KOREAN = {
    "알프":"Alp", "엄청난 장치들…":"Dispositivos impressionantes...",
    "도시… 아니 나라 수준의 규모에 에너지를 공급할 수 있겠군.":"Eles poderiam fornecer energia em escala suficiente para uma cidade... não, para um país inteiro.",
    "대체 뭘 위해 이렇게 까지…":"Mas para que fizeram tudo isso...?",
}
MONSTERS = {
    "Broken Beta":"Beta Quebrado", "Omega Cleaner":"Limpador Ômega", "Guardian Parts":"Peças do Guardião",
    "Bookworm":"Traça-de-Livro", "Broken Beta Guards":"Guardas Beta Quebrados",
    "Broken Omega Cleaner":"Limpador Ômega Quebrado", "Heart Hunter Skirmisher":"Caçador de Coração",
    "Broken Warehouse Manager":"Gerente de Armazém Quebrado", "Broken Cleaner":"Limpador Quebrado",
}
EN = re.compile(r"\b(the|this|that|these|those|you|your|we|our|they|their|is|are|was|were|will|would|should|could|cannot|have|has|had|does|did|and|but|if|then|when|where|what|why|how|who|with|without|from|into|inside|outside|before|after|again|already|still|here|there|now|please|thank|thanks|sorry|hello|welcome|enter|create|cancel|leave|wait|talk|look|come|help|find|found|need|must|seems|seem|place|room|garden|farm|security|manager|visitor|adventurer|party|leader|quest|instance|dungeon|research|laboratory|warning|failed|available|access|open|closed|dangerous|ready|right|left|over|under|about|because|around|through|something|someone|anything|everything|nothing|really|only)\b", re.I)


def protected_re():
    parts = [r'<INFO>.*?</INFO>', r'</?NAVI>', r'\^[0-9A-Fa-f]{6}', r'%[-+0-9.*]*[sdiufgxX]', r'\\[nrt]', r'\{[^{}]{1,80}\}']
    parts += [re.escape(x) for x in sorted(GLOSSARY, key=len, reverse=True)]
    parts += [r'(?<![A-Za-z])'+re.escape(x)+r'(?![A-Za-z])' for x in sorted(RISKY_NAMES, key=len, reverse=True)]
    return re.compile('|'.join('(?:'+x+')' for x in parts))
PROTECTED = protected_re()


def split(text):
    out=[]; pos=0
    for m in PROTECTED.finditer(text):
        if m.start()>pos: out.append((False,text[pos:m.start()]))
        v=m.group(0); out.append((True,GLOSSARY.get(v,v))); pos=m.end()
    if pos<len(text): out.append((False,text[pos:]))
    return out


def needs(text):
    s=text.strip()
    if not s or not re.search(r'[A-Za-z]',s) or re.search(r'[\uac00-\ud7a3]',s): return False
    if s in EXACT: return False
    return bool(EN.search(s) or re.search(r"\b(I|I'm|I'd|I'll|I've|my|me|him|her|his|it|its|to|of|for|at|on|in|as|be|been|get|got|make|take|see|say|said|know|think|want|let|all|some|any|more|very|just|one|two|first|second|last|next|back|away|much|many|time|way|thing|good|bad)\b",s,re.I))


def normalize(text, source=''):
    fixes = {r'\bAdventurer\b':'Aventureiro', r'\bGarden Entrance\b':'Entrada do Jardim', r'\bWait a sec!!\b':'Espere um pouco!!',
             r'\bTracker\b':'Rastreador', r'\bPotato Chips\b':'Chips de Batata', r'\bLeaves of Silva Papilla\b':'Folhas da Silva Papilla',
             r'\bfreezing trap\b':'armadilha congelante', r'\bsee me\b':'me vê', r'\buppermost part of the warehouse\b':'parte mais alta do armazém'}
    for a,b in fixes.items(): text=re.sub(a,b,text,flags=re.I)
    for a,b in sorted(GLOSSARY.items(),key=lambda kv:len(kv[0]),reverse=True): text=text.replace(a,b)
    if re.search(r'\bparty\b',source,re.I):
        text=re.sub(r'\blíder (?:da|de) festa\b','líder do grupo',text,flags=re.I)
        text=re.sub(r'\bmembros? (?:da|de) festa\b','membros do grupo',text,flags=re.I)
        text=re.sub(r'\b(?:sua |a )?festa\b|\bparty\b','grupo',text,flags=re.I)
    text=re.sub(r'\b([A-Za-zÀ-ÿ]+)-\s+(lo|la|los|las|lhe|lhes|se|me|te|nos|vos)\b',r'\1-\2',text,flags=re.I)
    text=re.sub(r'\bVice-\s+Presidente\b','Vice-Presidente',text,flags=re.I)
    text=re.sub(r'[ \t]+([,.!?;:])',r'\1',text); text=re.sub(r' {2,}',' ',text)
    return text.strip()


def collect(paths):
    found=set()
    for p in paths:
        if p.suffix.lower()!='.txt': continue
        for line in p.read_text(encoding='utf-8').splitlines():
            for s,e in visible_spans(line):
                t=decode_literal(line[s:e])
                if t.strip(): found.add(t)
    return sorted(found)


def build_cache(strings, cache_path):
    try: cache=json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    except Exception: cache={}
    cache.update(EXACT); cache.update(KOREAN)
    segments={part for t in strings if t not in KOREAN for prot,part in split(t) if not prot and needs(part)}
    pending=sorted(x for x in segments if x not in cache)
    if pending:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch
        name='Helsinki-NLP/opus-mt-tc-big-en-pt'; tok=AutoTokenizer.from_pretrained(name); model=AutoModelForSeq2SeqLM.from_pretrained(name); model.eval()
        for pos in range(0,len(pending),16):
            batch=pending[pos:pos+16]; enc=tok(batch,return_tensors='pt',padding=True,truncation=True,max_length=512)
            with torch.inference_mode(): gen=model.generate(**enc,max_new_tokens=512,num_beams=4)
            for src,out in zip(batch,tok.batch_decode(gen,skip_special_tokens=True)): cache[src]=normalize(out,src)
            cache_path.parent.mkdir(parents=True,exist_ok=True); cache_path.write_text(json.dumps(cache,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    return cache


def translate(text,cache):
    if text in KOREAN: return KOREAN[text]
    if text in EXACT: return EXACT[text]
    return normalize(''.join(part if prot else cache.get(part,EXACT.get(part,part)) for prot,part in split(text)),text)


def apply(p,cache):
    lines=p.read_text(encoding='utf-8').splitlines(keepends=True); out=[]; changed=0
    for line in lines:
        new=line
        for s,e in sorted(visible_spans(line),reverse=True):
            src=decode_literal(line[s:e]); dst=translate(src,cache)
            if dst!=src: new=new[:s]+encode_literal(dst)+new[e:]; changed+=1
        out.append(new)
    p.write_text(''.join(out),encoding='utf-8',newline=''); return changed


def mob_names(p):
    if '/mobs/' not in p.as_posix(): return 0
    out=[]; changed=0
    for raw in p.read_text(encoding='utf-8').splitlines(keepends=True):
        nl='\n' if raw.endswith('\n') else ''; body=raw[:-1] if nl else raw; parts=body.split('\t')
        if len(parts)>=4 and parts[1].strip()=='monster' and parts[2] in MONSTERS: parts[2]=MONSTERS[parts[2]]; body='\t'.join(parts); changed+=1
        out.append(body+nl)
    p.write_text(''.join(out),encoding='utf-8',newline=''); return changed


def audit(paths,root):
    residual=[]; visible=0
    for p in paths:
        if p.suffix.lower()!='.txt': continue
        r=str(p.relative_to(root)).replace('\\','/')
        for n,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
            for s,e in visible_spans(line):
                visible+=1; t=decode_literal(line[s:e]); clean=re.sub(r'<INFO>.*?</INFO>|<[^>]+>|\^[0-9A-Fa-f]{6}',' ',t)
                for name in PROPER_NAMES: clean=re.sub(r'(?<![A-Za-z])'+re.escape(name)+r'(?![A-Za-z])',' ',clean)
                if EN.search(clean): residual.append({'file':r,'line':n,'text':t})
    return {'upstream_commit':UPSTREAM_COMMIT,'episode':'17.2','files':[str(p.relative_to(root)).replace('\\','/') for p in paths],
            'visible_string_occurrences':visible,'english_residual_count':len(residual),'english_residuals':residual}


def main():
    if len(sys.argv)!=3: raise SystemExit('uso: ep172_pipeline_v4.py <upstream_dir> <stage_dir>')
    upstream=Path(sys.argv[1]).resolve(); stage=Path(sys.argv[2]).resolve()
    if stage.exists(): shutil.rmtree(stage)
    stage.mkdir(parents=True)
    copied=[]
    for rel in MANIFEST:
        src=upstream/rel
        if not src.exists(): raise SystemExit('arquivo ausente: '+rel)
        dst=stage/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); copied.append(dst)
    (stage/'UPSTREAM_COMMIT.txt').write_text(UPSTREAM_COMMIT+'\n',encoding='utf-8')
    cache=build_cache(collect(copied),Path('translation_cache/ep172_en_ptbr_v4.json').resolve())
    changed=localized=0
    for p in copied:
        if p.suffix.lower()=='.txt': changed+=apply(p,cache); localized+=mob_names(p)
    rep=audit(copied,stage); rep['translated_literal_occurrences']=changed; rep['localized_monster_display_names']=localized
    (stage/'AUDITORIA_EP17_2.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'translated_occurrences':changed,'localized_monster_display_names':localized,'english_residual_count':rep['english_residual_count'],'files':len(copied)},ensure_ascii=False))

if __name__=='__main__': main()
