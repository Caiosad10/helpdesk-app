"""Sessao logada + API client com polling (tempo real) + fallback offline."""
from __future__ import annotations
from urllib.parse import quote

import httpx
from config import API_URL, API_TIMEOUT
from models import Chamado, ChamadoStore

SESSAO: dict = {}  # {token, usuario, papel, nome}
LOCAL = ChamadoStore()  # cache offline
# [CLAUDE 25/09] Sessao persistente: se o servidor responder 401 com token (usuario
# excluido / sessao derrubada), limpa a SESSAO e marca aqui. nav.sessao_caiu() le
# a marca, apaga o token salvo no aparelho e volta pro login.
SESSAO_CAIU = {"v": False}


def _h():
    t = SESSAO.get("token")
    return {"X-Token": t} if t else {}


def _marca_401(r) -> None:
    if r.status_code == 401 and SESSAO.get("token"):
        SESSAO.clear()
        SESSAO_CAIU["v"] = True


def _erro(r, padrao: str) -> None:
    # [CLAUDE 25/09] Sobe o "detail" do servidor em vez do texto do httpx
    # ("Client error '403 Forbidden' for url ...") que aparecia no modal.
    if r.status_code < 400:
        return
    _marca_401(r)
    try:
        detalhe = r.json().get("detail") or padrao
    except Exception:
        detalhe = padrao
    raise RuntimeError(str(detalhe))


def _c(d: dict) -> Chamado:
    d = dict(d)
    d.pop("versao", None)
    d.pop("atualizado_em", None)
    # [MUSE 22/09] observacao (auditoria TI) nao existe no model offline — descarta aqui.
    d.pop("observacao", None)
    return Chamado(**{k: d.get(k) for k in ("id", "usuario", "motivo", "descricao", "status", "criado_em")})


