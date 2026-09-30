"""Telas: home, novo chamado, detalhe."""
import flet as ft
from theme import BG, CARD, CARD_BORDA, VERDE, BRANCO, CINZA_TEXTO, CINZA_SUBTIL, VERMELHO, MOTIVOS, STATUS_OPCOES, campo_estilo
from models import ChamadoStore
from ui import appbar, badge, card, borda, pad

STORE = ChamadoStore()


def ir(page: ft.Page, rota: str):
    """Navega trocando page.route e disparando o handler do main (sync, sem async)."""
    page.route = rota
    if page.on_route_change:
        page.on_route_change(None)


def avisar(page: ft.Page, texto: str, cor: str = "#2A2A2A"):
    sb = ft.SnackBar(ft.Text(texto, color="#FFFFFF"), bgcolor=cor)
    page.overlay.append(sb)
    sb.open = True
    page.update()


def home(page: ft.Page) -> ft.View:
    busca = ft.TextField(hint_text="Buscar motivo, descricao, usuario ou #id...", prefix_icon=ft.Icons.SEARCH, **campo_estilo())
    fst = ft.Dropdown(value="Todos", options=[ft.dropdown.Option(s) for s in ["Todos", *STATUS_OPCOES]], **campo_estilo())
    lista = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    cont = ft.Text("", color=CINZA_SUBTIL, size=12)

    def abrir(cid):
        ir(page, f"/detalhe/{cid}")

    def excluir(cid):
        STORE.excluir(cid)
        avisar(page, "Chamado excluido")
        recarregar()

    def recarregar():
        itens = STORE.filtrar(busca.value or "", fst.value or "Todos")
        lista.controls.clear()
        if not itens:
            lista.controls.append(ft.Container(padding=40, alignment=ft.Alignment.CENTER, content=ft.Column([
                ft.Icon(ft.Icons.INBOX_OUTLINED, size=56, color=CARD_BORDA),
                ft.Text("Nenhum chamado aqui", color=BRANCO, weight=ft.FontWeight.W_700),
                ft.Text("Toque no + para abrir o primeiro.", color=CINZA_SUBTIL, size=13),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)))
        else:
            for c in itens:
                lista.controls.append(card(c, abrir, excluir))
        cont.value = f"{len(itens)} chamado(s) - toque num card p/ detalhes"
        page.update()

    busca.on_change = lambda e: recarregar()
    fst.on_change = lambda e: recarregar()

    header = ft.Container(
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=["#1DB954", "#0E5C2A"]),
        border_radius=18, padding=18,
        content=ft.Column([
            ft.Text("Ola!", color="#06240F", size=13, weight=ft.FontWeight.W_700),
            ft.Text("Meus chamados", color="#06240F", size=24, weight=ft.FontWeight.W_800),
            ft.Text("Suporte estilo Spotify: rapido, escuro e verde.", color="#06240F", size=12),
        ], spacing=4),
    )
    recarregar()
    return ft.View(
        route="/", bgcolor=BG, appbar=appbar("HelpDesk"),
        floating_action_button=ft.FloatingActionButton(icon=ft.Icons.ADD, bgcolor=VERDE, foreground_color="#0B0B0B", on_click=lambda e: ir(page, "/novo")),
        controls=[ft.Container(padding=pad(14, 10), expand=True, content=ft.Column([header, busca, fst, cont, lista], spacing=10))])


def novo(page: ft.Page) -> ft.View:
    usuario = ft.TextField(label="Seu nome", value="Rafael", prefix_icon=ft.Icons.PERSON_OUTLINE, **campo_estilo())
    motivo = ft.Dropdown(label="Motivo", value=MOTIVOS[0], options=[ft.dropdown.Option(m) for m in MOTIVOS], **campo_estilo())
    desc = ft.TextField(label="Descreva o problema", multiline=True, min_lines=4, max_lines=6, **campo_estilo())

    def ok(e):
        if not (desc.value or "").strip():
            desc.error_text = "Descreva o problema rapidinho"
            page.update()
            return
        STORE.adicionar(usuario.value, motivo.value, desc.value)
        avisar(page, "Chamado aberto com sucesso!", VERDE)
        ir(page, "/")

    return ft.View(route="/novo", bgcolor=BG, appbar=appbar("Novo chamado", voltar=lambda e: ir(page, "/")),
        controls=[ft.Container(padding=16, content=ft.Column([
            ft.Text("Abrir chamado", size=22, weight=ft.FontWeight.W_800, color=BRANCO),
            ft.Text("Conta pra gente o que esta acontecendo.", color=CINZA_SUBTIL, size=13),
            usuario, motivo, desc,
            ft.ElevatedButton("Confirmar chamado", icon=ft.Icons.CHECK_CIRCLE_OUTLINE, bgcolor=VERDE, color="#0B0B0B", on_click=ok),
            ft.OutlinedButton("Cancelar", on_click=lambda e: ir(page, "/")),
        ], spacing=12))])


def detalhe(page: ft.Page, cid: int) -> ft.View:
    c = STORE.obter(cid)
    if not c:
        return ft.View(route="/", bgcolor=BG, appbar=appbar("HelpDesk"), controls=[ft.Text("Nao encontrado", color=BRANCO)])
    dd = ft.Dropdown(value=c.status, options=[ft.dropdown.Option(s) for s in STATUS_OPCOES], **campo_estilo())

    def salvar(e):
        STORE.status(c.id, dd.value)
        avisar(page, f"Status -> {dd.value}")
        ir(page, "/")

    def excluir(e):
        STORE.excluir(c.id)
        ir(page, "/")

    return ft.View(route=f"/detalhe/{c.id}", bgcolor=BG, appbar=appbar(f"Chamado #{c.id}", voltar=lambda e: ir(page, "/")),
        controls=[ft.Container(padding=16, content=ft.Column([
            ft.Container(bgcolor=CARD, border=borda(), border_radius=16, padding=16,
                content=ft.Column([
                    ft.Row([ft.Text(c.motivo, size=18, weight=ft.FontWeight.W_800, color=BRANCO, expand=True), badge(c.status)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(c.descricao, color=CINZA_TEXTO),
                    ft.Divider(color=CARD_BORDA),
                    ft.Text(f"Aberto por {c.usuario} - {c.criado_em}", color=CINZA_SUBTIL, size=12),
                ], spacing=10)),
            ft.Text("Alterar status", color=BRANCO, weight=ft.FontWeight.W_700),
            dd,
            ft.ElevatedButton("Salvar status", bgcolor=VERDE, color="#0B0B0B", on_click=salvar),
            ft.OutlinedButton("Excluir chamado", icon=ft.Icons.DELETE_OUTLINE, on_click=excluir),
        ], spacing=12))])
