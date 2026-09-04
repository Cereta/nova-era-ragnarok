#!/usr/bin/env python3
from __future__ import annotations

import re

import ep172_pipeline_v4 as base

# Episode 17.2 v5: mantém o pipeline v4, mas endurece a proteção de nomes
# próprios e corrige o último resíduo de inglês confirmado pela auditoria v4.
base.GLOSSARY.update({
    "Manager Beta": "Gerente Beta",
})


def protected_re_v5():
    parts = [
        r'<INFO>.*?</INFO>',
        r'</?NAVI>',
        r'\^[0-9A-Fa-f]{6}',
        r'%[-+0-9.*]*[sdiufgxX]',
        r'\\[nrt]',
        r'\{[^{}]{1,80}\}',
    ]
    # Termos conhecidos são substituídos somente como texto visível.
    parts += [re.escape(x) for x in sorted(base.GLOSSARY, key=len, reverse=True)]
    # Todos os nomes próprios são protegidos quando aparecem como tokens
    # independentes. Isso evita Dew/Mark/Est/Varmundt etc. grudados ou
    # reinterpretados pelo modelo sem bloquear palavras portuguesas como
    # "Este", "Estamos" ou "Estás".
    parts += [
        r'(?<![A-Za-zÀ-ÿ])' + re.escape(x) + r'(?![A-Za-zÀ-ÿ])'
        for x in sorted(base.PROPER_NAMES, key=len, reverse=True)
    ]
    return re.compile('|'.join('(?:' + x + ')' for x in parts))


base.PROTECTED = protected_re_v5()


if __name__ == "__main__":
    base.main()
