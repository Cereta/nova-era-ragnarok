#!/usr/bin/env python3
from __future__ import annotations

import re

import ep172_pipeline_v6 as v6

base = v6.base

# v7 parte da saída estruturalmente íntegra do v6 e ataca somente os resíduos
# linguísticos/bordas de nomes que o gate v6 ainda encontrou. Mantemos o cache
# v6 para que este passe seja determinístico e rápido.
base.EXACT.update({
    "Warehouse... Signal received...": "Armazém... Sinal recebido...",
    "Warehouse...?": "Armazém...?",
    "Warehouse Clearance": "Autorização do Armazém",
    "Enter '": "Entrar '",
    "Entering standby mode.": "Entrando em modo de espera.",
    "Suppress unauthorized outsider.": "Neutralizar intruso não autorizado.",
    "---- Combat Mode ----": "---- Modo de Combate ----",
    "Dear guest...": "Caro convidado...",
    "Guest... Huh...": "Convidado... Hã...",
    "Communication ended.": "Comunicação encerrada.",
    "Sewage Plant Cleaning": "Limpeza da Estação de Esgoto",
    "1st Power Plant Cleaning": "Limpeza da 1ª Usina",
    "Network check, automatic error correction. Reconfirming packets......":
        "Verificação de rede, correção automática de erros. Reconfirmando pacotes......",
    "┏(^▽^)┛Cleaning..": "┏(^▽^)┛Limpeza..",
    "┏(^▽^)┛ Cleaning..": "┏(^▽^)┛ Limpeza..",
})

