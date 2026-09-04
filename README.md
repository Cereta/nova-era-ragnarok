# Nova Era Ragnarok — Tradução por Episódios

Base técnica fixada: rAthena `e985006171d2eb320ee512a653f4c83aea3d81b6` (2026-08-21), Renewal, PACKETVER 20220330.

Este repositório é a área de trabalho controlada para consolidar a localização PT-BR sem substituir scripts antigos sobre o upstream atual. O Episode 18 permanece fora do alvo; o conteúdo máximo é Episode 17.2.

## Regra de merge
- upstream fixado = esqueleto/estrutura;
- traduções antigas = referência de strings;
- preservar IDs, labels, variáveis, nomes de mapas, constantes e lógica;
- nomes internos de instância permanecem técnicos quando necessários à sincronização;
- textos visíveis ao jogador são localizados em PT-BR;
- um episódio só é fechado após auditoria de resíduos e validação estrutural.

## Critério obrigatório de fechamento 100%
Um episódio só pode ser declarado 100% concluído quando passar, sem pendências, por todas as etapas abaixo:
- tradução completa de todo o conteúdo visível ao jogador;
- pente-fino minucioso de revisão linguística e estrutural;
- busca e correção de resíduos de inglês ou outros idiomas não previstos;
- validação de encoding e correção de caracteres corrompidos/mojibake;
- verificação de referências internas, preservando IDs, labels, variáveis, nomes de mapas, constantes, chamadas e lógica;
- verificação residual final para confirmar que nenhuma pendência linguística, estrutural ou funcional relacionada à tradução permaneceu.

Regra fixa: se qualquer uma dessas etapas encontrar pendência, o episódio permanece aberto e não pode ser marcado como 100%.

## Ordem de fechamento
17.2 → 17.1 → 16.2 → 16.1 → anteriores.
