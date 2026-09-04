#!/usr/bin/env python3
from __future__ import annotations
import re, sys
from pathlib import Path
from ep172_pipeline import MANIFEST

SUSPECT = "¾öÃ»³ÀåÄ¡µ½Æ´ë¹§±Ô¸¿°øÇ¤ð¢¥"


def decode(raw: bytes):
    for enc in ("utf-8-sig","utf-8","cp1252","latin-1"):
        try: return raw.decode(enc), enc
        except UnicodeDecodeError: pass
    raise UnicodeError("não foi possível detectar a codificação")


def repair(text: str):
    out=[]; total=0
    for line in text.splitlines(keepends=True):
        candidate=line
        if any(ch in line for ch in SUSPECT):
            try: fixed=line.encode("cp1252").decode("cp949")
            except (UnicodeEncodeError,UnicodeDecodeError): fixed=line
            if fixed!=line and (re.search(r"[\uac00-\ud7a3]",fixed) or any(x in fixed for x in "♥♡♬ㆀㅠ≥▽≤")):
                candidate=fixed; total+=1
        out.append(candidate)
    return ''.join(out),total


def main():
    if len(sys.argv)!=2: raise SystemExit("uso: normalize_ep172_encoding_v4.py <upstream_dir>")
    root=Path(sys.argv[1]); report=[]; repairs=0
    for rel in MANIFEST:
        p=root/rel; text,enc=decode(p.read_bytes()); text,n=repair(text); repairs+=n
        p.write_text(text,encoding="utf-8",newline="")
        if enc not in ("utf-8","utf-8-sig") or n: report.append({"file":rel,"from":enc,"to":"utf-8","cp949_repairs":n})
    print({"converted":report,"cp949_repairs":repairs})

if __name__=="__main__": main()
