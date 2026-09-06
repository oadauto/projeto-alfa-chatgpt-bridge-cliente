# projeto-alfa-chatgpt-bridge-cliente

Cliente separado do servidor MCP remoto do Projeto ALFA
(`projeto-alfa-openrouter-bridge-mcp`, publicado em
`https://projeto-alfa-openrouter-bridge-mcp.onrender.com/mcp`). Permite
que o ChatGPT/Codex, via **OpenAI Responses API** (não Chat
Completions), use as 3 ferramentas somente leitura desse servidor.

Este pacote **não altera** o servidor MCP remoto - é só um consumidor.

## Escopo desta versão (0.1.0-simulado)

- Somente **modo simulado (dry-run)** está implementado em
  `executar_local.py`. Não existe caminho de código que dispare uma
  chamada real à OpenAI ou ao servidor MCP remoto nesta etapa.
- `allowed_tools` é fixo no código
  (`cliente_responses.FERRAMENTAS_PERMITIDAS`): exatamente
  `listar_modelos_gratuitos`, `selecionar_candidatos`,
  `consultar_estado_ponte`. Não é parametrizável de fora.
- `require_approval` é fixo em `"always"` - toda chamada de ferramenta
  MCP exige uma aprovação humana explícita antes de ser executada
  (via `cliente_responses.responder_aprovacao`, que só deve ser chamada
  depois de uma decisão humana real, fora deste código).
- Segredos (`OPENAI_API_KEY`, `OPENROUTER_BRIDGE_MCP_REMOTE_TOKEN`): só
  por variável de ambiente. Nunca logados, nunca impressos em texto
  puro (nem em mensagens de erro).
- Não acessa Notion. Não usa a chave OpenRouter. Não implementa geração
  OpenRouter nem fallback automático.

## Uso (modo simulado)

```
set OPENAI_API_KEY=alguma-chave
set OPENROUTER_BRIDGE_MCP_REMOTE_TOKEN=algum-token
python -m chatgpt_bridge_cliente.executar_local --simular
```

## Testes

```
pytest tests/ -q
```

Um único arquivo de teste (`test_cliente_simulado.py`), totalmente
mockado - nenhuma chamada de rede real.
