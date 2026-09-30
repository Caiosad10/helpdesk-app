"""Backend FastAPI — rode no notebook (servidor local da empresa).

    python -m uvicorn server:app --host 0.0.0.0 --port 8000

Banco: SQLite (helpdesk.db) — zero config, backup = copiar 1 arquivo.
Docs automaticas: http://127.0.0.1:8000/docs
"""
from __future__ import annotations
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from auth import (
    validar_login, criar_sessao, get_sessao, listar_usuarios, criar_usuario,
    excluir_usuario, verificar_senha, invalidar_sessao,
)

DB = Path(__file__).with_name("helpdesk.db")

app = FastAPI(title="HelpDesk API", version="1.0")
# [CLAUDE 24/09] Antes: allow_origins=["*"], liberando QUALQUER site da internet a chamar
# essa API (com allow_private_network=True junto, isso derrubava a protecao do proprio
# Chrome contra site publico "pular" pra dentro da rede local -- risco real de phishing
# usando o navegador de alguem na rede da empresa como ponte ate aqui). Trocado por
# allow_origin_regex: so aceita origem que seja o proprio PWA rodando num IP da faixa
# privada (192.168.x.x / 10.x.x.x / 172.16-31.x.x) ou 127.0.0.1, na porta 8553 (onde o
# iniciar_helpdesk.bat serve o build/web) -- nenhum site da internet bate nesse padrao,
# so o proprio app. Continua resiliente a IP mudar via DHCP (nao fixei o IP, so a faixa).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"^http://(127\.0\.0\.1"
        r"|10(?:\.\d{1,3}){3}"
        r"|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"
        r"|192\.168(?:\.\d{1,3}){2}):8553$"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Chrome (Private Network Access) exige confirmacao explicita quando uma pagina
    # servida num endereco/porta chama fetch() pra outro endereco/porta da mesma rede
    # local -- sem isso o preflight volta 400 "Disallowed CORS private-network" e o fetch
    # falha ("Failed to fetch"), mesmo a porta estando acessivel (navegacao direta
    # funciona, so o fetch via JS falha). Foi o caso do PWA (:8553) chamando o backend
    # (:8000) pelo Chrome Android. Agora so vale pra origem que bate no regex acima.
    allow_private_network=True,
)


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS chamados(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              usuario TEXT NOT NULL,
              motivo TEXT NOT NULL,
              descricao TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'Aberto',
              criado_em TEXT NOT NULL,
              versao INTEGER NOT NULL DEFAULT 1,
              atualizado_em TEXT NOT NULL DEFAULT '')"""
        )
        # migra banco antigo sem as colunas novas
        cols = [r[1] for r in con.execute("PRAGMA table_info(chamados)").fetchall()]
        if "versao" not in cols:
            con.execute("ALTER TABLE chamados ADD COLUMN versao INTEGER NOT NULL DEFAULT 1")
        if "atualizado_em" not in cols:
            con.execute("ALTER TABLE chamados ADD COLUMN atualizado_em TEXT NOT NULL DEFAULT ''")
        # [MUSE 22/09] Observacao do TI em chamado Fechado (auditoria). Migracao leve:
        # coluna nova com default '' — banco antigo continua abrindo sem rebuild.
        if "observacao" not in cols:
            con.execute("ALTER TABLE chamados ADD COLUMN observacao TEXT NOT NULL DEFAULT ''")
        # [MUSE 24/09] v1.1: motivos gerenciados pelo TI (criar/excluir). Tabela nova
        # com seed dos 5 motivos originais — banco antigo recebe via CREATE + seed.
        con.execute("""CREATE TABLE IF NOT EXISTS motivos(nome TEXT PRIMARY KEY)""")
        if not con.execute("SELECT COUNT(*) FROM motivos").fetchone()[0]:
            for m in ("Problema com a conexão", "Problema com o site",
                      "Problema com o aplicativo", "Dúvida / suporte geral", "Outro"):
                con.execute("INSERT OR IGNORE INTO motivos(nome) VALUES(?)", (m,))
        con.execute("UPDATE chamados SET status='Tratado' WHERE status='Resolvido'")
        # [MUSE 23/09] Pente-fino: sem seed de exemplo — banco de produção começa
        # vazio (offline mantido: models.py/chamados.json continuam p/ fallback local).


@app.on_event("startup")
def _startup():
    init_db()


# ---- modelos ----
class LoginIn(BaseModel):
    usuario: str
    senha: str


class ChamadoIn(BaseModel):
    motivo: str
    descricao: str


class StatusIn(BaseModel):
    status: str


# [MUSE 22/09] Observacao do TI em chamado Fechado (auditoria). Sem max fixo aqui;
# limite validado no endpoint (500 chars) p/ nao poluir o historico.
class ObsIn(BaseModel):
    observacao: str


# [MUSE 22/09] Fase 1: funcionario pode editar motivo/descricao do proprio chamado
# (corrige erro de abertura). TI pode editar qualquer um. Fechado nunca edita.
class EditarIn(BaseModel):
    motivo: str | None = None
    descricao: str | None = None


def auth(x_token: str | None) -> dict:
    s = get_sessao(x_token or "")
    if not s:
        raise HTTPException(401, "Nao autenticado. Faca login.")
    return s


def auth_ti(x_token: str | None) -> dict:
    # [MUSE 24/09] v1.1: atalho p/ endpoints de gestao (so TI).
    s = auth(x_token)
    if s.get("papel") != "ti":
        raise HTTPException(403, "So o TI acessa")
    return s


def motivos_validos() -> list[str]:
    # [MUSE 24/09] v1.1: motivos vindos da tabela (TI gerencia). Fallback fixo.
    try:
        with db() as con:
            rows = con.execute("SELECT nome FROM motivos ORDER BY nome").fetchall()
        if rows:
            return [r[0] for r in rows]
    except Exception:
        pass
    from theme import MOTIVOS
    return list(MOTIVOS)


@app.get("/", include_in_schema=False)
def raiz():
    return {"app": "HelpDesk API", "mobile": "/mobile", "saude": "/health", "docs": "/docs"}




@app.get("/mobile", response_class=HTMLResponse)
def app_previsto():
    """Interface prevista p/ uso real no celular (mesma regra do desktop)."""
    from pathlib import Path
    return Path(__file__).with_name("mobile.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"ok": True, "db": str(DB.name)}


def _bump(con, cid: int):
    agora = datetime.now().strftime("%d/%m %H:%M")
    con.execute("UPDATE chamados SET versao=(SELECT COALESCE(MAX(versao),0)+1 FROM chamados), atualizado_em=? WHERE id=?", (agora, cid))


@app.get("/versao")
def versao(x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth(x_token)
    with db() as con:
        if s["papel"] == "ti":
            r = con.execute("SELECT COUNT(*) n, COALESCE(MAX(versao),0) v FROM chamados").fetchone()
        else:
            r = con.execute("SELECT COUNT(*) n FROM chamados WHERE usuario=?", (s["usuario"],)).fetchone()
            g = con.execute("SELECT COALESCE(MAX(versao),0) v FROM chamados").fetchone()
            return {"n": r["n"], "v": g["v"]}
        return {"n": r["n"], "v": r["v"]}


@app.get("/eventos")
def eventos(desde: int = 0, x_token: str | None = Header(default=None, alias="X-Token")):
    """Polling: mudancas com versao > desde (limite 50). Cursor versao e GLOBAL."""
    s = auth(x_token)
    with db() as con:
        if s["papel"] == "ti":
            rows = con.execute("SELECT * FROM chamados WHERE versao>? ORDER BY versao ASC LIMIT 50", (desde,)).fetchall()
            vmax = con.execute("SELECT COALESCE(MAX(versao),0) v FROM chamados").fetchone()["v"]
        else:
            rows = con.execute("SELECT * FROM chamados WHERE versao>? AND usuario=? ORDER BY versao ASC LIMIT 50", (desde, s["usuario"])).fetchall()
            vmax = con.execute("SELECT COALESCE(MAX(versao),0) v FROM chamados").fetchone()["v"]  # global: nao pula evento
        return {"versao": vmax, "mudancas": [dict(r) for r in rows]}


@app.post("/login")
def login(d: LoginIn):
    info = validar_login(d.usuario, d.senha)
    if not info:
        raise HTTPException(401, "Usuario ou senha invalidos")
    return {"token": criar_sessao(info), **info}


# [CLAUDE 25/09] Sessao persistente: o app salva o token no aparelho e, ao abrir,
# pergunta aqui quem e o dono dele. 401 = token morto (logout/usuario excluido).
@app.get("/me")
def me(x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth(x_token)
    return {"usuario": s["usuario"], "papel": s["papel"], "nome": s["nome"]}


@app.get("/chamados")
def listar(x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth(x_token)
    with db() as con:
        if s["papel"] == "ti":
            rows = con.execute("SELECT * FROM chamados ORDER BY id DESC").fetchall()
        else:
            rows = con.execute("SELECT * FROM chamados WHERE usuario=? ORDER BY id DESC", (s["usuario"],)).fetchall()
        return [dict(r) for r in rows]


@app.post("/chamados", status_code=201)
def criar(d: ChamadoIn, x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth(x_token)
    # [CLAUDE 22/09] TI nao abre chamado pra si mesmo — so o funcionario cria.
    if s["papel"] == "ti":
        raise HTTPException(403, "TI nao cria chamado, apenas o funcionario")
    if d.motivo not in motivos_validos():
        raise HTTPException(422, "Motivo invalido")
    if not d.descricao.strip():
        raise HTTPException(422, "Descricao vazia")
    with db() as con:
        cur = con.execute(
            "INSERT INTO chamados(usuario,motivo,descricao,status,criado_em,versao,atualizado_em) VALUES(?,?,?,?,?,?,?)",
            (s["usuario"], d.motivo, d.descricao.strip(), "Aberto", datetime.now().strftime("%d/%m %H:%M"), 1, ""),
        )
        cid = cur.lastrowid
        _bump(con, cid)
        return dict(con.execute("SELECT * FROM chamados WHERE id=?", (cid,)).fetchone())


@app.get("/chamados/{cid}")
def obter(cid: int, x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth(x_token)
    with db() as con:
        r = con.execute("SELECT * FROM chamados WHERE id=?", (cid,)).fetchone()
        if not r:
            raise HTTPException(404, "Chamado nao encontrado")
        d = dict(r)
        if s["papel"] != "ti" and d["usuario"] != s["usuario"]:
            raise HTTPException(403, "Sem acesso a este chamado")
        return d


@app.patch("/chamados/{cid}")
def mudar_status(cid: int, d: StatusIn, x_token: str | None = Header(default=None, alias="X-Token")):
    from theme import STATUS_OPCOES
    s = auth(x_token)
    if d.status not in STATUS_OPCOES:
        raise HTTPException(422, "Status invalido")
    with db() as con:
        r = con.execute("SELECT * FROM chamados WHERE id=?", (cid,)).fetchone()
        if not r:
            raise HTTPException(404, "Chamado nao encontrado")
        atual = dict(r)
        # TI: Aberto/Em atendimento/Tratado (nunca fecha direto)
        if s["papel"] == "ti" and d.status == "Fechado":
            raise HTTPException(403, "TI nao fecha: aguarde o usuario Confirmar")
        # Func: só pode Confirmar (Fechar) o próprio Tratado
        if s["papel"] != "ti":
            if atual["usuario"] != s["usuario"]:
                raise HTTPException(403, "Sem acesso")
            if not (atual["status"] == "Tratado" and d.status == "Fechado"):
                raise HTTPException(403, "Voce so pode Confirmar (Fechar) um chamado Tratado")
        con.execute("UPDATE chamados SET status=? WHERE id=?", (d.status, cid))
        _bump(con, cid)
        return dict(con.execute("SELECT * FROM chamados WHERE id=?", (cid,)).fetchone())


# [MUSE 22/09] Fase 1: PUT /chamados/{cid} = editar motivo/descricao.
# [CLAUDE 22/09] Só o funcionario, dono, e nunca Fechado — TI nao edita mais (so muda
# status). De quebra, ordem das checagens corrigida: dono/papel antes de revelar se o
# chamado esta Fechado (antes um func conseguia descobrir que um chamado alheio estava
# Fechado antes mesmo de passar pela checagem de acesso).
@app.put("/chamados/{cid}")
def editar(cid: int, d: EditarIn, x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth(x_token)
    if s["papel"] == "ti":
        raise HTTPException(403, "TI nao edita motivo/descricao, apenas o funcionario")
    with db() as con:
        r = con.execute("SELECT * FROM chamados WHERE id=?", (cid,)).fetchone()
        if not r:
            raise HTTPException(404, "Chamado nao encontrado")
        atual = dict(r)
        if atual["usuario"] != s["usuario"]:
            raise HTTPException(403, "Sem acesso")
        if atual["status"] == "Fechado":
            raise HTTPException(403, "Chamado fechado nao pode ser editado")
        novo_motivo = (d.motivo or atual["motivo"]).strip() or atual["motivo"]
        nova_desc = (d.descricao if d.descricao is not None else atual["descricao"]).strip()
        if novo_motivo not in motivos_validos():
            raise HTTPException(422, "Motivo invalido")
        if not nova_desc:
            raise HTTPException(422, "Descricao vazia")
        con.execute("UPDATE chamados SET motivo=?, descricao=? WHERE id=?", (novo_motivo, nova_desc, cid))
        _bump(con, cid)
        return dict(con.execute("SELECT * FROM chamados WHERE id=?", (cid,)).fetchone())


@app.delete("/chamados/{cid}")
def excluir(cid: int, x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth(x_token)
    with db() as con:
        r = con.execute("SELECT * FROM chamados WHERE id=?", (cid,)).fetchone()
        if not r:
            raise HTTPException(404, "Chamado nao encontrado")
        d = dict(r)
        if s["papel"] != "ti" and d["usuario"] != s["usuario"]:
            raise HTTPException(403, "Sem acesso")
        # [MUSE 22/09] Fase 1: Fechado é histórico — ninguém exclui (TI e func).
        if d["status"] == "Fechado":
            raise HTTPException(403, "Chamado fechado nao pode ser excluido")
        con.execute("DELETE FROM chamados WHERE id=?", (cid,))
        return {"ok": True}


# [MUSE 22/09] Observacao do TI em chamado Fechado (auditoria). Regras:
# só TI, só Fechado, max 500 chars. Gera evento (bump) p/ o app ver em tempo real.
@app.put("/chamados/{cid}/observacao")
def salvar_obs(cid: int, d: ObsIn, x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth(x_token)
    if s["papel"] != "ti":
        raise HTTPException(403, "So o TI registra observacao")
    obs = (d.observacao or "").strip()
    if not obs:
        raise HTTPException(422, "Observacao vazia")
    if len(obs) > 500:
        raise HTTPException(422, "Observacao muito longa (max 500)")
    with db() as con:
        r = con.execute("SELECT * FROM chamados WHERE id=?", (cid,)).fetchone()
        if not r:
            raise HTTPException(404, "Chamado nao encontrado")
        atual = dict(r)
        if atual["status"] != "Fechado":
            raise HTTPException(403, "Observacao so em chamado Fechado")
        con.execute("UPDATE chamados SET observacao=? WHERE id=?", (obs, cid))
        _bump(con, cid)
        return dict(con.execute("SELECT * FROM chamados WHERE id=?", (cid,)).fetchone())


# ===== v1.1: gestao (TI) + logout com senha =====

class UsuarioIn(BaseModel):
    usuario: str
    senha: str
    papel: str = "func"
    nome: str = ""


class MotivoIn(BaseModel):
    nome: str


class SenhaIn(BaseModel):
    senha: str


# [MUSE 24/09] v1.1: TI lista usuarios (sem hash) p/ tela de gestao.
@app.get("/usuarios")
def listar_usuarios_ep(x_token: str | None = Header(default=None, alias="X-Token")):
    auth_ti(x_token)
    return listar_usuarios()


# [MUSE 24/09] v1.1: TI cria usuario (papel func ou ti).
@app.post("/usuarios", status_code=201)
def criar_usuario_ep(d: UsuarioIn, x_token: str | None = Header(default=None, alias="X-Token")):
    auth_ti(x_token)
    try:
        return criar_usuario(d.usuario, d.senha, d.papel, d.nome or d.usuario)
    except ValueError as ex:
        raise HTTPException(422, str(ex))


# [MUSE 24/09] v1.1: TI exclui usuario. Bloqueia se tem chamado em aberto
# ou se e o ultimo TI (a checagem de ultimo TI esta em auth.excluir_usuario).
@app.delete("/usuarios/{nome}")
def excluir_usuario_ep(nome: str, x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth_ti(x_token)
    # [CLAUDE 25/09] TI excluindo a si mesmo derrubava a propria sessao na hora.
    if (nome or "").strip().lower() == s["usuario"]:
        raise HTTPException(403, "Você não pode excluir a si mesmo")
    with db() as con:
        n = con.execute(
            "SELECT COUNT(*) FROM chamados WHERE usuario=? AND status!='Fechado'",
            ((nome or "").strip().lower(),)).fetchone()[0]
    if n:
        raise HTTPException(403, "Usuario possui chamados em aberto")
    try:
        return excluir_usuario(nome)
    except ValueError as ex:
        raise HTTPException(422, str(ex))


# [MUSE 24/09] v1.1: motivos — lista p/ qualquer logado (dropdowns).
@app.get("/motivos")
def listar_motivos(x_token: str | None = Header(default=None, alias="X-Token")):
    auth(x_token)
    return motivos_validos()


# [MUSE 24/09] v1.1: TI cria motivo novo.
@app.post("/motivos", status_code=201)
def criar_motivo(d: MotivoIn, x_token: str | None = Header(default=None, alias="X-Token")):
    auth_ti(x_token)
    nome = (d.nome or "").strip()
    if len(nome) < 3 or len(nome) > 60:
        raise HTTPException(422, "Motivo deve ter 3-60 caracteres")
    with db() as con:
        try:
            con.execute("INSERT INTO motivos(nome) VALUES(?)", (nome,))
        except Exception:
            raise HTTPException(422, "Motivo ja existe")
    return {"nome": nome}


# [MUSE 24/09] v1.1: TI exclui motivo. Bloqueia se esta em uso (historico).
# [CLAUDE 25/09] {nome:path}: "Dúvida / suporte geral" tem "/" e dava 404.
@app.delete("/motivos/{nome:path}")
def excluir_motivo(nome: str, x_token: str | None = Header(default=None, alias="X-Token")):
    auth_ti(x_token)
    nome = (nome or "").strip()
    with db() as con:
        n = con.execute("SELECT COUNT(*) FROM chamados WHERE motivo=?", (nome,)).fetchone()[0]
        if n:
            raise HTTPException(403, "Motivo em uso por chamados")
        cur = con.execute("DELETE FROM motivos WHERE nome=?", (nome,))
        if not cur.rowcount:
            raise HTTPException(404, "Motivo nao encontrado")
    return {"ok": True}


# [MUSE 24/09] v1.1: logout invalida o token no servidor (logout travado).
@app.post("/logout")
def logout_ep(x_token: str | None = Header(default=None, alias="X-Token")):
    invalidar_sessao(x_token or "")
    return {"ok": True}


# [MUSE 24/09] v1.1: confere a senha do usuario logado (modal de logout).
@app.post("/verificar-senha")
def verificar_senha_ep(d: SenhaIn, x_token: str | None = Header(default=None, alias="X-Token")):
    s = auth(x_token)
    if not verificar_senha(s["usuario"], d.senha or ""):
        raise HTTPException(403, "Senha incorreta")
    return {"ok": True}
