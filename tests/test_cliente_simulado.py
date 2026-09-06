"""Único teste essencial (mockado, sem rede real) para o cliente
ChatGPT/Codex, conforme escopo mínimo reduzido:

1. URL do servidor MCP remoto correta;
2. exatamente 3 ferramentas permitidas (allowed_tools);
3. require_approval fixo em "always";
4. nenhuma credencial (token MCP, lido do Gerenciador de Credenciais do
   Windows) exposta em texto puro fora do header de autenticação da
   própria requisição.

A leitura do Gerenciador de Credenciais do Windows é mockada
(monkeypatch) - este teste não acessa o Windows Credential Manager de
verdade nem faz nenhuma chamada de rede.

Testes de cobertura ampliada, handshake aprofundado, desempenho ou
cenários repetidos foram deliberadamente removidos desta fase.
"""

from __future__ import annotations

from chatgpt_bridge_cliente import cliente_responses


def test_definicao_ferramenta_mcp_essencial(monkeypatch):
    monkeypatch.setattr(
        cliente_responses,
        "obter_token_mcp_remoto",
        lambda: "token-ficticio-de-teste",
    )

    definicao = cliente_responses.montar_definicao_ferramenta_mcp()

    # 1. URL correta
    assert definicao["server_url"] == "https://projeto-alfa-openrouter-bridge-mcp.onrender.com/mcp"

    # 2. Exatamente 3 ferramentas permitidas
    assert set(definicao["allowed_tools"]) == {
        "listar_modelos_gratuitos",
        "selecionar_candidatos",
        "consultar_estado_ponte",
    }
    assert len(definicao["allowed_tools"]) == 3

    # 3. Aprovação humana sempre exigida
    assert definicao["require_approval"] == "always"

    # 4. Nenhuma exposição de credencial: só aparece dentro do header
    # Authorization da própria requisição, nunca em texto solto no dict,
    # e a credencial só foi obtida via função de leitura do Gerenciador
    # de Credenciais do Windows (mockada acima), nunca de variável de
    # ambiente ou valor literal no código.
    assert definicao["headers"]["Authorization"] == "Bearer token-ficticio-de-teste"
    valores_fora_do_header = {chave: valor for chave, valor in definicao.items() if chave != "headers"}
    assert "token-ficticio-de-teste" not in repr(valores_fora_do_header)
