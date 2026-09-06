"""Montagem da chamada à OpenAI Responses API com a ferramenta MCP remota.

Usa exclusivamente a Responses API (não Chat Completions), com o tipo de
ferramenta nativo "mcp" (conecta diretamente a um servidor MCP remoto via
URL + headers, sem precisar de um cliente MCP customizado).

Regras fixas neste módulo, não configuráveis por parâmetro externo:
- `allowed_tools`: exatamente as 3 ferramentas somente leitura do
  servidor MCP remoto do Projeto ALFA. Nenhuma ferramenta a mais nunca é
  liberada por este cliente, mesmo que o servidor remoto exponha outras
  no futuro.
- `require_approval`: sempre "always" - a Responses API então retorna um
  item `mcp_approval_request` em vez de executar a ferramenta, e requer
  uma segunda chamada explícita (`responder_aprovacao`) para prosseguir.
  Este módulo nunca aprova uma chamada sozinho.

Segredos (chave OpenAI e token do servidor MCP remoto): lidos
EXCLUSIVAMENTE do Gerenciador de Credenciais do Windows (ver
`credenciais_windows.py`), pelos nomes de credencial `ProjetoAlfa-OpenAI`
e `ProjetoAlfa-Render-MCP`. Nenhuma chave/token literal existe em código
neste módulo, e nenhuma função aqui aceita segredo por variável de
ambiente, argumento de linha de comando ou arquivo. Nenhuma função deste
módulo registra (log/print) o valor de nenhum dos dois - nem mesmo em
caso de erro (as exceções reexportadas de `credenciais_windows` nunca
incluem o valor do segredo na mensagem, só o nome da credencial).
"""

from __future__ import annotations

import re
from typing import Any

from .credenciais_windows import (
    NOME_CREDENCIAL_OPENAI,
    NOME_CREDENCIAL_TOKEN_MCP_REMOTO,
    SegredoAusenteError,
    obter_chave_openai,
    obter_token_mcp_remoto,
)

URL_SERVIDOR_MCP_REMOTO = "https://projeto-alfa-openrouter-bridge-mcp.onrender.com/mcp"

# Fixo - as 3 ferramentas somente leitura do servidor MCP remoto do
# Projeto ALFA. Não é um valor default sobrescrevível: nenhuma função
# deste módulo aceita um `allowed_tools` diferente deste.
FERRAMENTAS_PERMITIDAS: tuple[str, ...] = (
    "listar_modelos_gratuitos",
    "selecionar_candidatos",
    "consultar_estado_ponte",
)

NOME_ROTULO_FERRAMENTA_MCP = "ponte_openrouter_alfa"

__all__ = [
    "URL_SERVIDOR_MCP_REMOTO",
    "FERRAMENTAS_PERMITIDAS",
    "NOME_ROTULO_FERRAMENTA_MCP",
    "NOME_CREDENCIAL_OPENAI",
    "NOME_CREDENCIAL_TOKEN_MCP_REMOTO",
    "SegredoAusenteError",
    "montar_definicao_ferramenta_mcp",
    "montar_definicao_ferramenta_mcp_restrita",
    "montar_parametros_requisicao",
    "executar_chamada_real",
    "executar_chamada_real_restrita",
    "resposta_tem_pedido_de_aprovacao",
    "responder_aprovacao",
    "resumir_resultado_ferramenta",
    "status_code_erro",
    "mensagem_sanitizada_erro",
]

_PADRAO_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_PADRAO_CABECALHO_AUTORIZACAO = re.compile(r"(?i)authorization['\"]?\s*[:=]\s*['\"]?[^,'\"\}\s]+")


def montar_definicao_ferramenta_mcp() -> dict[str, Any]:
    """Monta o bloco de ferramenta "mcp" da Responses API, apontando para
    o servidor MCP remoto do Projeto ALFA.

    Lê o token do servidor MCP remoto do Gerenciador de Credenciais do
    Windows (credencial `ProjetoAlfa-Render-MCP`) - nunca o inclui em
    nenhum retorno de função de log/depuração, só no dicionário de
    headers que vai diretamente para a chamada HTTP da biblioteca
    oficial da OpenAI.
    """
    token_mcp_remoto = obter_token_mcp_remoto()

    return {
        "type": "mcp",
        "server_label": NOME_ROTULO_FERRAMENTA_MCP,
        "server_url": URL_SERVIDOR_MCP_REMOTO,
        "headers": {
            "Authorization": f"Bearer {token_mcp_remoto}",
        },
        "allowed_tools": list(FERRAMENTAS_PERMITIDAS),
        "require_approval": "always",
    }


