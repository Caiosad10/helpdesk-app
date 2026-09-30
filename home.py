"""Home com polling tempo real + toast 1x + sino (v1.1: motivos via API, botao gestao)."""
import flet as ft
from theme import BG, CARD_BORDA, VERDE, BRANCO, CINZA_SUBTIL, STATUS_OPCOES, campo_estilo, msg_status
from ui import appbar, card, pad, snack, item_barra, barra_inferior
from nav import ir, sair, sessao_caiu
# [MUSE 22/09] Fluxo inline sem abrir detalhe: TI Aberto->Em atendimento->Tratado;
# func Tratado->Fechado (confirmar). Status continua restrito no server (PATCH).
# [MUSE 24/09] v1.1: api_motivos (dropdowns leem da API) + botao gestao p/ TI.
from api import SESSAO, api_listar, api_eventos, api_excluir, api_status, api_motivos, online
from notify import toast, sino_button


def home(page: ft.Page) -> ft.View:
    eu = SESSAO.get("nome", "?")
    e_ti = SESSAO.get("papel") == "ti"
    busca = ft.TextField(hint_text="Buscar motivo, descricao ou #id...", prefix_icon=ft.Icons.SEARCH, **campo_estilo())
    fst = ft.Dropdown(value="Todos", options=[ft.dropdown.Option(s) for s in ["Todos", *STATUS_OPCOES]], **campo_estilo())
    # [MUSE 22/09] Fase 1: TI tem aba Ativos (Aberto/Em atendimento/Tratado) + Fechados
    # (historico, sem excluir). Func usa o filtro normal e nunca tem acao em Fechado.
    # [CLAUDE 22/09] `selected` e tipado list[str] no Flet; um set() nao tem __dict__ e
    # quebra o encoder JSON usado no page.update() apos o login (exception engolida pelo
    # try/except do entrar() em nav.py -> tela de login travava sem erro visivel pro TI).
    aba_ti = ft.SegmentedButton(
        segments=[ft.Segment(value="ativos", label=ft.Text("Ativos")),
                  ft.Segment(value="fechados", label=ft.Text("Fechados"))],
        selected=["ativos"],
        on_change=lambda e: recarregar(forcar=True),
    ) if e_ti else None
    lista = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    cont = ft.Text("", color=CINZA_SUBTIL, size=12)
    modo = ft.Text("", color=CINZA_SUBTIL, size=12)

    def abrir(cid):
        ir(page, f"/detalhe/{cid}")

    def excluir(cid):
        try:
            api_excluir(cid)
            snack(page, "Chamado excluido")
        except Exception as ex:
            snack(page, f"Erro: {ex}")
            return
        page._hd_cache = [c for c in (getattr(page, "_hd_cache", []) or []) if c.id != cid]
        recarregar(forcar=True)

    # [MUSE 22/09] Fluxo inline sem abrir detalhe: TI Aberto->Em atendimento->Tratado;
    # func Tratado->Fechado (confirmar). Status continua restrito no server (PATCH).
    # [CLAUDE 22/09] usa toast() (com som + fica no historico do sino), nao snack() —
    # a mesma acao feita pela tela de detalhe ja usava toast(); o inline tava dando uma
    # experiencia diferente pra mesma coisa.
    def fluxo(cid, destino, titulo, texto):
        try:
            api_status(cid, destino)
            toast(page, titulo, texto, VERDE)
            try:
                for c in (getattr(page, "_hd_cache", []) or []):
                    if c.id == cid:
                        c.status = destino
                        break
            except Exception:
                pass
        except Exception as ex:
            snack(page, f"Erro: {ex}")
            return
        recarregar(forcar=True)

    def confirmar(cid):
        fluxo(cid, "Fechado", "Chamado resolvido!", "#%d fechado. Obrigado por confirmar!" % cid)

    def iniciar(cid):
        fluxo(cid, "Em atendimento", "Status atualizado", "#%d: %s" % (cid, msg_status("Em atendimento")))

    def finalizar(cid):
        fluxo(cid, "Tratado", "Chamado atualizado", "Aguarde a confirmacao do usuario.")

    def filtrados():
        # [MUSE 21/09] usa cache da thread (P1): evita HTTP sincrono na thread da UI,
        # que congelava a tela e "engolia" o clique no Abrir nos primeiros minutos.
        todos = list(getattr(page, "_hd_cache", []) or [])
        if not todos:
            try:
                todos = api_listar()
                page._hd_cache = list(todos)
            except Exception as ex:
                snack(page, f"Falha: {ex}")
                return []
        # [CLAUDE 22/09] funcionario nao tem filtro nem controle de Fechados — sempre
        # ve so os ativos (Aberto/Em atendimento/Tratado), sem opcao de alternar.
        if not e_ti:
            return [c for c in todos if c.status != "Fechado"]
        st = fst.value or "Todos"
        t = (busca.value or "").strip().lower()
        out = [c for c in todos if st == "Todos" or c.status == st]
        # [MUSE 22/09] Fase 1: aba do TI — Ativos esconde Fechado; Fechados mostra SÓ Fechado.
        if aba_ti is not None:
            sel = next(iter(aba_ti.selected or ["ativos"]), "ativos")
            if sel == "ativos":
                out = [c for c in out if c.status != "Fechado"]
            else:
                out = [c for c in out if c.status == "Fechado"]
        if t:
            out = [c for c in out if t in c.motivo.lower() or t in c.descricao.lower() or t in c.usuario.lower() or t == str(c.id)]
        return out

    def online_cache():
        # [MUSE 21/09] throttle 20s (P1): online() faz /health sincrono (~0,4s) e era
        # chamado 2-3x por ciclo de 3s, somando 1s+ de UI congelada por ciclo.
        import time as _tt
        try:
            ult = getattr(page, "_hd_online", None)
            agora = _tt.monotonic()
            if ult and (agora - ult[1] < 20):
                return ult[0]
            ok = online()
            page._hd_online = (ok, agora)
            return ok
        except Exception:
            return True

    def recarregar(primeira=False, forcar=False):
        itens = filtrados()
        # [MUSE 21/09] debounce (P2): só remonta os cards se a foto id->status mudou;
        # rebuild a cada 3s recriava os botoes e descartava o clique do usuario.
        # [CLAUDE 22/09] a foto so tinha status -> editar motivo/descricao (Fase 1) nao
        # muda o status, entao a edicao de outro usuario nunca aparecia na tela ate
        # navegar pra fora da home e voltar. Agora a foto inclui motivo/descricao tambem.
        try:
            foto = {c.id: (c.status, c.motivo, c.descricao) for c in itens}
            if not forcar and foto == getattr(page, "_hd_foto", None):
                cont.value = f"{len(itens)} chamado(s)"
                if not primeira and len(page.views) > 0:
                    try:
                        page.update()
                    except Exception:
                        pass
                return
            page._hd_foto = foto
        except Exception:
            pass
        lista.controls.clear()
        if not itens:
            lista.controls.append(ft.Container(padding=40, alignment=ft.Alignment.CENTER, content=ft.Column([
                ft.Icon(ft.Icons.INBOX_OUTLINED, size=56, color=CARD_BORDA),
                ft.Text("Nenhum chamado aqui", color=BRANCO, weight=ft.FontWeight.W_700),
                ft.Text("Toque no + para abrir o primeiro.", color=CINZA_SUBTIL, size=13),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)))
        else:
            for c in itens:
                # [MUSE 22/09] Fase 1: Fechado sem acoes p/ ninguém; func vê "Editar".
                # [CLAUDE 22/09] rotulo so diz "Editar" se realmente da pra editar (nunca
                # num Fechado, ainda que um chegue aqui por algum caminho futuro).
                fech = (c.status == "Fechado")
                # [MUSE 22/09] Botao de fluxo inline: func+Tratado confirma sem entrar;
                # TI+Aberto inicia, TI+Em atendimento finaliza (sem abrir detalhe).
                # [MUSE 23/09] Pente-fino: TI+Tratado ganha fantasma "Aguardando
                # confirmacao" (igual mobile.html) — OutlineButton que só recarrega.
                acao, rotulo, fant = None, None, False
                if e_ti and c.status == "Aberto":
                    acao, rotulo = iniciar, "Iniciar tratativa"
                elif e_ti and c.status == "Em atendimento":
                    acao, rotulo = finalizar, "Finalizar tratativa"
                elif e_ti and c.status == "Tratado":
                    acao, rotulo, fant = (lambda cid: recarregar(forcar=True)), "Aguardando confirmacao", True
                elif (not e_ti) and c.status == "Tratado":
                    acao, rotulo = confirmar, "Confirmar - foi resolvido!"
                lista.controls.append(card(c, abrir, excluir, pode_excluir=not fech,
                                           rotulo_abrir="Abrir >" if (e_ti or fech) else "Editar",
                                           acao=acao, rotulo_acao=rotulo, fantasma=fant))
        cont.value = f"{len(itens)} chamado(s)"
        modo.value = ("Visao TI - todos" if e_ti else f"{eu} - so os seus") + (" - servidor ON" if online_cache() else " - offline")
        # [MUSE 22/09 + CLAUDE 22/09] Consumidora dedicada de toasts: a thread de
        # polling só enfileira em _hd_toasts; quem chama toast() (que faz
        # page.update) é este trecho, que roda na thread da UI (via _obs/_tst).
        try:
            fila = getattr(page, "_hd_toasts", None)
            if fila:
                while fila:
                    try:
                        titulo, texto = fila.pop(0)
                    except Exception:
                        break
                    try:
                        toast(page, titulo, texto)
                    except Exception:
                        pass
        except Exception:
            pass
        if not primeira and len(page.views) > 0:
            try:
                page.update()
            except Exception:
                pass

    busca.on_change = lambda e: recarregar(forcar=True)
    fst.on_change = lambda e: recarregar(forcar=True)
    sino = sino_button(page)

    # a thread de polling roda so 1x pro app inteiro (nunca eh recriada),
    # mas cada navegacao monta uma home() nova com lista/recarregar novos.
    # guardamos sempre a versao mais recente aqui pra thread nunca ficar
    # presa atualizando uma tela antiga que ja saiu do ar.
    page._hd_recarregar = recarregar
    page._hd_filtrados = filtrados
    # [CLAUDE 22/09] Consumido: a thread de polling (produtora) não chama mais
    # page.update() direto — só marca _hd_sujo=True e agenda este coro na UI.
    # Roda a cada 1s (mais rápido que o ciclo de 3s) e só atualiza se houver
    # sujeira pendente E estivermos na home (route "/").
    async def _obs():
        import asyncio as _aio
        while True:
            try:
                await _aio.sleep(1)
                if not getattr(page, "_hd_sujo", False):
                    continue
                page._hd_sujo = False
                if (page.route or "/") != "/":
                    continue
                rec = getattr(page, "_hd_recarregar", None) or recarregar
                rec()
            except Exception:
                pass
    try:
        if not getattr(page, "_hd_obs", False):
            page._hd_obs = True
            page.run_task(_obs)
    except Exception:
        page._hd_obs = False

    # ---------- tempo real: 1 thread global, 1 toast por fato ----------
    if getattr(page, "_hd_poll", None) is None:
        page._hd_poll = {"v": 0, "ids": {}, "notificados": set()}
    estado = page._hd_poll

    # [CLAUDE 22/09] estado["ids"]/foto guardam (status,motivo,descricao), nao so
    # status — usado só como "sabe desse id" (in/not in) pelo dedup de notificacao,
    # nunca lido pelo valor lá, entao trocar a forma nao quebra nada disso. Precisava
    # incluir motivo/descricao aqui porque _hd_sujo (novo gate do Muse pro produtor-
    # -consumidor) só compara esse foto contra o anterior — uma edicao de texto sem
    # mudar status nunca marcava sujo, e minha correcao de ontem no debounce do
    # recarregar() virou codigo morto: _obs() nunca chegava a chamar rec() pra esse caso.
    def foto_atual():
        try:
            filt = getattr(page, "_hd_filtrados", None) or filtrados
            return {c.id: (c.status, c.motivo, c.descricao) for c in filt()}
        except Exception:
            return {}

    # [CLAUDE 24/09] poll_novo() virou coroutine (page.run_task), nao mais funcao
    # sincrona rodada via page.run_thread(). Motivo: no navegador (Pyodide/web),
    # page.run_thread() NAO cria thread nenhuma — olhei o codigo-fonte do Flet
    # (page.py:910, `if is_pyodide(): handler_with_context(*args, **kwargs)`) e ele
    # so roda o handler NA HORA, sincrono, no mesmo lugar que desenha a tela. Um
    # `while True: time.sleep(3)` rodando assim nunca retorna -> home() nunca termina
    # de montar a View -> tela trava preta pra sempre logo apos o login (reproduzi isso
    # ao vivo no build web). No desktop nativo run_thread() cria thread de verdade, mas
    # run_task()+await asyncio.sleep() funciona igual nos dois ambientes (mesmo
    # mecanismo que _obs()/_tst() ja usavam) — por isso a troca serve pros dois.
    async def poll_novo():
        import asyncio as _aio3
        # [MUSE 21/09] snapshot+throttle (P1): a thread faz os HTTPs (api_listar 1x por
        # ciclo) e a UI só lê o cache — antes eram 4-6 HTTPs/ciclo com rebuild total.
        try:
            try:
                snap = api_listar()
                page._hd_cache = list(snap)
                base = {c.id: (c.status, c.motivo, c.descricao) for c in snap}
            except Exception:
                base = {}
            estado["ids"] = base
            try:
                ev0 = api_eventos(0)
                estado["v"] = int(ev0.get("versao", 0) or 0)
            except Exception:
                estado["v"] = 0
            while True:
                await _aio3.sleep(3)
                try:
                    # [CLAUDE 25/09] 401 no polling (usuario excluido / sessao
                    # derrubada): apaga o token salvo e volta pro login com aviso.
                    if sessao_caiu(page):
                        return
                    if not SESSAO.get("token"):
                        return
                    rota = str(page.route or "/")
                    if rota not in ("/", "/novo") and not rota.startswith("/detalhe"):
                        continue
                    try:
                        ev = api_eventos(estado["v"])
                    except Exception:
                        continue
                    estado["v"] = int(ev.get("versao", estado["v"]) or estado["v"])
                    mud = ev.get("mudancas", []) or []
                    # [MUSE 21/09] 1 listar por ciclo (P1): atualiza cache+foto aqui; o
                    # recarregar() da UI não faz mais HTTP, só redesenha do cache.
                    try:
                        snap2 = api_listar()
                        page._hd_cache = list(snap2)
                        foto = {c.id: (c.status, c.motivo, c.descricao) for c in snap2}
                    except Exception:
                        foto = foto_atual()
                    papel = SESSAO.get("papel")
                    eu_user = SESSAO.get("usuario", "")
                    for c in mud:
                        chave = (c.id, c.status)
                        if chave in estado["notificados"]:
                            continue
                        if papel == "ti":
                            if c.usuario == eu_user:
                                continue
                            if c.id not in estado["ids"]:
                                estado["notificados"].add(chave)
                                fila = getattr(page, "_hd_toasts", None)
                                if fila is None:
                                    fila = []
                                    page._hd_toasts = fila
                                fila.append(("Novo chamado!", "#%d %s - %s" % (c.id, c.motivo, c.usuario)))
                            elif c.status == "Fechado":
                                estado["notificados"].add(chave)
                                fila = getattr(page, "_hd_toasts", None)
                                if fila is None:
                                    fila = []
                                    page._hd_toasts = fila
                                fila.append(("Chamado #%d Fechado" % c.id, "Confirmado pelo usuario."))
                        else:
                            if c.id in estado["ids"] or c.usuario == eu_user:
                                if c.status == "Em atendimento":
                                    estado["notificados"].add(chave)
                                    fila = getattr(page, "_hd_toasts", None)
                                    if fila is None:
                                        fila = []
                                        page._hd_toasts = fila
                                    fila.append(("Atualizacao!", "#%d: Seu chamado está sendo verificado!" % c.id))
                                elif c.status == "Tratado":
                                    estado["notificados"].add(chave)
                                    fila = getattr(page, "_hd_toasts", None)
                                    if fila is None:
                                        fila = []
                                        page._hd_toasts = fila
                                    fila.append(("Atualizacao!", "#%d: Tratado. Verifique!" % c.id))
                    if foto:
                        if foto != estado["ids"]:
                            page._hd_sujo = True
                        estado["ids"] = foto
                    if getattr(page, "_hd_toasts", None):
                        page._hd_sujo = True
                except Exception:
                    continue
        finally:
            page._hd_poll_ativo = False

    # evita empilhar 1 thread de polling por navegacao (era a causa do spam
    # de notificacao: cada troca de tela criava outro poll() que nunca morria)
    # [CLAUDE 24/09] run_task() no lugar de run_thread() — poll_novo() agora e
    # coroutine (ver comentario acima da definicao dela).
    if not getattr(page, "_hd_poll_ativo", False):
        page._hd_poll_ativo = True
        try:
            page.run_task(poll_novo)
        except Exception:
            page._hd_poll_ativo = False

    # [CLAUDE 22/09] Consumidora dedicada: a cada 1s dispara os toasts que a thread
    # de polling enfileirou em _hd_toasts. O disparo passa por rec(forcar=True),
    # que drena a fila na thread da UI — junto com o rec() do _obs, garante
    # lista + toast renderizados em <=1s após a sujeira.
    async def _tst():
        import asyncio as _aio2
        while True:
            try:
                await _aio2.sleep(1)
                if not getattr(page, "_hd_toasts", None):
                    continue
                if (page.route or "/") != "/":
                    continue
                try:
                    rec = getattr(page, "_hd_recarregar", None) or recarregar
                    rec(forcar=True)
                except Exception:
                    pass
            except Exception:
                pass
    try:
        if not getattr(page, "_hd_tst", False):
            page._hd_tst = True
            page.run_task(_tst)
    except Exception:
        page._hd_tst = False

    header = ft.Container(
        gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=["#1DB954", "#0E5C2A"]),
        border_radius=18, padding=18,
        content=ft.Column([
            ft.Text(f"Ola, {eu}!", color="#06240F", size=13, weight=ft.FontWeight.W_700),
            ft.Text("Painel do TI" if e_ti else "Meus chamados", color="#06240F", size=24, weight=ft.FontWeight.W_800),
            ft.Text("Analise os chamados." if e_ti else "Acompanhe e confirme a resolucao.", color="#06240F", size=12),
        ], spacing=4),
    )
    recarregar(primeira=True, forcar=True)
    # [MUSE 22/09] Fase 1: coluna inclui a aba Ativos/Fechados só p/ TI.
    # [CLAUDE 22/09] busca/fst (filtro) tambem so pro TI — funcionario nao filtra nada,
    # so acompanha os proprios chamados ativos.
    coluna = [header, modo] + ([aba_ti, busca, fst] if e_ti else []) + [cont, lista]
    # [CLAUDE 22/09] TI nao cria chamado pra si mesmo — sem FAB "+". Backend
    # (server.py::criar) ja recusa TI mesmo se a rota /novo for alcancada de outro jeito.
    # [CLAUDE 25/09] Experimento de design: FAB redondo encaixado no recorte da barra.
    fab = None if e_ti else ft.FloatingActionButton(
        icon=ft.Icons.ADD, bgcolor=VERDE, foreground_color="#0B0B0B", shape=ft.CircleBorder(),
        tooltip="Novo chamado", on_click=lambda e: ir(page, "/novo"))

    def perfil(e):
        papel = "TI" if e_ti else "Funcionário"
        dlg = ft.AlertDialog(
            title=ft.Text(eu, color=BRANCO, weight=ft.FontWeight.W_800),
            content=ft.Text(f"@{SESSAO.get('usuario', '?')} · {papel}", color=CINZA_SUBTIL, size=13),
            actions=[ft.TextButton("Fechar", on_click=lambda e2: fechar_perfil(dlg))])
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def fechar_perfil(dlg):
        dlg.open = False
        page.update()

    # [CLAUDE 25/09] Sino/gestao/sair sairam do topo e foram pra barra inferior.
    # [MUSE 24/09] v1.1: gestao (so TI) — agora item da barra.
    it_chamados = item_barra(ft.Icons.LIST_ALT, "Chamados", lambda e: recarregar(forcar=True), ativo=True)
    try:
        sino.controls[0].icon_color = CINZA_SUBTIL  # mesmo tom dos outros itens
    except Exception:
        pass
    it_avisos = item_barra(None, "Avisos", controle=sino)
    it_sair = item_barra(ft.Icons.LOGOUT, "Sair", lambda e: sair(page))
    if e_ti:
        barra = barra_inferior([it_chamados, it_avisos,
                                item_barra(ft.Icons.SETTINGS_OUTLINED, "Gestão", lambda e: ir(page, "/gestao")),
                                it_sair])
    else:
        barra = barra_inferior([it_chamados, it_avisos],
                               [item_barra(ft.Icons.PERSON_OUTLINE, "Perfil", perfil), it_sair], notch=True)
    return ft.View(
        route="/", bgcolor=BG, appbar=appbar("HelpDesk", nome=eu),
        floating_action_button=fab,
        floating_action_button_location=ft.FloatingActionButtonLocation.CENTER_DOCKED,
        bottom_appbar=barra,
        controls=[ft.Container(padding=pad(14, 10), expand=True, content=ft.Column(coluna, spacing=10))])
