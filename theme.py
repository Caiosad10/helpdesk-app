"""Paleta Spotify + helpers visuais."""
import flet as ft

BG = "#121212"
CARD = "#1E1E1E"
CARD_BORDA = "#2A2A2A"
VERDE = "#1DB954"
BRANCO = "#FFFFFF"
CINZA_TEXTO = "#B3B3B3"
CINZA_SUBTIL = "#8A8A8A"
AMARELO = "#FFC107"
VERMELHO = "#E53935"
AZUL = "#3FA9F5"

MOTIVOS = [
    "Problema com a conexão",
    "Problema com o site",
    "Problema com o aplicativo",
    "Dúvida / suporte geral",
    "Outro",
]
STATUS_OPCOES = ["Aberto", "Em atendimento", "Tratado", "Fechado"]
# TI só pode levar até Tratado. Fechado é confirmação do usuário.
STATUS_TI = ["Aberto", "Em atendimento", "Tratado"]


def msg_status(st: str) -> str:
    return {
        "Aberto": "Novo chamado. Analise para atender!",
        "Em atendimento": "Chamado sendo verificado!",
        "Tratado": "Seu chamado foi tratado. Verifique se foi resolvido!",
        "Fechado": "Chamado resolvido!",
    }.get(st, f"Status: {st}")


def cor_status(status: str) -> str:
    return {
        "Aberto": VERDE,
        "Em atendimento": AMARELO,
        "Tratado": AZUL,
        "Resolvido": AZUL,  # legado: trata como Tratado
        "Fechado": CINZA_SUBTIL,
    }.get(status, VERDE)


def campo_estilo(**kw) -> dict:
    b = ft.OutlineInputBorder(border_radius=12)
    base = dict(
        bgcolor="#1A1A1A",
        border=b,
        color=BRANCO,
        hint_style=ft.TextStyle(color=CINZA_SUBTIL),
        label_style=ft.TextStyle(color=CINZA_TEXTO),
        content_padding=14,
    )
    base.update(kw)
    return base
