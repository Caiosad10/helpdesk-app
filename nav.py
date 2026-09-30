"""Navegacao + login (v1.1: logout com senha + sessao persistente no aparelho)."""
import json

import flet as ft
from theme import BG, CARD, VERDE, BRANCO, CINZA_TEXTO, campo_estilo
from ui import appbar, borda, snack
from api import (SESSAO, SESSAO_CAIU, api_login, api_logout, api_me,
                 api_verificar_senha, online)

# [CLAUDE 25/09] Sessao persistente: token salvo no aparelho via ft.SharedPreferences
# (desktop: arquivo local do app; PWA: localStorage). page._hd_prefs e criado no
# main.py. Abrir/recarregar o app nao desloga mais — so o Sair com senha.
CHAVE_SESSAO = "helpdesk.sessao"


def lembrar_sessao(page: ft.Page):
    prefs = getattr(page, "_hd_prefs", None)
    if prefs is None or not SESSAO.get("token"):
        return
    dados = json.dumps({k: SESSAO.get(k) for k in ("token", "usuario", "papel", "nome")})

    async def _salvar():
        try:
            await prefs.set(CHAVE_SESSAO, dados)
        except Exception:
            pass
    page.run_task(_salvar)


def esquecer_sessao(page: ft.Page):
    prefs = getattr(page, "_hd_prefs", None)
    if prefs is None:
        return

    async def _apagar():
        try:
            await prefs.remove(CHAVE_SESSAO)
        except Exception:
            pass
    page.run_task(_apagar)


async def restaurar_sessao(page: ft.Page) -> bool:
    """Le o token salvo e valida no /me. True = SESSAO preenchida.
    Servidor fora do ar mantem a sessao salva (o app tem modo offline);
    so 401 (logout/usuario excluido) apaga o token."""
    prefs = getattr(page, "_hd_prefs", None)
    if prefs is None:
        return False
    try:
        bruto = await prefs.get(CHAVE_SESSAO)
    except Exception:
        return False
    if not bruto:
        return False
    try:
        dados = json.loads(bruto)
        token = dados["token"]
    except Exception:
        esquecer_sessao(page)
        return False
    try:
        info = api_me(token)
    except Exception:
        info = {k: dados.get(k) for k in ("usuario", "papel", "nome")}
    if info is None:
        esquecer_sessao(page)
        return False
    SESSAO.clear()
    SESSAO.update(info)
    SESSAO["token"] = token
    SESSAO_CAIU["v"] = False
    preparar_sessao(page)
    lembrar_sessao(page)  # atualiza nome/papel salvos
    return True


def sessao_caiu(page: ft.Page) -> bool:
    """Chamado pelo polling/gestao: se o servidor devolveu 401 (usuario excluido,
    sessao derrubada), apaga o token salvo e volta pro login com aviso."""
    if not SESSAO_CAIU["v"]:
        return False
    SESSAO_CAIU["v"] = False
    esquecer_sessao(page)

    # adiado: pode ser chamado no meio da montagem de uma View (dentro do rc() do
    # main.py) — navegar ali reentraria no rc() e empilharia a tela velha por cima.
    async def _ir_login():
        ir(page, "/login")
        snack(page, "Sua sessão foi encerrada. Entre novamente.")
    page.run_task(_ir_login)
    return True


def preparar_sessao(page: ft.Page):
    """Zera o estado por janela ao entrar (login ou sessao restaurada)."""
    page._hd_poll = {"v": 0, "ids": set(), "notificados": set()}
    page._hd_notifs = []
    # [CLAUDE 22/09] cache do P1 (page._hd_cache/_hd_foto) nao era limpo no
    # login: trocar de usuario na MESMA janela do Flet deixava a lista antiga
    # (de outro papel/dono) visivel ate o proximo ciclo de 3s da thread de
    # polling. home.py: filtrados() so busca de novo se o cache estiver vazio,
    # entao limpar aqui forca um fetch fresco e corretamente filtrado.
    page._hd_cache = []
    page._hd_foto = None
    # [CLAUDE 23/09] mesma lacuna do _hd_cache, agora pra fila de toasts do
    # produtor-consumidor (Muse, 22/09): _tst() roda pra sempre por janela e
    # nao sabe de troca de usuario — sem isso, um toast que sobrou da sessao
    # anterior (ex: "Novo chamado!" ainda nao drenado) podia aparecer pro
    # PROXIMO usuario que logar na mesma janela. Achado do Muse (Ponto 4).
    page._hd_toasts = []
    try:
        if getattr(page, "_hd_badge", None) is not None:
            page._hd_badge.value = "0"
            page._hd_badge.visible = False
            page._hd_badge_bg.visible = False
    except Exception:
        pass


