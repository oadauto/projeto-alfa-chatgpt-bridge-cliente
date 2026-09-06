"""projeto-alfa-chatgpt-bridge-cliente

Cliente separado (NÃO faz parte do servidor MCP) que consome o servidor
MCP remoto do Projeto ALFA (projeto-alfa-openrouter-bridge-mcp, já
publicado no Render) a partir do ChatGPT/Codex, via OpenAI Responses
API - usando o tipo de ferramenta nativo "mcp" da Responses API, não a
Chat Completions API.

Escopo desta etapa: SOMENTE modo simulado (dry-run). Nenhuma chamada
real à OpenAI nem ao servidor MCP remoto é feita pelo código deste
pacote nesta versão - ver `executar_local.py`.
"""

from __future__ import annotations

__version__ = "0.1.0-simulado"
