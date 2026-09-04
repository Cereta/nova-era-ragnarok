#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

import ep172_pipeline_v4 as base

# v6 corrige a causa-raiz do v5:
# 1) codec de literais não duplica escapes de aspas;
# 2) espaços nas bordas dos nomes/tokens protegidos são preservados;
# 3) cache novo evita reaproveitar segmentos defeituosos do v4/v5;
# 4) resíduos reais conhecidos recebem terminologia PT-BR determinística.

base.GLOSSARY.update({
    "Manager Beta": "Gerente Beta",
    "Cleaning Robot ¥Ø": "Robô de Limpeza",
    "Mansion Manager モ": "Gerente da Mansão",
    "Communication Chips": "Chips de Comunicação",
    "Communication Chip": "Chip de Comunicação",
    "Master Varmundt": "Mestre Varmundt",
    "Vice President": "Vice-Presidente",
    "Enter Zone": "Entrar na Área",
    "Water Garden": "Jardim Aquático",
    "Water Garden Hard": "Jardim Aquático Difícil",
})

base.EXACT.update({
    "[알프]": "[Alp]",
    "I'm Mansion Manager モ of [The Mansion of the Great Sage Varmundt].":
        "Sou o Gerente da Mansão da [Mansão do Grande Sábio Varmundt].",
    "Cleaning Robot ¥Ø: Unauthorized user. Communication terminated.":
        "Robô de Limpeza: Usuário não autorizado. Comunicação encerrada.",
    "Enter Zone": "Entrar na Área",
})

# Mantém também o dicionário de coreano do pipeline-base.
base.KOREAN["[알프]"] = "[Alp]"


def decode_literal_v6(token: str) -> str:
    if not (token.startswith('"') and token.endswith('"')):
        raise ValueError("literal inválido")
    raw = token[1:-1]
    out = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == '\\' and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt == '"':
                out.append('"')
                i += 2
                continue
            if nxt == '\\':
                out.append('\\')
                i += 2
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


def encode_literal_v6(text: str) -> str:
    # Escapa exatamente uma vez. Sequências de controle rAthena como \\n, \\t
    # e tags/códigos de cor permanecem semanticamente idênticos.
    out = []
    for ch in text:
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


# Frases do glossário têm precedência sobre nomes próprios.
def protected_re_v6():
    parts = [
        r'<INFO>.*?</INFO>',
        r'</?NAVI>',
        r'\^[0-9A-Fa-f]{6}',
        r'%[-+0-9.*]*[sdiufgxX]',
        r'\\[nrt]',
        r'\{[^{}]{1,80}\}',
    ]
    parts += [re.escape(x) for x in sorted(base.GLOSSARY, key=len, reverse=True)]
    parts += [
        r'(?<![A-Za-zÀ-ÿ])' + re.escape(x) + r'(?![A-Za-zÀ-ÿ])'
        for x in sorted(base.PROPER_NAMES, key=len, reverse=True)
    ]
    return re.compile('|'.join('(?:' + x + ')' for x in parts))


base.PROTECTED = protected_re_v6()


def split_v6(text: str):
    out = []
    pos = 0
    for m in base.PROTECTED.finditer(text):
        if m.start() > pos:
            out.append((False, text[pos:m.start()]))
        value = m.group(0)
        out.append((True, base.GLOSSARY.get(value, value)))
        pos = m.end()
    if pos < len(text):
        out.append((False, text[pos:]))
    return out


def edge_parts(text: str):
    m = re.match(r'^(\s*)(.*?)(\s*)$', text, re.S)
    assert m
    return m.group(1), m.group(2), m.group(3)


def needs_v6(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    if re.search(r'[\uac00-\ud7a3]', s):
        return True
    return base.needs(s)


def normalize_v6(text: str, source: str = '') -> str:
    text = base.normalize(text, source)
    # Correções pós-modelo de resíduos recorrentes e variantes pouco naturais.
    fixes = {
        r'\bCommunication Chips\b': 'Chips de Comunicação',
        r'\bCommunication Chip\b': 'Chip de Comunicação',
        r'\bManager Beta\b': 'Gerente Beta',
        r'\bCleaning Robot\b': 'Robô de Limpeza',
        r'\bMansion Manager\b': 'Gerente da Mansão',
        r'\bVice President\b': 'Vice-Presidente',
        r'\bMaster Varmundt\b': 'Mestre Varmundt',
        r'\bEnter Zone\b': 'Entrar na Área',
        r'\bWait a sec!!\b': 'Espere um pouco!!',
    }
    for pattern, replacement in fixes.items():
        text = re.sub(pattern, replacement, text, flags=re.I)
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def build_cache_v6(strings, _ignored_cache_path):
    cache_path = Path('translation_cache/ep172_en_ptbr_v6.json').resolve()
    try:
        cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    except Exception:
        cache = {}

    cache.update(base.EXACT)
    cache.update(base.KOREAN)

    cores = set()
    for text in strings:
        if text in base.EXACT or text in base.KOREAN:
            continue
        for protected, part in split_v6(text):
            if protected:
                continue
            _lead, core, _trail = edge_parts(part)
            if core and needs_v6(core):
                cores.add(core)

    pending = sorted(core for core in cores if core not in cache)
    if pending:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch

        model_name = 'Helsinki-NLP/opus-mt-tc-big-en-pt'
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        model.eval()

        for pos in range(0, len(pending), 16):
            batch = pending[pos:pos + 16]
            enc = tokenizer(batch, return_tensors='pt', padding=True, truncation=True, max_length=512)
            with torch.inference_mode():
                generated = model.generate(**enc, max_new_tokens=512, num_beams=4)
            outputs = tokenizer.batch_decode(generated, skip_special_tokens=True)
            for src, out in zip(batch, outputs):
                cache[src] = normalize_v6(out, src)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    return cache


def translate_v6(text: str, cache):
    if text in base.EXACT:
        return base.EXACT[text]
    if text in base.KOREAN:
        return base.KOREAN[text]

    pieces = []
    for protected, part in split_v6(text):
        if protected:
            pieces.append(part)
            continue
        lead, core, trail = edge_parts(part)
        if not core:
            pieces.append(part)
            continue
        translated = cache.get(core, core)
        pieces.append(lead + normalize_v6(translated, core) + trail)

    result = ''.join(pieces)
    # Remove somente espaços indevidos antes de pontuação; nunca remove os
    # espaços que separam nomes próprios dos trechos traduzidos.
    result = re.sub(r'[ \t]+([,.!?;:])', r'\1', result)
    result = re.sub(r' {2,}', ' ', result)
    return result.strip()


# Monkey patches deliberados: as funções do módulo-base consultam esses nomes
# em runtime, portanto todo o fluxo passa a usar o codec/segmentação v6.
base.decode_literal = decode_literal_v6
base.encode_literal = encode_literal_v6
base.split = split_v6
base.needs = needs_v6
base.normalize = normalize_v6
base.build_cache = build_cache_v6
base.translate = translate_v6


if __name__ == '__main__':
    base.main()
