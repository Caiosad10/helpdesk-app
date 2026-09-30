"""t12 — valida a tela /gestao v1.1 (hub + drill-down) com Page falso.

Cobre: (a) hub navega pras 2 rotas; (b) so TI entra; (c) REGRA DO DONO:
"Tem certeza?" so quando a exclusao e possivel — com chamado em aberto / motivo
em uso, o snack de bloqueio aparece e NENHUM dialogo de confirmacao abre;
(d) modal de criar abre e o Criar chama a API certa; (e) rotas registradas no
main.py. Rodar: python t12_gestao.py
[CLAUDE 25/09] + contadores no hub, 1 api_listar por recarga, "(voce)" sem lixeira,
lixeira apagada quando bloqueada, busca, validacao/sugestao de login no modal.
"""
import types
import flet as ft
import gestao as G
from api import SESSAO

RES = []


def ok(cond, nome):
    print(("PASS" if cond else "FAIL"), "-", nome)
    RES.append(bool(cond))


class FakePage:
    def __init__(self, rota="/gestao"):
        self.route = rota
        self.views = []
        self.overlay = []
        self.on_route_change = lambda e=None: None
        self.on_view_pop = None
        self._hd_cache = []
        self._hd_notifs = []
        self._sb = None

    def update(self):
        pass

    def run_task(self, fn, *a):
        self.tarefas = getattr(self, "tarefas", []) + [fn]


def walk(c):
    """Percorre controles Flet (controls/content/actions/...)."""
    yield c
    for a in ("controls", "actions"):
        v = getattr(c, a, None)
        if isinstance(v, list):
            for x in v:
                if isinstance(x, ft.Control):
                    yield from walk(x)
    for a in ("content", "title", "leading"):
        v = getattr(c, a, None)
        if isinstance(v, ft.Control):
            yield from walk(v)


def chams(usuario, status, motivo="M"):
    return types.SimpleNamespace(usuario=usuario, status=status, motivo=motivo)


def lixeiras_de(v):
    return [c for c in walk(v) if isinstance(c, ft.IconButton) and c.data == "lixeira"]


def textos(v):
    return [c.value for c in walk(v) if isinstance(c, ft.Text)]


def clicar(ctrl):
    ctrl.on_click(types.SimpleNamespace()) if ctrl.on_click else None


def rotulo(b):
    """Texto de um Button no Flet 1.0 (fica em _values['content'])."""
    v = getattr(b, "_values", None)
    return v.get("content") if isinstance(v, dict) else None


# ---------- 1) hub navega + so TI entra ----------
SESSAO.clear()
SESSAO.update(papel="ti", nome="TI Teste", usuario="ti", token="x")
G.api_listar_usuarios = lambda: [{"usuario": "ti", "papel": "ti", "nome": "TI"}] * 3
G.api_motivos = lambda estrito=False: ["A", "B"]
p = FakePage()
v = G.gestao(p)
ok("3" in textos(v) and "2" in textos(v), "hub: contadores 3 usuarios / 2 motivos")
ok(v.route == "/gestao", "hub: rota /gestao")
cards = [c for c in walk(v) if isinstance(c, ft.Container) and c.on_click]
ok(len(cards) == 2, "hub: 2 cards clicaveis")
clicar(cards[0])
ok(p.route == "/gestao/usuarios", "hub: card 1 -> /gestao/usuarios")
clicar(cards[1])
ok(p.route == "/gestao/motivos", "hub: card 2 -> /gestao/motivos")

SESSAO["papel"] = "func"
ok(G.gestao(FakePage()).appbar.title.value == "Sem acesso", "func: hub negado")
ok(G.gestao_usuarios(FakePage()).route == "/gestao/usuarios", "func: /gestao/usuarios negado")
ok(G.gestao_motivos(FakePage()).route == "/gestao/motivos", "func: /gestao/motivos negado")

# ---------- 2) /gestao/usuarios: regra da exclusao condicional ----------
SESSAO.clear()
SESSAO.update(papel="ti", nome="TI Teste", usuario="ti", token="x")

snacks = []
G.snack = lambda page, texto, cor=None: snacks.append(texto)
G.api_listar_usuarios = lambda: [
    {"usuario": "ana", "papel": "func", "nome": "Ana"},
    {"usuario": "bia", "papel": "func", "nome": "Bia"},
    {"usuario": "ti", "papel": "ti", "nome": "TI Teste"},
]
n_listar = []


def _listar():
    n_listar.append(1)
    return [chams("ana", "Aberto"), chams("ana", "Fechado"), chams("bia", "Fechado")]


G.api_listar = _listar

p = FakePage("/gestao/usuarios")
v = G.gestao_usuarios(p)
lixeiras = lixeiras_de(v)
ok(len(lixeiras) == 2, "usuarios: 2 lixeiras (o proprio TI nao tem)")
ok(len(n_listar) == 1, "usuarios: 1 api_listar por recarga (3 usuarios)")
ok("(você)" in textos(v), "usuarios: marca '(você)' no proprio card")
ok(lixeiras[0].icon_color == G.COR_LIXEIRA_BLOQ and "Bloqueado" in lixeiras[0].tooltip,
   "usuarios: lixeira apagada c/ tooltip quando tem aberto")
ok(lixeiras[1].icon_color == G.COR_LIXEIRA and lixeiras[1].tooltip == "Excluir",
   "usuarios: lixeira normal quando pode excluir")

