"""Leitura de segredos diretamente do Gerenciador de Credenciais do
Windows (Windows Credential Manager), via `pywin32` (`win32cred`).

Nenhuma chave/token literal existe em código neste pacote - os dois
segredos usados pelo cliente (chave OpenAI e token do servidor MCP
remoto) são lidos, em tempo de execução, das credenciais genéricas já
salvas pelo usuário no Windows:

    ProjetoAlfa-OpenAI
    ProjetoAlfa-Render-MCP

Nenhuma função deste módulo imprime, registra (log) ou salva em disco o
valor de um segredo lido - inclusive em mensagens de erro, que citam
apenas o NOME da credencial, nunca seu conteúdo.
"""

from __future__ import annotations

NOME_CREDENCIAL_OPENAI = "ProjetoAlfa-OpenAI"
NOME_CREDENCIAL_TOKEN_MCP_REMOTO = "ProjetoAlfa-Render-MCP"


class SegredoAusenteError(RuntimeError):
    """A credencial não foi encontrada (ou está vazia) no Gerenciador de
    Credenciais do Windows.

    A mensagem de erro NUNCA inclui o valor de nenhum segredo - apenas o
    nome da credencial não encontrada."""


def _decodificar_blob(blob: bytes) -> str:
    """`CredentialBlob` do Windows Credential Manager normalmente vem em
    UTF-16LE (é como o Credential Manager grava senhas digitadas via
    interface gráfica). Tenta essa decodificação primeiro; cai para
    UTF-8 como alternativa, caso a credencial tenha sido gravada por
    outra ferramenta que já grava em UTF-8/ASCII puro."""
    try:
        texto = blob.decode("utf-16-le")
    except UnicodeDecodeError:
        texto = blob.decode("utf-8")
    return texto.rstrip("\x00")


def obter_segredo_windows(nome_credencial: str) -> str:
    """Lê uma credencial genérica (CRED_TYPE_GENERIC) do Gerenciador de
    Credenciais do Windows pelo nome exato (TargetName).

    Levanta `SegredoAusenteError` (citando só o nome, nunca o valor) se a
    credencial não existir, estiver vazia, ou se `pywin32` não estiver
    disponível neste ambiente (ex.: rodando fora do Windows)."""
    try:
        import win32cred  # import local: só necessário neste caminho, e só existe no Windows
    except ImportError as erro:
        raise SegredoAusenteError(
            "Dependência 'pywin32' (win32cred) não está disponível neste "
            "ambiente - necessária para ler o Gerenciador de Credenciais "
            "do Windows. Instale com 'pip install pywin32'."
        ) from erro

    try:
        credencial = win32cred.CredRead(TargetName=nome_credencial, Type=win32cred.CRED_TYPE_GENERIC)
    except Exception as erro:  # noqa: BLE001 - qualquer falha de leitura vira o mesmo erro genérico, sem detalhes do valor
        raise SegredoAusenteError(
            f"Credencial '{nome_credencial}' não encontrada (ou inacessível) "
            "no Gerenciador de Credenciais do Windows. Confirme que ela foi "
            "salva com esse nome exato (TargetName)."
        ) from erro

    blob = credencial.get("CredentialBlob")
    if not blob:
        raise SegredoAusenteError(f"Credencial '{nome_credencial}' encontrada, mas está vazia.")

    valor = _decodificar_blob(blob)
    if not valor:
        raise SegredoAusenteError(f"Credencial '{nome_credencial}' encontrada, mas está vazia após decodificação.")

    return valor


def obter_chave_openai() -> str:
    return obter_segredo_windows(NOME_CREDENCIAL_OPENAI)


def obter_token_mcp_remoto() -> str:
    return obter_segredo_windows(NOME_CREDENCIAL_TOKEN_MCP_REMOTO)
