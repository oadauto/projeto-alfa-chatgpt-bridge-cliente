"""Ponto de entrada CLI deste cliente.

Dois modos:

1. `--simular` (padrão recomendado): nenhuma chamada real, apenas mostra
   os parâmetros que seriam usados.
2. `--confirmar-chamada-real`: dispara UMA chamada real à Responses API,
   restrita EXCLUSIVAMENTE à ferramenta `consultar_estado_ponte` (não
   aceita nenhuma outra ferramenta - a restrição é fixa no código, não
   um parâmetro de linha de comando). Exige aprovação humana explícita
   (digitada no terminal) antes de a ferramenta MCP ser de fato chamada,
   por causa de `require_approval: "always"`. Não implementa nenhuma
   outra ferramenta, não chama OpenRouter, não acessa Notion, e nunca
   imprime a resposta integral da API - só um resumo truncado do
   resultado da ferramenta.

Segredos: lidos exclusivamente do Gerenciador de Credenciais do Windows
(credenciais `ProjetoAlfa-OpenAI` e `ProjetoAlfa-Render-MCP`) - ver
`credenciais_windows.py`. Nada de variável de ambiente, argumento de
linha de comando ou arquivo.

Uso (modo simulado - credenciais já devem estar salvas no Gerenciador
de Credenciais do Windows, mas nenhuma chamada real é feita):
    python -m chatgpt_bridge_cliente.executar_local --simular

Uso (chamada real única, restrita a consultar_estado_ponte):
    python -m chatgpt_bridge_cliente.executar_local --confirmar-chamada-real
"""

from __future__ import annotations

import argparse
import sys

from . import cliente_responses


def _mascarar(presente: bool) -> str:
    """Nunca recebe nem retorna o segredo em si - só para confirmar, em
    mensagens ao usuário, que uma credencial foi encontrada no
    Gerenciador de Credenciais do Windows, sem revelar seu conteúdo."""
    return "<encontrada>" if presente else "<ausente ou erro ao ler>"


def rodar_simulacao() -> int:
    """Monta os parâmetros da chamada (sem executá-la) e simula, com
    dados fictícios, o ciclo de aprovação humana - só para demonstrar e
    validar o fluxo, sem nenhuma chamada de rede real.

    Confirma que as credenciais existem no Gerenciador de Credenciais do
    Windows (só presença/ausência - nunca imprime o valor)."""
    from . import credenciais_windows

    print("=== Modo simulado (dry-run) - nenhuma chamada real será feita ===")

    for nome_credencial, funcao_leitura in (
        (credenciais_windows.NOME_CREDENCIAL_OPENAI, credenciais_windows.obter_chave_openai),
        (credenciais_windows.NOME_CREDENCIAL_TOKEN_MCP_REMOTO, credenciais_windows.obter_token_mcp_remoto),
    ):
        try:
            funcao_leitura()
            presente = True
        except credenciais_windows.SegredoAusenteError:
            presente = False
        print(f"Credencial '{nome_credencial}': {_mascarar(presente)}")

    definicao_ferramenta = {
        "type": "mcp",
        "server_label": cliente_responses.NOME_ROTULO_FERRAMENTA_MCP,
        "server_url": cliente_responses.URL_SERVIDOR_MCP_REMOTO,
        "headers": {"Authorization": "Bearer <oculto>"},
        "allowed_tools": list(cliente_responses.FERRAMENTAS_PERMITIDAS),
        "require_approval": "always",
    }

    print("\nDefinição da ferramenta MCP que seria enviada à Responses API:")
    for chave, valor in definicao_ferramenta.items():
        print(f"  {chave}: {valor}")

    print(
        "\nEm uma chamada real, a Responses API retornaria um item "
        "'mcp_approval_request' antes de qualquer execução de ferramenta - "
        "este cliente nunca aprova essa chamada automaticamente. A "
        "aprovação humana explícita (fora deste script) seria necessária "
        "para prosseguir, via cliente_responses.responder_aprovacao(...)."
    )
    print(
        "\nNenhuma chamada real foi feita à OpenAI nem ao servidor MCP "
        "remoto. Modo simulado concluído."
    )
    return 0


# Fixo - a chamada real desta CLI nunca usa outra ferramenta. Não é lido
# de argumento de linha de comando nem de variável de ambiente.
FERRAMENTA_UNICA_CHAMADA_REAL = "consultar_estado_ponte"