# Correções determinísticas para resíduos mistos gerados pelo modelo no v6.
OUTPUT_EXACT = {
    "Por um momento, eu vi Mark smiling brightly carrying a donation bag...":
        "Por um momento, vi Mark sorrindo alegremente enquanto carregava uma sacola de doações...",
    "Eu acho que posso ouvir MagiA voz de lá!!!":
        "Acho que consigo ouvir a voz de Magi vindo de lá!!!",
    "Está tudo bem, MarkAs habilidades de cura quase me curaram completamente.":
        "Está tudo bem. As habilidades de cura de Mark quase me curaram completamente.",
    "Esta é a mansão. Varmundt's Mansion!": "Esta é a Mansão Varmundt!",
    "Escritório de Segurança: Esta é a área 4, over.":
        "Escritório de Segurança: Esta é a área 4, câmbio.",
    "Como o Vice-PresidenteEu me sinto responsável por tudo isso.":
        "Como Vice-Presidente, eu me sinto responsável por tudo isso.",
    "Saí assim que entrei em contato de Vice-Presidente Kaya Toss E acabou de chegar.":
        "Saí assim que entrei em contato com o Vice-Presidente Kaya Toss e acabei de chegar.",
    "Vice-Presidente TossEu vi os relatos de que você trabalhou com os agentes do governo e aventureiros.":
        "Vice-Presidente Toss, vi os relatórios de que você trabalhou com agentes do governo e aventureiros.",
    "Também aceitaremos Vice-Presidente Kaya Toss\"opinião e analisar completamente o que ele investigou até agora, e distribuir as compensações e punição em conformidade.":
        "Também aceitaremos a opinião do Vice-Presidente Kaya Toss, analisaremos tudo o que ele investigou até agora e aplicaremos as recompensas e punições adequadas.",
    "Vice-PresidenteEstou com o Conselho do Rekenber, não precisas de saber a minha identidade.":
        "Sou o Vice-Presidente do Conselho da Rekenber. Você não precisa saber minha identidade.",
    "A empresa está preocupada com o Vice-Presidenteação. Quanto tempo você vai ser influenciado pela eloquência deles? O que você faria se um representante da empresa repetidamente agisse contra o interesse da empresa?":
        "A empresa está preocupada com as ações do Vice-Presidente. Por quanto tempo você continuará sendo influenciado pela eloquência deles? O que faria se um representante agisse repetidamente contra os interesses da empresa?",
    "Anyway, Alpha Dito isto, temos que lidar com os robôs automáticos que não são capazes de distinguir o código de identificação e recuperar os núcleos.":
        "De qualquer forma, Alpha disse que precisamos lidar com as bonecas automáticas incapazes de distinguir o código de identificação e recuperar seus núcleos.",
    "Eu não posso evitar. Estou preocupado com Elyumina's safety.":
        "Não posso evitar. Estou preocupado com a segurança de Elyumina.",
    "Também estou preocupado com os gerentes que perderam seu código de identificação que Alpha mentioned.":
        "Também estou preocupado com os gerentes que perderam o código de identificação mencionado por Alpha.",
    "Embora ainda não saibamos o paradeiro da Master's Collection No. 3, precisamos continuar a coletar informações vindas daqui...":
        "Embora ainda não saibamos o paradeiro da Coleção do Mestre nº 3, precisamos continuar coletando informações por aqui...",
    "Peço desculpa. É Varmundt A política da Mansion para manter os hóspedes de ^0000CDsituações perigosas^000000Por favor, espere um pouco mais.":
        "Peço desculpas. É política da Mansão Varmundt manter os hóspedes longe de ^0000CDsituações perigosas^000000. Por favor, espere mais um pouco.",
    "Robô de Limpeza: Unauthorized user. Communication terminated.":
        "Robô de Limpeza: Usuário não autorizado. Comunicação encerrada.",
    "Por favor, descanse seu corpo por um dia como Sigma ordered.":
        "Por favor, descanse por um dia, conforme Sigma ordenou.",
    "While Mestre Varmundt ainda estava presente, o andamento das tarefas foi verificado na forma de relatórios individuais e avaliações semanais no local.":
        "Enquanto Mestre Varmundt ainda estava presente, o andamento das tarefas era verificado por relatórios individuais e avaliações semanais no local.",
    "Currently, Mestre Varmundt Está ausente há mais de 1 milhão de horas.":
        "Atualmente, Mestre Varmundt está ausente há mais de 1 milhão de horas.",
    "Since Varmundt era uma pessoa que pode se mover independentemente do terreno, não instalamos uma estrutura separada para pessoas normais durante a criação do jardim de flores.":
        "Como Varmundt podia se mover independentemente do terreno, não instalamos uma estrutura separada para pessoas comuns durante a criação do jardim de flores.",
    "Children affected by LambdaAs memórias das memórias tendem a ser guerreiras em relação a estranhos. Eles não confiam em ninguém, mas Mestre Varmundt.":
        "As crianças afetadas pelas memórias de Lambda tendem a ser hostis com estranhos. Elas não confiam em ninguém além de Mestre Varmundt.",
    "A Papillas has devolvido!": "Papilla voltou!",
    "Next garden... portal creation complete... Mover-se para a direção das 12 horas... para usar... Obrigado...":
        "Próximo jardim... criação do portal concluída... Mova-se na direção das 12 horas para utilizá-lo... Obrigado...",
    "Silk: Dear guest...": "Silk: Caro convidado...",
    "Silk: Guest... Huh...": "Silk: Convidado... Hã...",
    "Silk: He-Help me!": "Silk: A-Ajude-me!",
    "eu trocarei ^FF00001 Physical Automatic Improvement Device^000000":
        "Vou trocar por ^FF00001 Dispositivo Físico de Aprimoramento Automático^000000.",
    "eu trocarei ^FF00001 Magical Automatic Improvement Device^000000":
        "Vou trocar por ^FF00001 Dispositivo Mágico de Aprimoramento Automático^000000.",
    "Você precisa de asas para se mudar para Barmund Mansion?":
        "Você precisa de asas para se deslocar até a Mansão Barmund?",
}

PRESERVE_NAMES = {
    name for name in base.PROPER_NAMES
    if base.GLOSSARY.get(name, name) == name
}
LOWERCASE_SAFE_NAMES = PRESERVE_NAMES - {"Est", "Magi", "Alp"}


def repair_name_boundaries(text: str) -> str:
    # Corrige apenas nomes preservados. O caso especial Alp evita quebrar Alpha.
    for name in sorted(PRESERVE_NAMES, key=len, reverse=True):
        if name == "Alp":
            text = re.sub(r'(?<![A-Za-zÀ-ÿ])Alp(?=[A-ZÀ-Ý])(?!ha)', 'Alp ', text)
            continue
        text = re.sub(
            r'(?<![A-Za-zÀ-ÿ])' + re.escape(name) + r'(?=[A-ZÀ-Ý])',
            name + ' ', text,
        )
        if name in LOWERCASE_SAFE_NAMES:
            text = re.sub(
                r'(?<![A-Za-zÀ-ÿ])' + re.escape(name) + r'(?=[a-zà-ÿ])',
                name + ' ', text,
            )
        text = re.sub(
            r'(?<=[A-Za-zÀ-ÿ])' + re.escape(name) + r'(?![A-Za-zÀ-ÿ])',
            ' ' + name, text,
        )
    return text


