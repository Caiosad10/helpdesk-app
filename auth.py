"""Auth local: usuarios + sessoes simples por token."""
from __future__ import annotations
import hashlib
import json
import os
import secrets
import sqlite3
import time

ARQ_USUARIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usuarios.json")
# [VERSIONAMENTO] Credenciais de TESTE ficam versionadas em usuarios.exemplo.json
# (nunca em usuarios.json, que tem as senhas reais e esta no .gitignore).
ARQ_EXEMPLO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usuarios.exemplo.json")
# [CLAUDE 25/09] Sessoes saem da memoria (dict SESSOES, 12h) e vao pro helpdesk.db:
# logout travado de verdade — reiniciar o servidor ou passar 12h nao desloga mais
# ninguem. Sessao so morre por logout (com senha) ou exclusao do usuario.
ARQ_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpdesk.db")
_TABELA_OK = False


def _con() -> sqlite3.Connection:
    global _TABELA_OK
    con = sqlite3.connect(ARQ_DB)
    if not _TABELA_OK:
        con.execute("CREATE TABLE IF NOT EXISTS sessoes("
                    "token TEXT PRIMARY KEY, usuario TEXT NOT NULL, criado_em REAL NOT NULL)")
        con.commit()
        _TABELA_OK = True
    return con


def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


def _usuarios_padrao() -> dict:
    """[VERSIONAMENTO] Semente de usuarios: le `usuarios.exemplo.json` (versionado,
    so com credenciais de teste) para criar o `usuarios.json` na primeira execucao.
    Fallback fixo se o arquivo de exemplo nao existir (mesmos logins de teste)."""
    try:
        with open(ARQ_EXEMPLO, encoding="utf-8") as f:
            modelo = json.load(f)
        if isinstance(modelo, dict) and modelo:
            return modelo
    except Exception:
        pass
    return {
        "ti": {"senha": _hash("ti123"), "papel": "ti", "nome": "TI - Teste"},
        "maria": {"senha": _hash("1234"), "papel": "func", "nome": "Maria"},
        "joao": {"senha": _hash("1234"), "papel": "func", "nome": "Joao"},
    }


def carregar_usuarios() -> dict:
    if not os.path.exists(ARQ_USUARIOS):
        padrao = _usuarios_padrao()
        with open(ARQ_USUARIOS, "w", encoding="utf-8") as f:
            json.dump(padrao, f, ensure_ascii=False, indent=2)
        return padrao
    with open(ARQ_USUARIOS, encoding="utf-8") as f:
        return json.load(f)


def validar_login(usuario: str, senha: str) -> dict | None:
    users = carregar_usuarios()
    u = (usuario or "").strip().lower()
    reg = users.get(u)
    if not reg or reg.get("senha") != _hash(senha or ""):
        return None
    return {"usuario": u, "papel": reg.get("papel", "func"), "nome": reg.get("nome", u)}


def criar_sessao(info: dict) -> str:
    token = secrets.token_hex(16)
    con = _con()
    try:
        con.execute("INSERT INTO sessoes(token, usuario, criado_em) VALUES(?,?,?)",
                    (token, info["usuario"], time.time()))
        con.commit()
    finally:
        con.close()
    return token


def get_sessao(token: str) -> dict | None:
    # papel/nome vem do usuarios.json a cada chamada (mudanca vale na hora).
    if not token:
        return None
    con = _con()
    try:
        row = con.execute("SELECT usuario FROM sessoes WHERE token=?", (token,)).fetchone()
    finally:
        con.close()
    if not row:
        return None
    reg = carregar_usuarios().get(row[0])
    if not reg:
        invalidar_sessao(token)
        return None
    return {"usuario": row[0], "papel": reg.get("papel", "func"), "nome": reg.get("nome", row[0])}


# [MUSE 24/09] v1.1: gestao de usuarios pelo TI (criar/excluir) + logout com senha.
# Usuarios ficam em usuarios.json (mesmo arquivo do login). Sessoes em memoria.
def _salvar_usuarios(users: dict) -> None:
    with open(ARQ_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def listar_usuarios() -> list[dict]:
    """Lista sem hash (p/ tela de gestao do TI)."""
    users = carregar_usuarios()
    return [
        {"usuario": u, "papel": r.get("papel", "func"), "nome": r.get("nome", u)}
        for u, r in sorted(users.items())
    ]


def _validar_novo(usuario: str, senha: str, papel: str, nome: str) -> str:
    u = (usuario or "").strip().lower()
    if len(u) < 3 or len(u) > 20:
        raise ValueError("Usuario deve ter 3-20 caracteres")
    if not all(ch.isalnum() or ch in "._-" for ch in u):
        raise ValueError("Usuario so aceita letras, numeros, ponto, _ ou -")
    if len(senha or "") < 4:
        raise ValueError("Senha deve ter ao menos 4 caracteres")
    if papel not in ("func", "ti"):
        raise ValueError("Papel invalido (func ou ti)")
    if not (nome or "").strip():
        raise ValueError("Nome vazio")
    return u


def criar_usuario(usuario: str, senha: str, papel: str, nome: str) -> dict:
    users = carregar_usuarios()
    u = _validar_novo(usuario, senha, papel, nome)
    if u in users:
        raise ValueError("Usuario ja existe")
    users[u] = {"senha": _hash(senha), "papel": papel, "nome": nome.strip()}
    _salvar_usuarios(users)
    return {"usuario": u, "papel": papel, "nome": nome.strip()}


def excluir_usuario(usuario: str) -> dict:
    users = carregar_usuarios()
    u = (usuario or "").strip().lower()
    reg = users.get(u)
    if not reg:
        raise ValueError("Usuario nao encontrado")
    if reg.get("papel") == "ti":
        n_ti = sum(1 for r in users.values() if r.get("papel") == "ti")
        if n_ti <= 1:
            raise ValueError("Nao pode excluir o ultimo TI")
    del users[u]
    _salvar_usuarios(users)
    # derruba sessoes do usuario excluido
    con = _con()
    try:
        con.execute("DELETE FROM sessoes WHERE usuario=?", (u,))
        con.commit()
    finally:
        con.close()
    return {"ok": True}


def verificar_senha(usuario: str, senha: str) -> bool:
    users = carregar_usuarios()
    u = (usuario or "").strip().lower()
    reg = users.get(u)
    return bool(reg) and reg.get("senha") == _hash(senha or "")


def invalidar_sessao(token: str) -> None:
    con = _con()
    try:
        con.execute("DELETE FROM sessoes WHERE token=?", (token or "",))
        con.commit()
    finally:
        con.close()
