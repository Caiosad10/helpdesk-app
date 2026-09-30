"""HelpDesk — Flet + FastAPI local. Rode backend + app."""
import flet as ft
from theme import BG, VERDE
from nav import ir, sair, tela_login, restaurar_sessao
from home import home
from detail import novo, detalhe
from gestao import gestao, gestao_usuarios, gestao_motivos
from api import SESSAO


def main(page: ft.Page):
    page.title = "HelpDesk"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.theme = ft.Theme(color_scheme_seed=VERDE, use_material3=True)
    page.dark_theme = ft.Theme(color_scheme_seed=VERDE, use_material3=True)
    page.window.width = 410
    page.window.height = 860
    page.window.min_width = 360
    page.padding = 0
    # [CLAUDE 25/09] token salvo no aparelho (nav.lembrar/esquecer/restaurar_sessao).
    page._hd_prefs = ft.SharedPreferences()

    def rc(e=None):
        if not SESSAO.get("token") and (page.route or "/login") != "/login":
            page.views.clear()
            page.views.append(tela_login(page))
            page.update()
            return
        page.views.clear()
        r = page.route or ("/" if SESSAO.get("token") else "/login")
        if r == "/login":
            page.views.append(tela_login(page))
        elif r == "/gestao":
            # [MUSE 24/09] v1.1: tela de gestao do TI (usuarios + motivos).
            hv0 = getattr(page, "_hd_home_view", None)
            if hv0 is None or (hv0.route or "/") != "/":
                hv0 = home(page)
                page._hd_home_view = hv0
            page.views.append(hv0)
            page.views.append(gestao(page))
        elif r in ("/gestao/usuarios", "/gestao/motivos"):
            # [MUSE 25/09] drill-down do hub /gestao (mesmo padrao P3 da home).
            hv0 = getattr(page, "_hd_home_view", None)
            if hv0 is None or (hv0.route or "/") != "/":
                hv0 = home(page)
                page._hd_home_view = hv0
            page.views.append(hv0)
            page.views.append(gestao_usuarios(page) if r.endswith("usuarios")
                              else gestao_motivos(page))
        elif r == "/novo":
            # [MUSE 21/09] reuso P3 também no /novo (mesmo motivo do /detalhe/).
            hv0 = getattr(page, "_hd_home_view", None)
            if hv0 is None or (hv0.route or "/") != "/":
                hv0 = home(page)
                page._hd_home_view = hv0
            page.views.append(hv0)
            page.views.append(novo(page))
        elif r.startswith("/detalhe/"):
            try:
                cid = int(r.split("/")[-1])
            except ValueError:
                cid = -1
            # [MUSE 21/09] P3 corrigido (valeu, Claude!): reaproveita a View "/" já
            # montada em vez de chamar home(page) de novo. Antes eu fazia o append
            # ANTES do teste, então a home era sempre recriada e o reuso nunca ocorria.
            hv = getattr(page, "_hd_home_view", None)
            if hv is None or (hv.route or "/") != "/":
                hv = home(page)
                page._hd_home_view = hv
            page.views.append(hv)
            page.views.append(detalhe(page, cid))
        else:
            # [MUSE 21/09] guarda a home atual p/ reuso no /detalhe/ (P3 corrigido).
            hv2 = home(page)
            page._hd_home_view = hv2
            page.views.append(hv2)
        page.update()

    async def vp(e: ft.ViewPopEvent):
        if len(page.views) > 1:
            page.views.pop()
            page.route = page.views[-1].route or "/"
            rc()

    page.on_route_change = rc
    page.on_view_pop = vp
    # [CLAUDE 25/09] Sessao persistente: abre num "carregando" e tenta restaurar o
    # token salvo (/me). Deu certo -> home direto; senao -> login. Timeout pra nunca
    # ficar preso no carregando se o armazenamento do aparelho nao responder.
    page.views.clear()
    page.views.append(ft.View(route="/login", bgcolor=BG, controls=[ft.Container(
        expand=True, alignment=ft.Alignment.CENTER,
        content=ft.ProgressRing(color=VERDE))]))
    page.update()

    async def _inicio():
        import asyncio as _aio
        try:
            ok = await _aio.wait_for(restaurar_sessao(page), timeout=10)
        except Exception:
            ok = False
        page.route = "/" if ok else "/login"
        rc()

    page.run_task(_inicio)


if __name__ == "__main__":
    ft.run(main)
