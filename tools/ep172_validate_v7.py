#!/usr/bin/env python3
from __future__ import annotations

import re

import ep172_validate_v6 as validator

# Mantém todas as verificações estruturais do v6. O único ajuste do detector é
# retirar "vice" e "president" isolados, que davam falso positivo em
# "Vice-Presidente" já localizado. A expressão "vice president" continua
# coberta explicitamente, assim como os demais resíduos de alta confiança.
validator.ENGLISH_RE = re.compile(
    r"(?:\bvice\s+president\b|"
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
    r"mansion|cleaning|robot|unauthorized|user|terminated|anyway|anyways|"
    r"smiling|brightly|carrying|donation|bag|voice|skills|country|device|facilities|public|"
    r"instructions|facility|recorded|abnormal|usage|accumulate|removed|network|report|"
    r"weekly|similarity|mode|sleep|target|detected|project|storage|warehouse|guest|"
    r"physical|magical|improvement|children|affected|portal|combat|standby|outsider)\b)",
    re.I,
)


if __name__ == '__main__':
    raise SystemExit(validator.main())
