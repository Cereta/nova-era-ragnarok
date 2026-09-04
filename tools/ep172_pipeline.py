#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable

UPSTREAM_COMMIT = "e985006171d2eb320ee512a653f4c83aea3d81b6"

# Arquivos diretamente ligados ao conteúdo jogável do Episode 17.2 no upstream fixado.
MANIFEST = [
    "npc/re/quests/quests_17_2.txt",
    "npc/re/instances/HiddenGarden.txt",
    "npc/re/instances/WaterGarden.txt",
    "npc/re/instances/TwilightGarden.txt",
    "npc/re/instances/LostFarm.txt",
    "npc/re/merchants/enchan_sage_legacy_17_2.txt",
    "npc/re/merchants/barters/quests_17_2.yml",
    "npc/re/warps/other/ba_2whs.txt",
    "npc/re/warps/other/ba_maison.txt",
    "npc/re/warps/other/ba_pw.txt",
    "npc/re/mobs/fields/ba_lost.txt",
    "npc/re/mobs/fields/ba_maison.txt",
    "npc/re/mobs/dungeons/ba_2whs.txt",
    "npc/re/mobs/dungeons/ba_bath.txt",
    "npc/re/mobs/dungeons/ba_lib.txt",
    "npc/re/mobs/dungeons/ba_pw.txt",
]

# Strings técnicas que nunca devem ser alteradas quando usadas como identificadores.
INTERNAL_INSTANCE_NAMES = {
    "Hidden Flower Garden",
    "Security Area 1",
    "Security Area 2",
    "Water Garden",
    "Water Garden Hard",
    "Hey! Sweety",
    "Farm Lost in Time",
}

# Termos bRO/Nova Era aplicados somente em texto visível.
PHRASE_GLOSSARY = {
    "Water Garden Hard": "Jardim Aquático Difícil",
    "Water Garden": "Jardim Aquático",
    "Hidden Flower Garden": "Jardim de Flores Oculto",
    "Security Area 1": "Área de Segurança 1",
    "Security Area 2": "Área de Segurança 2",
    "Farm Lost in Time": "Fazenda de Pitayas",
    "Hey! Sweety": "Duelo com Sweety",
    "Heart Hunters": "Caçadores de Corações",
    "Heart Hunter": "Caçador de Corações",
    "Yggdrasil Leaf": "Folha de Yggdrasil",
    "Prontera Church": "Igreja de Prontera",
    "memorial dungeon": "Masmorra Memorial",
    "Memorial Dungeon": "Masmorra Memorial",
    "automatic doll": "boneca automática",
    "Automatic Doll": "Boneca Automática",
    "Flower Garden Manager": "Gerente do Jardim de Flores",
}

# Palavras/nome próprios que o tradutor não deve converter (Dew->Orvalho, Mark->Marca etc.).
PROPER_NAMES = {
    "Varmundt", "Dew", "Magi", "Lasis", "Mark", "Est", "Elena", "Almond",
    "Sweety", "Luina", "Cotton", "Silk", "Sigma", "Lambda", "Alpha", "Beta",
    "Harad", "Hetilla", "Juventus", "Elyumina", "Oscar", "Rookie", "Wilde",
    "Tess", "Tamarin", "Aas", "Ashley", "Rage", "Rookie", "Rebellion",
    "Pitaya", "Papilla", "Prontera", "Yggdrasil", "Varmundt",
}

# Palavras inglesas usadas apenas para detectar resíduo em texto VISÍVEL.
ENGLISH_MARKERS = re.compile(
    r"\b(the|this|that|these|those|you|your|you're|you'll|you've|we|we're|our|they|their|"
    r"is|are|was|were|will|would|should|could|can|can't|cannot|have|has|had|do|does|did|"
    r"not|don't|doesn't|didn't|and|but|or|if|then|when|where|what|why|how|who|with|without|"
    r"from|into|inside|outside|before|after|again|already|still|here|there|now|today|tomorrow|"
    r"please|thank|thanks|sorry|hello|welcome|enter|create|cancel|leave|wait|talk|look|go|come|"
    r"help|find|found|need|must|seems|seem|place|area|room|garden|farm|security|manager|"
    r"visitor|adventurer|party|leader|quest|instance|dungeon|monster|research|laboratory|"
    r"warning|failed|available|access|open|closed|dangerous|ready|right|left|over|under)\b",
    re.IGNORECASE,
)

STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')


def decode_literal(token: str) -> str:
    assert token.startswith('"') and token.endswith('"')
    raw = token[1:-1]
    return raw.replace(r'\\"', '"').replace(r'\\\\', '\\')


def encode_literal(text: str) -> str:
    text = text.replace('\\', r'\\').replace('"', r'\\"')
    return '"' + text + '"'


def split_top_level_args(expr: str) -> list[tuple[int, int]]:
    """Retorna spans de argumentos separados por vírgula, respeitando strings/parênteses."""
    spans: list[tuple[int, int]] = []
    start = 0
    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(expr):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth = max(0, depth - 1)
        elif ch == ',' and depth == 0:
            spans.append((start, i))
            start = i + 1
    spans.append((start, len(expr)))
    return spans


def literal_spans(text: str, offset: int = 0) -> list[tuple[int, int]]:
    return [(m.start() + offset, m.end() + offset) for m in STRING_RE.finditer(text)]


def command_arg_literal_spans(line: str, command: str, arg_indexes: Iterable[int] | None) -> list[tuple[int, int]]:
    # Encontra o comando como palavra e analisa o restante da instrução até ';'.
    m = re.search(r'\b' + re.escape(command) + r'\b', line)
    if not m:
        return []
    tail_start = m.end()
    tail = line[tail_start:]
    semi = tail.rfind(';')
    if semi >= 0:
        tail = tail[:semi]
    args = split_top_level_args(tail)
    wanted = range(len(args)) if arg_indexes is None else arg_indexes
    out: list[tuple[int, int]] = []
    for idx in wanted:
        if idx < 0 or idx >= len(args):
            continue
        a, b = args[idx]
        out.extend(literal_spans(tail[a:b], tail_start + a))
    return out