def montar_definicao_ferramenta_mcp_restrita(ferramenta_unica: str) -> dict[str, Any]:
    """Variante MAIS restritiva de `montar_definicao_ferramenta_mcp`: em
    vez das 3 ferramentas permitidas, libera exatamente 1 - usada para
    uma chamada real pontual, autorizada para uma única ferramenta
    específica (ex.: `consultar_estado_ponte`). Nunca amplia o conjunto
    de `FERRAMENTAS_PERMITIDAS`, só restringe ainda mais."""
    if ferramenta_unica not in FERRAMENTAS_PERMITIDAS:
        raise ValueError(
            f"Ferramenta '{ferramenta_unica}' não está entre as permitidas: {FERRAMENTAS_PERMITIDAS}."
        )

    definicao = montar_definicao_ferramenta_mcp()
    definicao["allowed_tools"] = [ferramenta_unica]
    return definicao


def montar_parametros_requisicao(instrucao_usuario: str, modelo: str = "gpt-5") -> dict[str, Any]:
    """Monta o corpo completo (dict) da chamada `client.responses.create(...)`,
    sem executá-la. Função pura, fácil de testar sem rede.

    `instrucao_usuario` é o texto de entrada (`input`) para a Responses
    API - por exemplo, a pergunta ou tarefa que o ChatGPT/Codex quer
    resolver usando a ponte OpenRouter remota como ferramenta.
    """
    if not isinstance(instrucao_usuario, str) or not instrucao_usuario.strip():
        raise ValueError("instrucao_usuario é obrigatório e deve ser uma string não vazia.")

    return {
        "model": modelo,
        "input": instrucao_usuario,
        "tools": [montar_definicao_ferramenta_mcp()],
    }


def executar_chamada_real(instrucao_usuario: str, modelo: str = "gpt-5") -> Any:
    """Executa de fato a chamada à Responses API (rede real).

    NÃO é chamada por `executar_local.py` nesta etapa - só existe para
    uma etapa futura, autorizada separadamente, quando uma chamada real
    for explicitamente aprovada. Import da biblioteca `openai` é feito
    localmente (dentro da função) para que nada neste pacote precise da
    dependência instalada apenas para rodar em modo simulado."""
    from openai import OpenAI  # import local: só necessário neste caminho de chamada real

    chave_openai = obter_chave_openai()
    parametros = montar_parametros_requisicao(instrucao_usuario, modelo=modelo)

    cliente = OpenAI(api_key=chave_openai)
    return cliente.responses.create(**parametros)


def executar_chamada_real_restrita(instrucao_usuario: str, ferramenta_unica: str, modelo: str = "gpt-5") -> Any:
    """Como `executar_chamada_real`, mas usando
    `montar_definicao_ferramenta_mcp_restrita` - a única forma, neste
    módulo, de fazer uma chamada real limitada a 1 ferramenta específica
    (nunca mais que isso). Usada para a chamada real única, autorizada
    caso a caso, restrita a `consultar_estado_ponte`.

    `store=False` - a Responses API não retém esta chamada/resposta do
    lado da OpenAI (sem persistência para reuso posterior via
    `previous_response_id` além do necessário ao fluxo de aprovação em
    curso). `max_tool_calls=1` - limite explícito de uma única chamada de
    ferramenta nesta requisição, reforçando (no nível do parâmetro da
    própria API) a mesma garantia de "no máximo 1 chamada" já expressa
    por `allowed_tools` conter só `ferramenta_unica`."""
    from openai import OpenAI  # import local, mesmo motivo de executar_chamada_real

    chave_openai = obter_chave_openai()
    definicao_ferramenta = montar_definicao_ferramenta_mcp_restrita(ferramenta_unica)

    cliente = OpenAI(api_key=chave_openai)
    return cliente.responses.create(
        model=modelo,
        input=instrucao_usuario,
        tools=[definicao_ferramenta],
        store=False,
        max_tool_calls=1,
    )


def resposta_tem_pedido_de_aprovacao(resposta: Any) -> bool:
    """Verifica se a resposta da Responses API contém um item
    `mcp_approval_request` pendente - ou seja, se a ferramenta MCP quer
    ser chamada mas está aguardando aprovação humana (por causa de
    `require_approval: "always"`, fixado acima)."""
    saida = getattr(resposta, "output", None) or []
    return any(getattr(item, "type", None) == "mcp_approval_request" for item in saida)


def responder_aprovacao(
    id_pedido_aprovacao: str,
    aprovado: bool,
    resposta_anterior_id: str,
    modelo: str = "gpt-5",
) -> Any:
    """Envia a decisão humana (aprovar ou negar) de volta à Responses API,
    continuando a conversa a partir de `resposta_anterior_id`.

    Esta função só deve ser chamada depois de uma aprovação humana real
    e explícita (fora deste código) - nunca chama a si mesma
    automaticamente, e não há nenhum caminho neste módulo que aprove uma
    chamada MCP sem essa decisão externa."""
    from openai import OpenAI  # import local, mesmo motivo de executar_chamada_real

    chave_openai = obter_chave_openai()
    cliente = OpenAI(api_key=chave_openai)

    return cliente.responses.create(
        model=modelo,
        previous_response_id=resposta_anterior_id,
        input=[
            {
                "type": "mcp_approval_response",
                "approval_request_id": id_pedido_aprovacao,
                "approve": aprovado,
            }
        ],
    )


def resumir_resultado_ferramenta(resposta_final: Any) -> str:
    """Extrai um RESUMO curto do resultado da chamada MCP - nunca a
    resposta integral da API (que inclui metadados internos, ids,
    tokens de uso etc.). Regra permanente: não registrar respostas
    integrais.

    Procura o item de saída do tipo "mcp_call" e devolve só uma prévia
    truncada do campo `output` dele. Se a estrutura não for a esperada,
    devolve uma mensagem genérica em vez de despejar o objeto inteiro.
    """
    saida = getattr(resposta_final, "output", None) or []

    for item in saida:
        if getattr(item, "type", None) == "mcp_call":
            saida_ferramenta = getattr(item, "output", None)
            if saida_ferramenta:
                texto = str(saida_ferramenta)
                limite = 500
                if len(texto) > limite:
                    texto = texto[:limite] + "... (truncado - resumo, não resposta integral)"
                return texto
            erro_ferramenta = getattr(item, "error", None)
            if erro_ferramenta:
                return f"A ferramenta MCP retornou erro: {erro_ferramenta}"

    return "Nenhum resultado de chamada de ferramenta MCP (mcp_call) encontrado na resposta."


def status_code_erro(erro: Exception) -> int | None:
    """Extrai `status_code` de um erro da biblioteca `openai` (ex.:
    `APIStatusError`), se existir. Não faz rede, não interpreta nada
    além de um atributo já presente no objeto de exceção."""
    return getattr(erro, "status_code", None)


def mensagem_sanitizada_erro(erro: Exception) -> str:
    """Monta uma mensagem de diagnóstico de erro SEM headers, sem a
    chave OpenAI, sem o token do servidor MCP remoto e sem corpo
    integral de requisição/resposta que possa conter segredo.

    Usa preferencialmente `erro.message` (mensagem curada da biblioteca
    `openai`, tipicamente sem os headers da requisição) em vez de
    `str(erro)`/`erro.body` (que podem ecoar a requisição inteira,
    inclusive o header Authorization enviado ao servidor MCP remoto
    dentro da definição da ferramenta). Mesmo assim, aplica uma
    segunda camada de redação por padrão de texto (qualquer "Bearer
    <valor>" ou "Authorization: <valor>"), e trunca o resultado."""
    texto = getattr(erro, "message", None) or str(erro)

    texto = _PADRAO_BEARER.sub("Bearer <redigido>", texto)
    texto = _PADRAO_CABECALHO_AUTORIZACAO.sub("Authorization: <redigido>", texto)

    limite = 300
    if len(texto) > limite:
        texto = texto[:limite] + "... (truncado)"
    return texto