def online() -> bool:
    try:
        r = httpx.get(f"{API_URL}/health", timeout=API_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def api_login(usuario: str, senha: str) -> dict:
    r = httpx.post(f"{API_URL}/login", json={"usuario": usuario, "senha": senha}, timeout=API_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(r.json().get("detail", "Falha no login"))
    SESSAO.clear()
    SESSAO.update(r.json())
    SESSAO_CAIU["v"] = False
    LOCAL.carregar()
    return dict(SESSAO)


def api_me(token: str) -> dict | None:
    """[CLAUDE 25/09] Valida um token salvo. None = token morto (401);
    excecao = servidor fora do ar (quem chama decide manter a sessao)."""
    r = httpx.get(f"{API_URL}/me", headers={"X-Token": token}, timeout=API_TIMEOUT)
    if r.status_code == 401:
        return None
    r.raise_for_status()
    return dict(r.json())


def api_listar() -> list[Chamado]:
    try:
        r = httpx.get(f"{API_URL}/chamados", headers=_h(), timeout=API_TIMEOUT)
        _marca_401(r)
        r.raise_for_status()
        return [_c(c) for c in r.json()]
    except Exception:
        LOCAL.carregar()
        if SESSAO.get("papel") == "ti":
            return list(LOCAL.chamados)
        u = SESSAO.get("usuario", "")
        return [c for c in LOCAL.chamados if c.usuario == u]


def api_eventos(desde: int) -> dict:
    r = httpx.get(f"{API_URL}/eventos", params={"desde": desde}, headers=_h(), timeout=API_TIMEOUT)
    _marca_401(r)
    r.raise_for_status()
    j = r.json()
    return {"versao": j.get("versao", desde), "mudancas": [_c(c) for c in j.get("mudancas", [])]}


def api_versao(token: str | None = None) -> int:
    try:
        h = {"X-Token": token} if token else _h()
        r = httpx.get(f"{API_URL}/versao", headers=h, timeout=API_TIMEOUT)
        r.raise_for_status()
        j = r.json()
        # server retorna {"n":..,"v":..} (legado: {"versao":..})
        return int(j.get("v", j.get("versao", 0)))
    except Exception:
        return -1


def api_criar(motivo: str, descricao: str) -> Chamado:
    try:
        r = httpx.post(f"{API_URL}/chamados", json={"motivo": motivo, "descricao": descricao}, headers=_h(), timeout=API_TIMEOUT)
        r.raise_for_status()
        c = _c(r.json())
        LOCAL.chamados.insert(0, c)
        LOCAL.salvar()
        return c
    except Exception as e:
        if "401" in str(e) or "403" in str(e):
            raise
        u = SESSAO.get("usuario", "local")
        return LOCAL.adicionar(u, motivo, descricao)


def api_obter(cid: int) -> Chamado | None:
    try:
        r = httpx.get(f"{API_URL}/chamados/{cid}", headers=_h(), timeout=API_TIMEOUT)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return _c(r.json())
    except Exception:
        return LOCAL.obter(cid)


# [MUSE 22/09] Detalhe completo (inclui observacao do TI p/ auditoria em Fechado).
def api_obter_full(cid: int) -> dict | None:
    try:
        r = httpx.get(f"{API_URL}/chamados/{cid}", headers=_h(), timeout=API_TIMEOUT)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def api_status(cid: int, st: str) -> None:
    r = httpx.patch(f"{API_URL}/chamados/{cid}", json={"status": st}, headers=_h(), timeout=API_TIMEOUT)
    r.raise_for_status()


# [MUSE 22/09] Fase 1: editar motivo/descricao (func: próprio não-Fechado; TI: qualquer não-Fechado).
def api_editar(cid: int, motivo: str | None = None, descricao: str | None = None) -> Chamado:
    r = httpx.put(f"{API_URL}/chamados/{cid}", json={"motivo": motivo, "descricao": descricao}, headers=_h(), timeout=API_TIMEOUT)
    r.raise_for_status()
    return _c(r.json())


def api_obs(cid: int, observacao: str) -> None:
    # [MUSE 22/09] Observacao do TI em chamado Fechado (auditoria). Sem fallback
    # offline: auditoria exige servidor (erro sobe p/ o chamador exibir).
    r = httpx.put(f"{API_URL}/chamados/{cid}/observacao", json={"observacao": observacao}, headers=_h(), timeout=API_TIMEOUT)
    r.raise_for_status()


def api_excluir(cid: int) -> None:
    try:
        r = httpx.delete(f"{API_URL}/chamados/{cid}", headers=_h(), timeout=API_TIMEOUT)
        r.raise_for_status()
    except Exception:
        pass
    LOCAL.excluir(cid)


# ===== v1.1: gestao (TI) + logout com senha =====

# [MUSE 24/09] v1.1: motivos via API (TI gerencia). Fallback p/ lista fixa offline.
def api_motivos(estrito: bool = False) -> list[str]:
    # [CLAUDE 25/09] estrito=True (tela de gestao): erro sobe em vez de cair na
    # lista fixa — senao o TI "gerencia" motivos que nem estao no banco.
    try:
        from theme import MOTIVOS as _FIXOS
    except Exception:
        _FIXOS = []
    try:
        r = httpx.get(f"{API_URL}/motivos", headers=_h(), timeout=API_TIMEOUT)
        _erro(r, "Falha ao listar motivos")
        j = r.json()
        return list(j) if j else list(_FIXOS)
    except Exception:
        if estrito:
            raise
        return list(_FIXOS)


def api_criar_motivo(nome: str) -> None:
    r = httpx.post(f"{API_URL}/motivos", json={"nome": nome}, headers=_h(), timeout=API_TIMEOUT)
    _erro(r, "Falha ao criar motivo")


def api_excluir_motivo(nome: str) -> None:
    r = httpx.delete(f"{API_URL}/motivos/{quote(nome, safe='')}", headers=_h(), timeout=API_TIMEOUT)
    _erro(r, "Falha ao excluir motivo")


def api_listar_usuarios() -> list[dict]:
    r = httpx.get(f"{API_URL}/usuarios", headers=_h(), timeout=API_TIMEOUT)
    _erro(r, "Falha ao listar usuários")
    return list(r.json())


def api_criar_usuario(usuario: str, senha: str, papel: str, nome: str) -> dict:
    r = httpx.post(f"{API_URL}/usuarios",
                   json={"usuario": usuario, "senha": senha, "papel": papel, "nome": nome},
                   headers=_h(), timeout=API_TIMEOUT)
    _erro(r, "Falha ao criar usuário")
    return dict(r.json())


def api_excluir_usuario(usuario: str) -> None:
    r = httpx.delete(f"{API_URL}/usuarios/{quote(usuario, safe='')}", headers=_h(), timeout=API_TIMEOUT)
    _erro(r, "Falha ao excluir usuário")


def api_verificar_senha(senha: str) -> bool:
    # True = senha confere; False = incorreta (sem excecao p/ UX do modal).
    try:
        r = httpx.post(f"{API_URL}/verificar-senha", json={"senha": senha},
                       headers=_h(), timeout=API_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def api_logout() -> None:
    # [MUSE 24/09] v1.1: invalida o token no servidor (logout travado de verdade).
    try:
        httpx.post(f"{API_URL}/logout", headers=_h(), timeout=API_TIMEOUT)
    except Exception:
        pass
    SESSAO.clear()