def visible_spans(line: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []

    # Diálogo e menus.
    if re.search(r'\bmes\b', line):
        spans += command_arg_literal_spans(line, "mes", [0])
    if re.search(r'\bmesf\b', line):
        spans += command_arg_literal_spans(line, "mesf", [0])
    if re.search(r'\bnpctalk\b', line):
        spans += command_arg_literal_spans(line, "npctalk", [0])
    if re.search(r'\bunittalk\b', line):
        spans += command_arg_literal_spans(line, "unittalk", [1])
    if re.search(r'\bmapannounce\b', line):
        spans += command_arg_literal_spans(line, "mapannounce", [1])
    if re.search(r'(?<!map)\bannounce\b', line):
        spans += command_arg_literal_spans(line, "announce", [0])
    if re.search(r'\bdispbottom\b', line):
        spans += command_arg_literal_spans(line, "dispbottom", [0])
    if re.search(r'\bwaitingroom\b', line):
        spans += command_arg_literal_spans(line, "waitingroom", [0])
    if re.search(r'\bbroadcast\b', line):
        spans += command_arg_literal_spans(line, "broadcast", [0])

    # select() / prompt() podem aparecer dentro de if/switch.
    for fn in ("select", "prompt"):
        for fm in re.finditer(r'\b' + fn + r'\s*\(', line):
            start = fm.end()
            depth = 1
            in_str = False
            esc = False
            end = len(line)
            for i in range(start, len(line)):
                ch = line[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            spans += literal_spans(line[start:end], start)

    # Arrays/variáveis explicitamente usados como menu/opção.
    if re.search(r'(?:setarray\s+)?[^;]*(?:menu|option|choice)\$\s*(?:\[.*?\])?\s*[,=]', line, re.I):
        spans += literal_spans(line)

    # Nomes custom de monstros são somente apresentação; IDs permanecem intactos.
    mm = re.search(r'\bmonster\b', line)
    if mm:
        spans += command_arg_literal_spans(line, "monster", [3])
    am = re.search(r'\bareamonster\b', line)
    if am:
        spans += command_arg_literal_spans(line, "areamonster", [5])

    # Remove duplicatas/overlaps.
    uniq = sorted(set(spans))
    result: list[tuple[int, int]] = []
    for s, e in uniq:
        if not any(s >= a and e <= b for a, b in result):
            result.append((s, e))
    return result


def protect_text(text: str) -> tuple[str, dict[str, str]]:
    restore: dict[str, str] = {}
    n = 0

    def hold(value: str, replacement: str | None = None) -> str:
        nonlocal n
        key = f"ZXQH{n:04d}QXZ"
        n += 1
        restore[key] = value if replacement is None else replacement
        return key

    # Glossário de frases primeiro: o modelo nunca toca no termo e a forma PT-BR volta no final.
    for src in sorted(PHRASE_GLOSSARY, key=len, reverse=True):
        if src in text:
            text = text.replace(src, hold(src, PHRASE_GLOSSARY[src]))

    # Cores, escapes, placeholders printf e tags de controle.
    patterns = [
        r'\^[0-9A-Fa-f]{6}', r'%[-+0-9.*]*[sdiufgxX]', r'\\[nrt]',
        r'<[^>]{1,80}>', r'\{[^{}]{1,80}\}',
    ]
    for pat in patterns:
        text = re.sub(pat, lambda m: hold(m.group(0)), text)

    # Nomes próprios sensíveis à tradução automática.
    for name in sorted(PROPER_NAMES, key=len, reverse=True):
        text = re.sub(r'(?<![A-Za-z])' + re.escape(name) + r'(?![A-Za-z])', lambda m: hold(m.group(0)), text)
    return text, restore


def restore_text(text: str, restore: dict[str, str]) -> str:
    # Modelos às vezes inserem espaços ao redor do token; tolerar isso.
    for key, value in restore.items():
        text = re.sub(r'\s*' + re.escape(key) + r'\s*', value, text)
    return text


def should_translate(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped in INTERNAL_INSTANCE_NAMES:
        # Esta função só é chamada para texto visível; nesses casos queremos a forma PT-BR.
        return True
    # Cabeçalho de nome próprio puro: preservar, salvo papéis genéricos cobertos pelo glossário.
    if stripped.startswith('[') and stripped.endswith(']'):
        inner = stripped[1:-1].strip()
        if inner in PROPER_NAMES:
            return False
    # Sons/onomatopeias sem palavras reconhecíveis não precisam de tradução.
    return bool(ENGLISH_MARKERS.search(stripped) or re.search(r"\b(I|I'm|I'd|I'll|I've|my|me|him|her|his|hers|it|its|to|of|for|at|on|in|as|be|been|get|got|make|take|see|say|said|know|think|want|let|all|some|any|more|very|just)\b", stripped, re.I))


def normalize_ptbr(text: str) -> str:
    # Correções terminológicas/variante pt-BR depois da tradução automática.
    replacements = {
        "masmorra memorial": "Masmorra Memorial",
        "caçador de coração": "Caçador de Corações",
        "caçadores de coração": "Caçadores de Corações",
        "boneca automatizada": "boneca automática",
        "boneca automática automática": "boneca automática",
        "grupo de festa": "grupo",
        "líder da festa": "líder do grupo",
        "membro da festa": "membro do grupo",
        "missão": "missão",
        "nível de base": "nível Base",
        "Level Base": "nível Base",
    }
    for a, b in replacements.items():
        text = text.replace(a, b)
    # Pontuação/espaçamento comum.
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def translate_unique(strings: list[str], cache_path: Path) -> dict[str, str]:
    cache: dict[str, str] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    pending = [s for s in strings if s not in cache and should_translate(s)]
    if pending:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch

        model_name = "Helsinki-NLP/opus-mt-en-ROMANCE"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        model.eval()

        batch_size = 24
        for pos in range(0, len(pending), batch_size):
            batch_original = pending[pos:pos + batch_size]
            batch_protected: list[str] = []
            restores: list[dict[str, str]] = []
            for s in batch_original:
                p, r = protect_text(s)
                batch_protected.append(">>pt_BR<< " + p)
                restores.append(r)
            enc = tokenizer(batch_protected, return_tensors="pt", padding=True, truncation=True, max_length=512)
            with torch.inference_mode():
                generated = model.generate(**enc, max_new_tokens=512, num_beams=4)
            outs = tokenizer.batch_decode(generated, skip_special_tokens=True)
            for src, out, restore in zip(batch_original, outs, restores):
                out = restore_text(out, restore)
                out = normalize_ptbr(out)
                cache[src] = out
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    # Frases cobertas integralmente pelo glossário não precisam passar pelo modelo.
    for s in strings:
        if s in cache:
            continue
        out = s
        changed = False
        for a, b in PHRASE_GLOSSARY.items():
            if a in out:
                out = out.replace(a, b)
                changed = True
        if changed:
            cache[s] = normalize_ptbr(out)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return cache


def apply_translations(path: Path, cache: dict[str, str]) -> int:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines(keepends=True)
    changed = 0
    out_lines: list[str] = []
    for line in lines:
        spans = visible_spans(line)
        if not spans:
            out_lines.append(line)
            continue
        new_line = line
        for s, e in sorted(spans, reverse=True):
            tok = line[s:e]
            text = decode_literal(tok)
            translated = cache.get(text)
            if translated is None:
                # Aplicar glossário simples mesmo quando o detector não pede tradução.
                translated = text
                for a, b in PHRASE_GLOSSARY.items():
                    translated = translated.replace(a, b)
            if translated != text:
                new_line = new_line[:s] + encode_literal(translated) + new_line[e:]
                changed += 1
        out_lines.append(new_line)
    path.write_text(''.join(out_lines), encoding="utf-8", newline="")
    return changed


def collect_visible_strings(paths: list[Path]) -> list[str]:
    found: set[str] = set()
    for path in paths:
        if path.suffix.lower() != ".txt":
            continue
        for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
            for s, e in visible_spans(line):
                text = decode_literal(line[s:e])
                if text.strip():
                    found.add(text)
    return sorted(found)


def audit(paths: list[Path], root: Path) -> dict:
    residuals: list[dict] = []
    dynamic_leaks: list[dict] = []
    total_visible = 0
    for path in paths:
        if path.suffix.lower() != ".txt":
            continue
        rel = str(path.relative_to(root)).replace('\\', '/')
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            spans = visible_spans(line)
            total_visible += len(spans)
            for s, e in spans:
                text = decode_literal(line[s:e]).strip()
                if not text:
                    continue
                # Desconsidera nomes próprios puros e onomatopeias, mas não frases inglesas.
                clean = re.sub(r'\^[0-9A-Fa-f]{6}', '', text)
                clean = re.sub(r'\[[^\]]+\]', '', clean) if text.startswith('[') and text.endswith(']') else clean
                if ENGLISH_MARKERS.search(clean):
                    residuals.append({"file": rel, "line": lineno, "text": text, "source": line.strip()})
            if spans and re.search(r'\.@(?:md_name|instance_name)\$', line):
                dynamic_leaks.append({"file": rel, "line": lineno, "source": line.strip()})

    return {
        "upstream_commit": UPSTREAM_COMMIT,
        "episode": "17.2",
        "files": [str(p.relative_to(root)).replace('\\', '/') for p in paths],
        "visible_string_occurrences": total_visible,
        "english_residual_count": len(residuals),
        "english_residuals": residuals,
        "dynamic_internal_name_leak_count": len(dynamic_leaks),
        "dynamic_internal_name_leaks": dynamic_leaks,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("uso: ep172_pipeline.py <upstream_dir> <stage_dir>", file=sys.stderr)
        return 2
    upstream = Path(sys.argv[1]).resolve()
    stage = Path(sys.argv[2]).resolve()
    stage.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    missing: list[str] = []
    for rel in MANIFEST:
        src = upstream / rel
        if not src.exists():
            missing.append(rel)
            continue
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(dst)
    if missing:
        raise SystemExit("Arquivos esperados ausentes no upstream: " + ", ".join(missing))

    # Prova de origem para impedir Stage montado sobre revisão errada.
    (stage / "UPSTREAM_COMMIT.txt").write_text(UPSTREAM_COMMIT + "\n", encoding="utf-8")

    strings = collect_visible_strings(copied)
    cache_path = Path("translation_cache/ep172_en_ptbr.json").resolve()
    cache = translate_unique(strings, cache_path)

    changed = 0
    for path in copied:
        if path.suffix.lower() == ".txt":
            changed += apply_translations(path, cache)

    report = audit(copied, stage)
    report["translated_literal_occurrences"] = changed
    report_path = stage / "AUDITORIA_EP17_2.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # O primeiro passe não declara 100% se houver inglês visível ou nomes técnicos vazando.
    print(json.dumps({
        "translated_occurrences": changed,
        "english_residual_count": report["english_residual_count"],
        "dynamic_internal_name_leak_count": report["dynamic_internal_name_leak_count"],
        "files": len(copied),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
