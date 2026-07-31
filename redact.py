"""
Utilitario de seguranca: remove segredos de textos antes de exibi-los.

Motivo concreto: a API do Pollinations recebe a chave como parametro de URL
(`?token=...`). Quando a requisicao falha, a excecao do `requests` costuma
incluir a URL inteira — e essa mensagem ia parar em `st.error()` e no
traceback mostrado na tela. Num app publicado na nuvem, isso exibiria a chave
do usuario para quem estivesse olhando.

Este modulo centraliza a limpeza: qualquer texto que va para a interface
passa por `redact()` antes.
"""

from __future__ import annotations

import re

MASCARA = "***REMOVIDO***"

# Padroes genericos de segredo, independentes de qual chave o usuario usa.
_PADROES = [
    # ?token=..., &key=..., ?api_key=..., &apikey=...
    re.compile(r"((?:token|key|api_key|apikey|access_token)=)[^&\s\"']{6,}", re.IGNORECASE),
    # Authorization: Bearer <token>
    re.compile(r"((?:Authorization|Bearer)[:\s]+)[A-Za-z0-9._\-]{10,}", re.IGNORECASE),
    # Formato das chaves do Google AI Studio (AIza + 35 caracteres)
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
]


def redact(texto: str, *segredos: str | None) -> str:
    """
    Devolve `texto` com segredos mascarados.

    - `segredos`: valores exatos conhecidos (as chaves da sessao atual). Sao
      removidos primeiro, cobrindo formatos que os padroes genericos nao
      preveem.
    - Em seguida aplica padroes genericos (token=, Bearer, AIza...), que
      protegem tambem chaves que nunca passaram por aqui.
    """
    if not texto:
        return texto

    resultado = str(texto)

    for segredo in segredos:
        if segredo and len(str(segredo)) >= 6:
            resultado = resultado.replace(str(segredo), MASCARA)

    for padrao in _PADROES:
        if padrao.groups:
            resultado = padrao.sub(rf"\1{MASCARA}", resultado)
        else:
            resultado = padrao.sub(MASCARA, resultado)

    return resultado