# busca filtra sem novo fetch
busca = [c for c in walk(v) if isinstance(c, ft.TextField)][0]
busca.value = "bi"
busca.on_change(None)
ok("Bia" in textos(v) and "Ana" not in textos(v) and len(n_listar) == 1,
   "usuarios: busca filtra na memoria")
busca.value = ""
busca.on_change(None)

# ana tem chamado em aberto -> bloqueio SEM "Tem certeza?"
n_ov = len(p.overlay)
clicar(lixeiras[0])
ok(len(p.overlay) == n_ov, "usuarios: com aberto -> NAO abre confirmacao")
ok(any("em aberto" in s for s in snacks), "usuarios: com aberto -> mostra snack de bloqueio")

# bia so tem Fechado -> confirmacao aparece
clicar(lixeiras[1])
dlg = p.overlay[-1] if p.overlay else None
ok(isinstance(dlg, ft.AlertDialog) and "Tem certeza" in dlg.content.controls[0].value,
   "usuarios: sem aberto -> abre 'Tem certeza?'")

# criar usuario: modal abre e Criar chama a API com os campos
criados = []
G.api_criar_usuario = lambda u, s, pa, n: criados.append((u, s, pa, n))
p2 = FakePage("/gestao/usuarios")
v2 = G.gestao_usuarios(p2)
novo_btn = [c for c in walk(v2) if isinstance(c, ft.FilledButton) and rotulo(c) == "Novo usuário"][0]
novo_btn.on_click(None)
ok(isinstance(p2.overlay[-1], ft.AlertDialog), "usuarios: modal 'Novo usuario' abre")
dlg2 = p2.overlay[-1]
f_nome, f_user, f_senha, f_papel, _msg = dlg2.content.controls
criar_btn = [c for c in dlg2.actions if isinstance(c, ft.FilledButton) and rotulo(c) == "Criar"][0]
ok(criar_btn.disabled, "usuarios: Criar desabilitado com formulario vazio")
f_nome.value = "Ána Silva"
f_nome.on_change(None)
ok(f_user.value == "ana.silva", "usuarios: login sugerido a partir do nome (sem acento)")
f_senha.value = "12"
f_senha.on_change(None)
ok(criar_btn.disabled and f_senha.error, "usuarios: senha curta -> erro no campo + Criar desabilitado")
f_user.value = "ana silva!"
f_user.on_change(None)
ok(bool(f_user.error), "usuarios: login invalido -> erro no campo")
f_user.value = "ana.silva"
f_user.on_change(None)
f_nome.value = "Ana Silva"
f_nome.on_change(None)
ok(f_user.value == "ana.silva", "usuarios: login digitado a mao nao e sobrescrito")
f_senha.value = "1234"
f_senha.on_change(None)
ok(not criar_btn.disabled, "usuarios: formulario valido -> Criar habilitado")
criar_btn.on_click(None)
ok(criados == [("ana.silva", "1234", "func", "Ana Silva")],
   "usuarios: botao Criar chamou api_criar_usuario")
ok(not dlg2.open, "usuarios: modal fecha apos criar")

# ---------- 3) /gestao/motivos: mesma regra ----------
snacks.clear()
G.api_motivos = lambda estrito=False: ["Impressora", "Sem internet"]
G.api_listar = lambda: [
    chams("ana", "Fechado", "Impressora"),
    chams("bia", "Aberto", "Impressora"),
]
p = FakePage("/gestao/motivos")
v = G.gestao_motivos(p)
lixeiras = lixeiras_de(v)
ok(len(lixeiras) == 2, "motivos: 2 lixeiras na lista")
ok(lixeiras[0].icon_color == G.COR_LIXEIRA_BLOQ, "motivos: lixeira apagada quando em uso")
n_ov = len(p.overlay)
clicar(lixeiras[0])  # Impressora em uso (2 chamados)
ok(len(p.overlay) == n_ov and any("em uso" in s for s in snacks),
   "motivos: em uso -> bloqueio SEM confirmacao")
clicar(lixeiras[1])  # Sem internet sem uso
ok(isinstance(p.overlay[-1], ft.AlertDialog) and
   "Tem certeza" in p.overlay[-1].content.controls[0].value,
   "motivos: sem uso -> abre 'Tem certeza?'")

# criar motivo via modal
criados_m = []
G.api_criar_motivo = lambda nome: criados_m.append(nome)
p2 = FakePage("/gestao/motivos")
v2 = G.gestao_motivos(p2)
novo_btn = [c for c in walk(v2) if isinstance(c, ft.FilledButton) and rotulo(c) == "Novo motivo"][0]
novo_btn.on_click(None)
dlg = p2.overlay[-1]
dlg.content.controls[0].value = "Mouse quebrado"
[c for c in dlg.actions if isinstance(c, ft.FilledButton) and rotulo(c) == "Criar"][0].on_click(None)
ok(criados_m == ["Mouse quebrado"], "motivos: botao Criar chamou api_criar_motivo")

# ---------- 4) rotas registradas no main.py ----------
src = open("main.py", encoding="utf-8").read()
ok("gestao_usuarios" in src and "gestao_motivos" in src, "main.py: importa as views novas")
ok('"/gestao/usuarios"' in src and '"/gestao/motivos"' in src, "main.py: registra as rotas novas")

print()
print(f"TOTAL: {sum(RES)}/{len(RES)} PASS")
raise SystemExit(0 if all(RES) else 1)

