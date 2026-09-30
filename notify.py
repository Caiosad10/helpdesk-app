"""Toast popup canto superior + som + sino de notificacoes."""
import time
import flet as ft
from theme import CARD, CARD_BORDA, BRANCO, CINZA_TEXTO, VERDE
from ui import borda


def bleep(page: ft.Page):
    """Som curto no desktop (Windows). No mobile/web fica silencioso."""
    try:
        import winsound
        page.run_thread(lambda: winsound.MessageBeep(winsound.MB_ICONASTERISK))
    except Exception:
        pass


def toast(page: ft.Page, titulo: str, texto: str, cor: str = "#1DB954", dur_ms: int = 4500):
    """Popup topo-direita com auto-dismiss. Tambem registra no sino (1 som por fato)."""
    try:
        hist = getattr(page, "_hd_notifs", None)
        if hist is None:
            hist = []
            page._hd_notifs = hist
        hist.insert(0, {"titulo": titulo, "texto": texto, "hora": time.strftime("%H:%M")})
        del hist[20:]
        bdg = getattr(page, "_hd_badge", None)
        if bdg is not None:
            try:
                bdg.value = str(len(hist))
                bdg.visible = True
                bdg_bg = getattr(page, "_hd_badge_bg", None)
                if bdg_bg is not None:
                    bdg_bg.visible = True
            except Exception:
                pass
    except Exception:
        pass
    box = ft.Container(
        bgcolor=CARD, border=borda(), border_radius=14, padding=12, width=330,
        shadow=ft.BoxShadow(blur_radius=18, color="#00000088"),
        content=ft.Column(spacing=4, controls=[
            ft.Row(spacing=8, controls=[
                ft.Container(width=10, height=10, border_radius=5, bgcolor=cor),
                ft.Text(titulo, weight=ft.FontWeight.W_800, color=BRANCO, size=14, expand=True),
                ft.IconButton(ft.Icons.CLOSE, icon_size=16, icon_color=CINZA_TEXTO, on_click=lambda e: fechar()),
            ]),
            ft.Text(texto, color=CINZA_TEXTO, size=12),
        ]),
    )

    def fechar():
        try:
            page.overlay.remove(box)
            page.update()
        except Exception:
            pass

    async def auto():
        import asyncio
        await asyncio.sleep(dur_ms / 1000)
        fechar()

    page.overlay.append(box)
    box.top = 10
    box.right = 10
    bleep(page)
    page.update()
    page.run_task(auto)


def sino_button(page: ft.Page):
    hist0 = getattr(page, "_hd_notifs", None) or []
    badge = ft.Text(str(len(hist0)), size=10, weight=ft.FontWeight.W_800, color="#0B0B0B", visible=bool(hist0))
    badge_bg = ft.Container(badge, bgcolor=VERDE, width=18, height=18, border_radius=9,
                            alignment=ft.Alignment.CENTER, visible=bool(hist0))
    page._hd_badge = badge
    page._hd_badge_bg = badge_bg

    def abrir(e):
        hist = list(getattr(page, "_hd_notifs", []) or [])
        linhas = []
        if not hist:
            linhas.append(ft.Text("Nenhuma notificacao recente.", color=CINZA_TEXTO, size=12))
        for n in hist[:20]:
            linhas.append(ft.Container(
                bgcolor="#1A1A1A", border=borda(), border_radius=10, padding=8,
                content=ft.Column(spacing=2, controls=[
                    ft.Text("%s - %s" % (n.get("titulo", ""), n.get("hora", "")), color=BRANCO, size=12, weight=ft.FontWeight.W_700),
                    ft.Text(n.get("texto", ""), color=CINZA_TEXTO, size=12),
                ])))
        dlg = ft.AlertDialog(
            title=ft.Text("Notificacoes recentes", color=BRANCO, weight=ft.FontWeight.W_800),
            content=ft.Container(width=340, height=380, content=ft.Column(linhas, scroll=ft.ScrollMode.AUTO, spacing=8)),
            actions=[ft.TextButton("Limpar", on_click=lambda e2: limpar(dlg)),
                     ft.TextButton("Fechar", on_click=lambda e2: fechar_dlg(dlg))],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def fechar_dlg(dlg):
        dlg.open = False
        page.update()

    def limpar(dlg):
        page._hd_notifs = []
        try:
            badge.value = "0"
            badge.visible = False
            badge_bg.visible = False
        except Exception:
            pass
        dlg.open = False
        page.update()

    return ft.Stack([
        ft.IconButton(ft.Icons.NOTIFICATIONS_OUTLINED, icon_color=BRANCO, tooltip="Notificacoes", on_click=abrir),
        ft.Container(badge_bg, top=2, right=2),
    ])
