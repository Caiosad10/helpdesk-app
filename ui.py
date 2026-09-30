"""Cards, appbar e widgets reutilizáveis."""
import flet as ft
from theme import BG, CARD, CARD_BORDA, VERDE, BRANCO, CINZA_TEXTO, CINZA_SUBTIL, cor_status


def borda(cor=CARD_BORDA, larg=1):
    lado = ft.BorderSide(larg, cor)
    return ft.Border(top=lado, bottom=lado, left=lado, right=lado)


def pad(h=8, v=4):
    return ft.Padding(left=h, right=h, top=v, bottom=v)


def snack(page: ft.Page, texto: str, cor: str = "#2A2A2A"):
    """SnackBar unica reutilizada (evita acumular overlay)."""
    sb = getattr(page, "_sb", None)
    if sb is None:
        sb = ft.SnackBar(ft.Text("", color="#FFFFFF"), bgcolor=cor)
        page.overlay.append(sb)
        page._sb = sb
    sb.content = ft.Text(texto, color="#FFFFFF")
    sb.bgcolor = cor
    sb.open = True
    page.update()


def badge(st):
    return ft.Container(ft.Text(st, size=11, weight=ft.FontWeight.W_700, color="#0B0B0B"), bgcolor=cor_status(st), padding=pad(), border_radius=20)


def card(c, on_abrir, on_excluir, pode_excluir=True, rotulo_abrir="Abrir >",
         acao=None, rotulo_acao=None, fantasma=False):
    # Botao ABRIR separado (evita clique duplo lixeira+card do bug antigo)
    # [MUSE 22/09] Fase 1: rotulo adaptavel — TI "Abrir >", func "Editar".
    # [MUSE 22/09] Acao primaria inline (fluxo sem abrir detalhe):
    #   func+Tratado -> "Confirmar - foi resolvido!" (fecha);
    #   TI+Aberto -> "Iniciar tratativa"; TI+Em atendimento -> "Finalizar tratativa";
    #   TI+Tratado -> fantasma "Aguardando confirmacao" (igual mobile, so recarrega).
    # [MUSE 23/09] Pente-fino: fantasma=OutlineButton (moderno, intuitivo, sem regra nova).
    linha_btns = ft.Row(spacing=6, controls=[
        ft.TextButton(rotulo_abrir, on_click=lambda e: on_abrir(c.id)),
    ])
    if pode_excluir:
        linha_btns.controls.append(
            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=CINZA_SUBTIL, icon_size=20, tooltip="Excluir", on_click=lambda e: on_excluir(c.id))
        )
    extras = []
    if acao and rotulo_acao:
        if fantasma:
            extras.append(ft.OutlinedButton(rotulo_acao, on_click=lambda e: acao(c.id)))
        else:
            extras.append(ft.FilledButton(rotulo_acao, style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"),
                                          on_click=lambda e: acao(c.id)))
    return ft.Container(
        bgcolor=CARD, border=borda(), border_radius=16, padding=14,
        content=ft.Column(spacing=8, controls=[
            ft.Row([ft.Text(f"#{c.id} - {c.motivo}", weight=ft.FontWeight.W_700, color=BRANCO, size=14, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS), badge(c.status)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(c.descricao, color=CINZA_TEXTO, size=13, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            *extras,
            ft.Row([
                ft.Row([ft.Icon(ft.Icons.ACCOUNT_CIRCLE_OUTLINED, size=16, color=CINZA_SUBTIL), ft.Text(f"{c.usuario} - {c.criado_em}", size=12, color=CINZA_SUBTIL)], spacing=6),
                linha_btns,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ]),
    )


def appbar(titulo, voltar=None, nome="?", sair=None, sino=None, gestao=None):
    acts = []
    if gestao is not None:
        acts.append(gestao)
    if sino is not None:
        acts.append(sino)
    if sair:
        acts.append(ft.IconButton(ft.Icons.LOGOUT, icon_color=CINZA_SUBTIL, tooltip=f"Sair ({nome})", on_click=sair))
    acts.append(ft.Container(ft.Icon(ft.Icons.SUPPORT_AGENT, color=VERDE), bgcolor="#1A1A1A", width=40, height=40, border_radius=20, alignment=ft.Alignment.CENTER, margin=ft.Margin(right=8)))
    return ft.AppBar(
        title=ft.Text(titulo, weight=ft.FontWeight.W_800, color=VERDE, size=20),
        center_title=False, bgcolor="#0B0B0B",
        leading=ft.IconButton(ft.Icons.ARROW_BACK, icon_color=BRANCO, on_click=voltar) if voltar else None,
        actions=acts,
    )


# [CLAUDE 25/09] Experimento de design (pos v1.1): barra inferior na home.
# Func: BottomAppBar com recorte (notch) onde o FAB "+" encaixa no centro.
# TI: sem FAB, BottomAppBar com cantos superiores arredondados.
COR_BARRA = "#1A1A1A"


def item_barra(icone, rotulo, on_click=None, ativo=False, controle=None):
    """Icone + legenda pequena. `controle` substitui o IconButton (ex: sino c/ badge)."""
    cor = VERDE if ativo else CINZA_SUBTIL
    btn = controle or ft.IconButton(icone, icon_color=cor, tooltip=rotulo, on_click=on_click)
    return ft.Column([btn, ft.Text(rotulo, size=10, color=cor, weight=ft.FontWeight.W_600)],
                     spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)


def barra_inferior(esquerda, direita=None, notch=False):
    """notch=True: deixa um vao central p/ o FAB (CENTER_DOCKED) e recorta a barra.
    notch=False: itens distribuidos e cantos de cima arredondados."""
    if notch:
        itens = [*esquerda, ft.Container(width=56), *(direita or [])]
    else:
        itens = [*esquerda, *(direita or [])]
    return ft.BottomAppBar(
        bgcolor=COR_BARRA, height=76, padding=ft.Padding(left=8, right=8, top=0, bottom=0),
        shape=ft.CircularRectangleNotchShape() if notch else None, notch_margin=6,
        border_radius=None if notch else ft.BorderRadius.vertical(top=24),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Row(itens, alignment=ft.MainAxisAlignment.SPACE_AROUND,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )
