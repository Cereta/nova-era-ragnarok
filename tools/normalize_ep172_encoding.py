#!/usr/bin/env python3
from pathlib import Path

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


def decode(raw: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    raise UnicodeError("não foi possível detectar a codificação")


def main() -> None:
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("uso: normalize_ep172_encoding.py <upstream_dir>")
    root = Path(sys.argv[1])
    converted = []
    for rel in MANIFEST:
        p = root / rel
        raw = p.read_bytes()
        text, enc = decode(raw)
        # O Stage Nova Era usa fonte textual UTF-8 para impedir mojibake e manter PT-BR consistente.
        p.write_text(text, encoding="utf-8", newline="")
        if enc not in ("utf-8", "utf-8-sig"):
            converted.append({"file": rel, "from": enc, "to": "utf-8"})
    print(converted)


if __name__ == "__main__":
    main()
