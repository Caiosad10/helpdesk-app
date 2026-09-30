"""Gestao do TI (v1.1): hub drill-down -> /gestao/usuarios e /gestao/motivos."""
import unicodedata

import flet as ft
from theme import (BG, CARD, VERDE, BRANCO, CINZA_TEXTO, CINZA_SUBTIL, AMARELO, AZUL,
                   VERMELHO, campo_estilo)
from ui import appbar, borda, snack, pad
from nav import ir, sair, sessao_caiu
from api import (
    SESSAO, api_listar, api_listar_usuarios, api_criar_usuario, api_excluir_usuario,
    api_motivos, api_criar_motivo, api_excluir_motivo,
)
from notify import sino_button

# [CLAUDE 25/09] lixeira "apagada" = exclusao bloqueada (clicar ainda mostra o snack
# com o motivo, entao a regra do dono segue: "Tem certeza?" so quando da pra excluir).
COR_LIXEIRA = CINZA_TEXTO
COR_LIXEIRA_BLOQ = "#3A3A3A"


def _so_ti(page, rota):
    if SESSAO.get("papel") == "ti":
        return None
    return ft.View(route=rota, bgcolor=BG, appbar=appbar("Sem acesso"),
                   controls=[ft.Container(padding=20, content=ft.Text(
                       "Só o TI acessa esta tela.", color=BRANCO))])


def gestao(page: ft.Page) -> ft.View:
    # [MUSE 25/09] Hub drill-down: 2 cards (Usuarios, Motivos). Scroll p/ caber.
    negado = _so_ti(page, "/gestao")
    if negado:
        return negado
    eu = SESSAO.get("nome", "?")

    # [CLAUDE 25/09] contadores nos cards; servidor OFF -> cards sem numero.
    def _qtd(fn):
        try:
            return len(fn())
        except Exception:
            return None
    n_users = _qtd(api_listar_usuarios)
    n_mots = _qtd(lambda: api_motivos(estrito=True))
    sessao_caiu(page)

    def card_hub(titulo, qtd, subtitulo, icone, rota):
        # [CLAUDE 25/09] contador discreto a direita, antes da seta (a pilula verde
        # ao lado do titulo ficou desproporcional — feedback do dono).
        fim = [ft.Icon(ft.Icons.CHEVRON_RIGHT, color=CINZA_SUBTIL)]
        if qtd is not None:
            fim.insert(0, ft.Text(str(qtd), color=CINZA_TEXTO, size=16, weight=ft.FontWeight.W_600))
        return ft.Container(
            bgcolor=CARD, border=borda(), border_radius=16, padding=18,
            on_click=lambda e: ir(page, rota), ink=True,
            content=ft.Row([
                ft.Container(ft.Icon(icone, color=VERDE, size=30), bgcolor="#1A1A1A",
                             width=56, height=56, border_radius=28, alignment=ft.Alignment.CENTER),
                ft.Column([ft.Text(titulo, color=BRANCO, weight=ft.FontWeight.W_800, size=18),
                           ft.Text(subtitulo, color=CINZA_SUBTIL, size=12)],
                          spacing=4, expand=True),
                ft.Row(fim, spacing=4, tight=True),
            ], spacing=12),
        )

    return ft.View(
        route="/gestao", bgcolor=BG,
        appbar=appbar("Gestão (TI)", voltar=lambda e: ir(page, "/"), nome=eu,
                      sair=lambda e: sair(page), sino=sino_button(page)),
        controls=[ft.Container(padding=16, content=ft.Column([
            card_hub("Usuários", n_users, "Criar, ver e excluir usuários",
                     ft.Icons.PEOPLE_OUTLINE, "/gestao/usuarios"),
            card_hub("Motivos", n_mots, "Criar e excluir motivos de chamado",
                     ft.Icons.LABEL_OUTLINE, "/gestao/motivos"),
        ], spacing=12, scroll=ft.ScrollMode.AUTO))])


