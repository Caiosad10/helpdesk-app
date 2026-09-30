"""Novo chamado + detalhe (fluxo Tratado -> Confirmar=Fechado)."""
import flet as ft
from theme import BG, CARD, CARD_BORDA, VERDE, BRANCO, CINZA_TEXTO, CINZA_SUBTIL, MOTIVOS, STATUS_TI, campo_estilo, msg_status
from ui import appbar, badge, borda, snack
from nav import ir, sair
# [MUSE 24/09] v1.1: motivos via API (TI gerencia) c/ fallback p/ MOTIVOS fixos.
from api import SESSAO, api_criar, api_obter, api_obter_full, api_status, api_excluir, api_editar, api_obs, api_motivos
from notify import toast, sino_button


def novo(page: ft.Page) -> ft.View:
    eu = SESSAO.get("nome", "?")
    mots = api_motivos()
    motivo = ft.Dropdown(label="Motivo", value=mots[0] if mots else MOTIVOS[0],
                         options=[ft.dropdown.Option(m) for m in mots], **campo_estilo())
    desc = ft.TextField(label="Descreva o problema", multiline=True, min_lines=4, max_lines=6, **campo_estilo())

    def ok(e):
        if not (desc.value or "").strip():
            desc.error_text = "Descreva o problema rapidinho"
            page.update()
            return
        try:
            c = api_criar(motivo.value, desc.value)
            # [CLAUDE 22/09] api_criar() nunca tocava em page._hd_cache (so
            # excluir()/fluxo() em home.py faziam isso) — a home nova (forcar=True
            # logo depois) lia o cache velho, sem o chamado recem-criado, ate o
            # proximo ciclo de 3s da thread de polling. Insere igual o padrao ja usado.
            try:
                cache = getattr(page, "_hd_cache", None)
                if cache is not None:
                    page._hd_cache = [c] + [x for x in cache if x.id != c.id]
            except Exception:
                pass
            snack(page, "Chamado aberto com sucesso!", VERDE)
            ir(page, "/")
        except Exception as ex:
            snack(page, f"Erro: {ex}")

    return ft.View(route="/novo", bgcolor=BG, appbar=appbar("Novo chamado", voltar=lambda e: ir(page, "/"), nome=eu, sair=lambda e: sair(page), sino=sino_button(page)),
        controls=[ft.Container(padding=16, content=ft.Column([
            ft.Text("Abrir chamado", size=22, weight=ft.FontWeight.W_800, color=BRANCO),
            ft.Text(f"Abrindo como {eu} — vai direto pro TI.", color=CINZA_SUBTIL, size=13),
            motivo, desc,
            ft.FilledButton("Confirmar chamado", icon=ft.Icons.CHECK_CIRCLE_OUTLINE, style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"), on_click=ok),
            ft.OutlinedButton("Cancelar", on_click=lambda e: ir(page, "/")),
        ], spacing=12))])


def detalhe(page: ft.Page, cid: int) -> ft.View:
    eu = SESSAO.get("nome", "?")
    e_ti = SESSAO.get("papel") == "ti"
    c = api_obter(cid)
    if not c:
        return ft.View(route="/", bgcolor=BG, appbar=appbar("HelpDesk"), controls=[ft.Text("Nao encontrado", color=BRANCO)])
    dd = ft.Dropdown(value=c.status if c.status in STATUS_TI else STATUS_TI[0], options=[ft.dropdown.Option(s) for s in STATUS_TI], **campo_estilo(), disabled=not e_ti)

    fechado = (c.status == "Fechado")

    # [MUSE 22/09] Observacao do TI em Fechado (auditoria): modal p/ registrar,
    # visivel p/ todos no detalhe. So TI grava; server recusa resto (403/422).
    full = api_obter_full(cid) or {}
    obs_atual = (full.get("observacao") or "").strip()
    obs_campo = ft.TextField(label="Observacao (auditoria)", multiline=True, min_lines=3,
                             max_lines=5, value=obs_atual, **campo_estilo())

    # [CLAUDE 22/09] salvar_obs precisa fechar o dialogo (dlg.open=False) ANTES de
    # navegar com ir(page,"/") — page.views.clear() nao mexe em page.overlay, entao sem
    # isso o dialogo ficava aberto por cima da tela nova depois de salvar. Por isso
    # salvar_obs foi pra dentro de abrir_obs (precisa do "fechar" e do "dlg").
    def abrir_obs(e):
        def fechar():
            dlg.open = False
            page.update()

        def salvar_obs(ev):
            try:
                api_obs(c.id, obs_campo.value or "")
                fechar()
                snack(page, "Observacao registrada!", VERDE)
                ir(page, "/")
            except Exception as ex:
                snack(page, f"Erro: {ex}")

        dlg = ft.AlertDialog(
            title=ft.Text("Observacao do TI", color=BRANCO, weight=ft.FontWeight.W_700),
            content=ft.Container(width=340, content=obs_campo),
            actions=[ft.TextButton("Cancelar", on_click=lambda ev: fechar()),
                     ft.FilledButton("Salvar observacao", style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"),
                                     on_click=salvar_obs)],
        )
        dlg.on_dismiss = lambda ev: None
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    bloco_obs = []
    if fechado and e_ti:
        bloco_obs = [
            ft.Divider(color=CARD_BORDA),
            ft.Text("Auditoria (TI)", color=BRANCO, weight=ft.FontWeight.W_700),
            *( [ft.Text(f"Registrada: {obs_atual}", color=CINZA_TEXTO, size=13)] if obs_atual else
               [ft.Text("Nenhuma observacao registrada.", color=CINZA_SUBTIL, size=12)] ),
            ft.OutlinedButton("Adicionar observacao", icon=ft.Icons.NOTE_ADD_OUTLINED, on_click=abrir_obs),
        ]
    elif fechado and obs_atual:
        bloco_obs = [
            ft.Divider(color=CARD_BORDA),
            ft.Text("Observacao do TI", color=BRANCO, weight=ft.FontWeight.W_700),
            ft.Text(obs_atual, color=CINZA_TEXTO, size=13),
        ]

    def salvar(e):
        try:
            api_status(c.id, dd.value)
            if dd.value == "Tratado":
                toast(page, "Chamado atualizado", "Aguarde a confirmacao do usuario.", VERDE)
            else:
                toast(page, "Status atualizado", "#%d: %s" % (c.id, msg_status(dd.value)), VERDE)
            ir(page, "/")
        except Exception as ex:
            snack(page, f"Erro: {ex}")

    def confirmar(e):
        """Usuário confirma que foi resolvido -> Fechado."""
        try:
            api_status(c.id, "Fechado")
            toast(page, "Chamado resolvido!", "#%d fechado. Obrigado por confirmar!" % c.id, VERDE)
            ir(page, "/")
        except Exception as ex:
            snack(page, f"Erro: {ex}")

    def excluir(e):
        try:
            api_excluir(c.id)
            snack(page, "Chamado excluido")
        except Exception as ex:
            snack(page, f"Erro: {ex}")
            return
        ir(page, "/")

    # [MUSE 22/09] Fase 1: funcionario edita motivo/descricao do proprio chamado
    # (nunca Fechado).
    # [CLAUDE 22/09] TI nao edita mais motivo/descricao (so muda status) — bloco some
    # tambem pra TI, nao so quando Fechado. Backend (server.py::editar) ja recusa TI.
    # [MUSE 24/09] v1.1: opcoes do dropdown vindas da API (TI gerencia motivos).
    mots_ed = api_motivos()
    ed_motivo = ft.Dropdown(label="Motivo", value=c.motivo if c.motivo in mots_ed else (mots_ed[0] if mots_ed else MOTIVOS[0]),
                            options=[ft.dropdown.Option(m) for m in mots_ed], **campo_estilo())
    ed_desc = ft.TextField(label="Descricao", value=c.descricao, multiline=True, min_lines=3, max_lines=5, **campo_estilo())

    def salvar_edicao(e):
        try:
            api_editar(c.id, ed_motivo.value, ed_desc.value)
            snack(page, "Chamado atualizado!", VERDE)
            ir(page, "/")
        except Exception as ex:
            snack(page, f"Erro: {ex}")

    bloco_editar = [] if (fechado or e_ti) else [
        ft.Text("Editar chamado (corrige motivo/descricao)", color=BRANCO, weight=ft.FontWeight.W_700),
        ed_motivo, ed_desc,
        ft.FilledButton("Salvar edicao", style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"), on_click=salvar_edicao),
    ]

    if e_ti:
        bloco = [ft.Text("Alterar status (TI vai até Tratado)", color=BRANCO, weight=ft.FontWeight.W_700), dd, ft.FilledButton("Salvar status", style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"), on_click=salvar)]
    else:
        if c.status == "Tratado":
            bloco = [
                ft.Container(bgcolor="#0E2F1B", border=borda("#1DB954"), border_radius=12, padding=12,
                    content=ft.Column(spacing=6, controls=[
                        ft.Text("Seu chamado foi tratado. Verifique se foi resolvido!", color=BRANCO, weight=ft.FontWeight.W_700),
                        ft.Text("Se realmente resolveu, confirme abaixo. Se não, aguarde ou abra outro chamado.", color=CINZA_TEXTO, size=12),
                        ft.FilledButton("Confirmar - foi resolvido!", style=ft.ButtonStyle(bgcolor=VERDE, color="#0B0B0B"), on_click=confirmar),
                    ])),
            ]
        elif fechado:
            bloco = [ft.Text(msg_status("Fechado"), color=VERDE, weight=ft.FontWeight.W_700)]
        else:
            bloco = [ft.Text(f"Aguardando o TI — {msg_status(c.status)}", color=CINZA_SUBTIL)]

    return ft.View(route=f"/detalhe/{c.id}", bgcolor=BG, appbar=appbar(f"Chamado #{c.id}", voltar=lambda e: ir(page, "/"), nome=eu, sair=lambda e: sair(page), sino=sino_button(page)),
        controls=[ft.Container(padding=16, content=ft.Column([
            ft.Container(bgcolor=CARD, border=borda(), border_radius=16, padding=16,
                content=ft.Column([
                    ft.Row([ft.Text(c.motivo, size=18, weight=ft.FontWeight.W_800, color=BRANCO, expand=True), badge(c.status)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(c.descricao, color=CINZA_TEXTO),
                    ft.Divider(color=CARD_BORDA),
                    ft.Text(f"Aberto por {c.usuario} - {c.criado_em}", color=CINZA_SUBTIL, size=12),
                ], spacing=10)),
            *bloco,
            *bloco_editar,
            *bloco_obs,
            # [MUSE 22/09] Fase 1: Fechado é histórico — sem Excluir p/ ninguém.
            *([] if fechado else [ft.OutlinedButton("Excluir chamado", icon=ft.Icons.DELETE_OUTLINE, on_click=excluir)]),
        ], spacing=12))])