def rodar_chamada_real_restrita() -> int:
    """Executa a ÚNICA chamada real autorizada: uma chamada à Responses
    API restrita exclusivamente a `consultar_estado_ponte`, com
    aprovação humana obrigatória antes da execução da ferramenta MCP.

    Para no primeiro erro ou recusa - nunca tenta de novo sozinha, nunca
    aprova sozinha, nunca chama outra ferramenta."""
    print("=== Chamada real única - restrita exclusivamente a 'consultar_estado_ponte' ===")
    print(f"Servidor MCP remoto: {cliente_responses.URL_SERVIDOR_MCP_REMOTO}")
    print(f"Ferramenta única permitida nesta chamada: {FERRAMENTA_UNICA_CHAMADA_REAL}")

    try:
        resposta = cliente_responses.executar_chamada_real_restrita(
            instrucao_usuario=(
                "Chame a ferramenta MCP 'consultar_estado_ponte' e devolva o "
                "resultado. Não chame nenhuma outra ferramenta."
            ),
            ferramenta_unica=FERRAMENTA_UNICA_CHAMADA_REAL,
        )
    except cliente_responses.SegredoAusenteError as erro:
        print(f"Erro (credencial ausente, nome apenas): {erro}")
        return 1
    except Exception as erro:  # noqa: BLE001 - parar imediatamente diante de qualquer erro, conforme regra
        status = cliente_responses.status_code_erro(erro)
        mensagem = cliente_responses.mensagem_sanitizada_erro(erro)
        print(
            "Erro na chamada à Responses API - parando imediatamente. "
            f"Tipo: {type(erro).__name__}; status_code: {status}; mensagem (sanitizada): {mensagem}"
        )
        return 1

    if not cliente_responses.resposta_tem_pedido_de_aprovacao(resposta):
        print(
            "A resposta não trouxe nenhum pedido de aprovação MCP "
            "(mcp_approval_request). Por segurança (regra: aprovação humana "
            "sempre exigida), parando sem prosseguir."
        )
        return 1

    pedido_aprovacao = next(
        (item for item in (getattr(resposta, "output", None) or []) if getattr(item, "type", None) == "mcp_approval_request"),
        None,
    )
    nome_ferramenta_solicitada = getattr(pedido_aprovacao, "name", None)

    if nome_ferramenta_solicitada != FERRAMENTA_UNICA_CHAMADA_REAL:
        print(
            f"A ferramenta solicitada ('{nome_ferramenta_solicitada}') não é a "
            f"única autorizada ('{FERRAMENTA_UNICA_CHAMADA_REAL}'). Parando sem aprovar."
        )
        return 1

    print(f"\nPedido de aprovação MCP recebido: ferramenta='{nome_ferramenta_solicitada}', id='{pedido_aprovacao.id}'")
    decisao = input("Aprovar esta chamada MCP real? Digite exatamente 'sim' para aprovar: ")

    if decisao.strip().lower() != "sim":
        print("Chamada não aprovada. Parando sem executar a ferramenta MCP.")
        return 1

    try:
        resultado_final = cliente_responses.responder_aprovacao(
            id_pedido_aprovacao=pedido_aprovacao.id,
            aprovado=True,
            resposta_anterior_id=resposta.id,
        )
    except Exception as erro:  # noqa: BLE001 - parar imediatamente diante de qualquer erro
        status = cliente_responses.status_code_erro(erro)
        mensagem = cliente_responses.mensagem_sanitizada_erro(erro)
        print(
            "Erro ao enviar aprovação - parando imediatamente. "
            f"Tipo: {type(erro).__name__}; status_code: {status}; mensagem (sanitizada): {mensagem}"
        )
        return 1

    resumo = cliente_responses.resumir_resultado_ferramenta(resultado_final)
    print("\nResultado da ferramenta MCP (RESUMO, não a resposta integral da API):")
    print(resumo)
    print("\nFim. Nenhuma outra ferramenta foi chamada. Parando conforme regra.")
    return 0


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description="Cliente ChatGPT/Codex -> servidor MCP remoto do Projeto ALFA (Responses API)."
    )
    grupo = analisador.add_mutually_exclusive_group(required=True)
    grupo.add_argument(
        "--simular",
        action="store_true",
        help="Roda o fluxo em modo simulado (dry-run), sem nenhuma chamada real.",
    )
    grupo.add_argument(
        "--confirmar-chamada-real",
        action="store_true",
        help=(
            "Dispara UMA chamada real, restrita exclusivamente a "
            "'consultar_estado_ponte', com aprovação humana obrigatória."
        ),
    )
    argumentos = analisador.parse_args(argv)

    if argumentos.simular:
        return rodar_simulacao()

    return rodar_chamada_real_restrita()


if __name__ == "__main__":
    sys.exit(main())