def _dlg(page, titulo, campos, texto_ok, on_ok):
    # [MUSE 25/09] Modal generico p/ criar + confirmar exclusao.
    # [CLAUDE 25/09] devolve o botao OK (o modal de Novo usuario o desabilita
    # enquanto o formulario estiver invalido).
    msg = ft.Text("", color=VERMELHO, size=13)

    def ok(e):
        try:
            on_ok()
        except Exception as ex:
            if sessao_caiu(page):
                fechar()
                return
            msg.value = str(ex)
            page.update()
            return
        fechar()

    def fechar():
        try:
            dlg.open = False
        except Exception:
            pass
        page.update()

    btn_ok = ft.FilledButton(texto_ok, style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"),
                             on_click=ok)
    dlg = ft.AlertDialog(
        modal=True, title=ft.Text(titulo),
        content=ft.Column([*campos, msg], spacing=8, tight=True),
        actions=[ft.TextButton("Cancelar", on_click=lambda e: fechar()), btn_ok],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()
    return btn_ok


def _lixeira(bloqueio, on_click):
    """IconButton de excluir. bloqueio = texto do motivo (lixeira apagada) ou None."""
    return ft.IconButton(ft.Icons.DELETE_OUTLINE, data="lixeira", icon_size=20,
                         icon_color=COR_LIXEIRA_BLOQ if bloqueio else COR_LIXEIRA,
                         tooltip=bloqueio or "Excluir", on_click=on_click)


def _erro_lista(page, col, ex):
    if sessao_caiu(page):
        return
    col.controls = [ft.Text(f"Erro: {ex} (servidor OFF?)", color=VERMELHO, size=13)]
    page.update()


def _chamados():
    # 1 fetch por recarga (antes era 1 por usuario/motivo).
    try:
        return list(api_listar())
    except Exception:
        return []


def _sugerir_login(nome: str) -> str:
    # "Ana Silva" -> "ana.silva" (sem acento, so a-z0-9._-, max 20).
    base = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    base = ".".join(base.lower().split())
    return "".join(ch for ch in base if ch.isalnum() or ch in "._-")[:20]


def _erros_usuario(login, nome, senha):
    # Mesmas regras de auth._validar_novo (o servidor continua validando).
    erros = {}
    u = (login or "").strip().lower()
    if not (3 <= len(u) <= 20):
        erros["login"] = "Entre 3 e 20 caracteres"
    elif not all(ch.isalnum() or ch in "._-" for ch in u):
        erros["login"] = "Só letras, números, ponto, _ ou -"
    if not (nome or "").strip():
        erros["nome"] = "Informe o nome"
    if len(senha or "") < 4:
        erros["senha"] = "Mínimo de 4 caracteres"
    return erros


def gestao_usuarios(page: ft.Page) -> ft.View:
    # [MUSE 25/09] Cards nome/@/papel/N abertos + lixeira. "Tem certeza?" so
    # quando valido; com chamado em aberto mostra o bloqueio direto (sem conf.).
    # [CLAUDE 25/09] + busca, chip TI/FUNC, "(você)" sem lixeira, abertos em amarelo.
    negado = _so_ti(page, "/gestao/usuarios")
    if negado:
        return negado
    eu = SESSAO.get("nome", "?")
    eu_login = SESSAO.get("usuario", "")
    col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    estado = {"users": [], "abertos": {}}
    busca = ft.TextField(hint_text="Buscar por nome ou login", prefix_icon=ft.Icons.SEARCH,
                         dense=True, on_change=lambda e: desenhar(), **campo_estilo())

    def chip(papel):
        ti = papel == "ti"
        return ft.Container(
            ft.Text("TI" if ti else "FUNC", size=10, weight=ft.FontWeight.W_800, color="#0B0B0B"),
            bgcolor=AZUL if ti else CINZA_TEXTO, padding=pad(6, 1), border_radius=20)

    def desenhar():
        termo = (busca.value or "").strip().lower()
        linhas = []
        for u in estado["users"]:
            nome_u = u.get("usuario")
            nome_exib = u.get("nome", "?")
            if termo and termo not in nome_u.lower() and termo not in nome_exib.lower():
                continue
            n = estado["abertos"].get(nome_u, 0)
            sou_eu = nome_u == eu_login
            titulo = [ft.Text(nome_exib, color=BRANCO, weight=ft.FontWeight.W_700, size=15),
                      chip(u.get("papel"))]
            if sou_eu:
                titulo.append(ft.Text("(você)", color=VERDE, size=12))
            acao = [] if sou_eu else [_lixeira(
                f"Bloqueado: {n} chamado(s) em aberto" if n else None,
                lambda e, x=nome_u, q=n: pedir_excluir(x, q))]
            linhas.append(ft.Container(
                bgcolor=CARD, border=borda(), border_radius=14, padding=14,
                content=ft.Row([
                    ft.Column([
                        ft.Row(titulo, spacing=6, wrap=True),
                        ft.Text(f"@{nome_u}", color=CINZA_SUBTIL, size=12),
                        ft.Text(f"{n} chamado(s) em aberto" if n else "Nenhum chamado em aberto",
                                color=AMARELO if n else CINZA_TEXTO, size=12),
                    ], spacing=2, expand=True),
                    *acao,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)))
        vazio = "Nenhum usuário encontrado." if termo else "Nenhum usuário."
        col.controls = linhas or [ft.Text(vazio, color=CINZA_SUBTIL, size=13)]
        page.update()

    def recarregar():
        try:
            estado["users"] = api_listar_usuarios()
        except Exception as ex:
            _erro_lista(page, col, ex)
            return
        abertos = {}
        for c in _chamados():
            if c.status != "Fechado":
                abertos[c.usuario] = abertos.get(c.usuario, 0) + 1
        estado["abertos"] = abertos
        desenhar()

    def pedir_excluir(nome, qtd):
        # Regra do dono: so pergunta "Tem certeza?" se da pra excluir de verdade.
        if qtd > 0:
            snack(page, f"Não é possível: {nome} tem chamado(s) em aberto.")
            return

        def vai():
            api_excluir_usuario(nome)
            snack(page, "Usuário excluído", VERDE)
            recarregar()

        msg = ft.Text(f"Tem certeza que deseja excluir @{nome}?", color=BRANCO, size=14)
        _dlg(page, "Excluir usuário", [msg], "Excluir", vai)

    def novo_modal(e):
        f_user = ft.TextField(label="Usuário (login)", hint_text="ex: ana.silva", **campo_estilo())
        f_nome = ft.TextField(label="Nome", hint_text="ex: Ana Silva", **campo_estilo())
        f_senha = ft.TextField(label="Senha inicial", password=True, can_reveal_password=True,
                               **campo_estilo())
        f_papel = ft.Dropdown(label="Papel", value="func",
                              options=[ft.dropdown.Option("func", "Funcionário"),
                                       ft.dropdown.Option("ti", "TI")],
                              **campo_estilo())
        mexeu = {"login": False, "nome": False, "senha": False}

        def validar(e=None, campo=None):
            if campo:
                mexeu[campo] = True
            # login sugerido a partir do nome ate o TI digitar o login na mao
            if campo == "nome" and not mexeu["login"]:
                f_user.value = _sugerir_login(f_nome.value)
            erros = _erros_usuario(f_user.value, f_nome.value, f_senha.value)
            f_user.error = erros.get("login") if mexeu["login"] or mexeu["nome"] else None
            f_nome.error = erros.get("nome") if mexeu["nome"] else None
            f_senha.error = erros.get("senha") if mexeu["senha"] else None
            btn.disabled = bool(erros)
            page.update()

        f_user.on_change = lambda e: validar(e, "login")
        f_nome.on_change = lambda e: validar(e, "nome")
        f_senha.on_change = lambda e: validar(e, "senha")

        def vai():
            api_criar_usuario((f_user.value or "").strip().lower(), f_senha.value or "",
                              f_papel.value or "func", (f_nome.value or "").strip())
            snack(page, "Usuário criado!", VERDE)
            recarregar()

        btn = _dlg(page, "Novo usuário", [f_nome, f_user, f_senha, f_papel], "Criar", vai)
        btn.disabled = True
        page.update()

    recarregar()
    return ft.View(
        route="/gestao/usuarios", bgcolor=BG,
        appbar=appbar("Usuários", voltar=lambda e: ir(page, "/gestao"), nome=eu,
                      sair=lambda e: sair(page), sino=sino_button(page)),
        controls=[ft.Container(padding=16, expand=True, content=ft.Column([
            ft.FilledButton("Novo usuário", icon=ft.Icons.PERSON_ADD_OUTLINED,
                            style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"), on_click=novo_modal),
            busca,
            col,
        ], spacing=10))])


def gestao_motivos(page: ft.Page) -> ft.View:
    # [MUSE 25/09] Mesmo padrao: Novo no topo, cards c/ lixeira, modal criar,
    # "Tem certeza?" so quando valido (em uso -> bloqueio direto, sem conf.).
    negado = _so_ti(page, "/gestao/motivos")
    if negado:
        return negado
    eu = SESSAO.get("nome", "?")
    col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    def recarregar():
        try:
            mots = api_motivos(estrito=True)
        except Exception as ex:
            _erro_lista(page, col, ex)
            return
        uso = {}
        for c in _chamados():
            uso[c.motivo] = uso.get(c.motivo, 0) + 1
        linhas = []
        for m in mots:
            q = uso.get(m, 0)
            linhas.append(ft.Container(
                bgcolor=CARD, border=borda(), border_radius=14, padding=14,
                content=ft.Row([
                    ft.Column([ft.Text(m, color=BRANCO, size=14, weight=ft.FontWeight.W_700),
                               ft.Text(f"{q} chamado(s) vinculado(s)" if q else "Sem chamados vinculados",
                                       color=AMARELO if q else CINZA_SUBTIL, size=12)],
                              spacing=2, expand=True),
                    _lixeira(f"Bloqueado: em uso por {q} chamado(s)" if q else None,
                             lambda e, n=m, q=q: pedir_excluir(n, q)),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)))
        col.controls = linhas or [ft.Text("Nenhum motivo.", color=CINZA_SUBTIL, size=13)]
        page.update()

    def pedir_excluir(nome, qtd):
        if qtd > 0:
            snack(page, f"Não é possível: motivo em uso por {qtd} chamado(s).")
            return

        def vai():
            api_excluir_motivo(nome)
            snack(page, "Motivo excluído", VERDE)
            recarregar()

        msg = ft.Text(f'Tem certeza que deseja excluir "{nome}"?', color=BRANCO, size=14)
        _dlg(page, "Excluir motivo", [msg], "Excluir", vai)

    def novo_modal(e):
        f_mot = ft.TextField(label="Novo motivo", hint_text="ex: Impressora não imprime",
                             max_length=60, **campo_estilo())

        def vai():
            api_criar_motivo((f_mot.value or "").strip())
            snack(page, "Motivo criado!", VERDE)
            recarregar()

        _dlg(page, "Novo motivo", [f_mot], "Criar", vai)

    recarregar()
    return ft.View(
        route="/gestao/motivos", bgcolor=BG,
        appbar=appbar("Motivos", voltar=lambda e: ir(page, "/gestao"), nome=eu,
                      sair=lambda e: sair(page), sino=sino_button(page)),
        controls=[ft.Container(padding=16, expand=True, content=ft.Column([
            ft.FilledButton("Novo motivo", icon=ft.Icons.ADD,
                            style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"), on_click=novo_modal),
            col,
        ], spacing=10))])