def ir(page: ft.Page, rota: str):
    page.route = rota
    if page.on_route_change:
        page.on_route_change(None)


def sair(page: ft.Page):
    # [MUSE 24/09] v1.1: logout travado — botao continua visivel, mas sair exige
    # a senha do proprio usuario logado (so o TI sabe, pois cadastrou e logou na
    # maquina). Modal valida no servidor; invalida o token de verdade.
    eu = SESSAO.get("nome", "?")
    pwd = ft.TextField(label="Sua senha", password=True, can_reveal_password=True,
                       prefix_icon=ft.Icons.LOCK_OUTLINE, **campo_estilo())
    msg = ft.Text("", color="#E53935", size=13)

    def confirmar(e):
        if not api_verificar_senha(pwd.value or ""):
            msg.value = "Senha incorreta — logout bloqueado."
            page.update()
            return
        try:
            dlg.open = False
        except Exception:
            pass
        try:
            api_logout()
        except Exception:
            SESSAO.clear()
        esquecer_sessao(page)
        ir(page, "/login")

    def cancelar(e):
        try:
            dlg.open = False
        except Exception:
            pass
        page.update()

    dlg = ft.AlertDialog(
        modal=True, title=ft.Text(f"Sair ({eu})?"),
        content=ft.Column([ft.Text("Digite sua senha para confirmar o logout.",
                                   color=CINZA_TEXTO, size=13), pwd, msg], spacing=8, tight=True),
        actions=[ft.TextButton("Cancelar", on_click=cancelar),
                 ft.FilledButton("Sair", style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"),
                                 on_click=confirmar)],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


def tela_login(page: ft.Page) -> ft.View:
    user = ft.TextField(label="Usuário", hint_text="Seu usuário da empresa", prefix_icon=ft.Icons.PERSON_OUTLINE, **campo_estilo())
    pwd = ft.TextField(label="Senha", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK_OUTLINE, **campo_estilo())
    msg = ft.Text("", color="#E53935", size=13)

    def entrar(e):
        try:
            info = api_login((user.value or "").strip(), pwd.value or "")
            preparar_sessao(page)
            lembrar_sessao(page)
            snack(page, f"Bem-vindo, {info['nome']}!", VERDE)
            ir(page, "/")
        except Exception as ex:
            msg.value = f"{ex} (servidor {'ON' if online() else 'OFF'})"
            page.update()

    return ft.View(
        route="/login", bgcolor=BG, appbar=appbar("HelpDesk"),
        controls=[ft.Container(padding=20, content=ft.Column([
            ft.Container(
                gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=["#1DB954", "#0E5C2A"]),
                border_radius=18, padding=20,
                content=ft.Column([
                    ft.Icon(ft.Icons.SUPPORT_AGENT, size=40, color="#06240F"),
                    ft.Text("HelpDesk", color="#06240F", size=26, weight=ft.FontWeight.W_800),
                    ft.Text("Entre com seu usuário da empresa.", color="#06240F", size=13),
                ], spacing=6),
            ),
            user, pwd, msg,
            ft.FilledButton("Entrar", icon=ft.Icons.LOGIN, style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"), on_click=entrar),
            ft.Container(bgcolor=CARD, border=borda(), border_radius=12, padding=12,
                content=ft.Text("Use seu usuário e senha da empresa.", color=CINZA_TEXTO, size=12)),
        ], spacing=12))],
    )