def post_repair(text: str) -> str:
    if text in OUTPUT_EXACT:
        return OUTPUT_EXACT[text]

    replacements = [
        ("Varmundt's Mansion", "Mansão Varmundt"),
        ("Varmundt A Mansion", "Mansão Varmundt"),
        ("Varmundt Mansion", "Mansão Varmundt"),
        ("Varmundt Mansão", "Mansão Varmundt"),
        ("Warehouse... Signal received...", "Armazém... Sinal recebido..."),
        ("Warehouse...?", "Armazém...?"),
        ("Warehouse Clearance", "Autorização do Armazém"),
        ("Unauthorized user. Communication terminated.", "Usuário não autorizado. Comunicação encerrada."),
        ("Entering standby mode.", "Entrando em modo de espera."),
        ("Suppress unauthorized outsider.", "Neutralizar intruso não autorizado."),
        ("---- Combat Mode ----", "---- Modo de Combate ----"),
        ("Dear guest...", "Caro convidado..."),
        ("Guest... Huh...", "Convidado... Hã..."),
        ("Communication ended.", "Comunicação encerrada."),
        ("Sewage Plant Cleaning", "Limpeza da Estação de Esgoto"),
        ("1st Power Plant Cleaning", "Limpeza da 1ª Usina"),
        ("Network check, automatic error correction. Reconfirming packets......",
         "Verificação de rede, correção automática de erros. Reconfirmando pacotes......"),
        ("┏(^▽^)┛Cleaning..", "┏(^▽^)┛Limpeza.."),
        ("┏(^▽^)┛ Cleaning..", "┏(^▽^)┛ Limpeza.."),
        ("Anyway,", "De qualquer forma,"),
        ("Anyways,", "De qualquer forma,"),
        ("Master's Collection No. 3", "Coleção do Mestre nº 3"),
        ("[mansion]", "[mansão]"),
    ]
    for before, after in replacements:
        text = text.replace(before, after)

    text = re.sub(r'\bMansion\b', 'Mansão', text)
    text = re.sub(r'\bWarehouse\b', 'Armazém', text)
    text = re.sub(r'\bCleaning\b', 'Limpeza', text)
    text = re.sub(r'\bWhile\b', 'Enquanto', text)
    text = re.sub(r'\bCurrently\b', 'Atualmente', text)
    text = re.sub(r'\bSince\b', 'Como', text)
    text = re.sub(r'\bEnter\b', 'Entrar', text)
    text = re.sub(r'\bAlpha mentioned\b', 'Alpha mencionou', text)
    text = re.sub(r'\bSigma ordered\b', 'Sigma ordenou', text)

    text = repair_name_boundaries(text)
    text = re.sub(r'Vice-Presidente(?=[A-Za-zÀ-ÿ])', 'Vice-Presidente ', text)

    # Ajustes recorrentes de possessivo/ordem gerados pela segmentação.
    text = text.replace('Magi A voz', 'a voz de Magi')
    text = text.replace("Papilla O 's", 'Papilla')
    text = text.replace('Papilla O s', 'Papilla')
    text = text.replace('Varmundt de mana', 'a mana de Varmundt')
    text = text.replace('Varmundt da pesquisa', 'da pesquisa de Varmundt')
    text = text.replace("Elyumina's safety", 'a segurança de Elyumina')
    text = text.replace('ao Mansão Varmundt', 'à Mansão Varmundt')
    text = text.replace('no Mansão Varmundt', 'na Mansão Varmundt')
    text = text.replace('do Mansão Varmundt', 'da Mansão Varmundt')
    text = text.replace('em Mansão Varmundt', 'na Mansão Varmundt')
    text = text.replace('dentro do Mansão Varmundt', 'dentro da Mansão Varmundt')
    text = text.replace('A Mansão Varmundt A Mansão', 'A Mansão Varmundt')
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)
    return text.strip()


ORIGINAL_TRANSLATE = v6.translate_v6


def translate_v7(text: str, cache):
    return post_repair(ORIGINAL_TRANSLATE(text, cache))


base.translate = translate_v7


if __name__ == '__main__':
    base.main()
