"""Modelo Chamado + persistência local em chamados.json."""
from __future__ import annotations
import json, os
from dataclasses import dataclass, asdict
from datetime import datetime

ARQUIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chamados.json")


@dataclass
class Chamado:
    id: int
    usuario: str
    motivo: str
    descricao: str
    status: str = "Aberto"
    criado_em: str = ""


class ChamadoStore:
    def __init__(self, caminho: str = ARQUIVO):
        self.caminho = caminho
        self.chamados: list[Chamado] = []
        self.carregar()

    def carregar(self):
        if not os.path.exists(self.caminho):
            self.chamados = [Chamado(1, "Rafael", "Problema com a conexão", "Internet caindo a cada 10 minutos no setor 2.", "Aberto", datetime.now().strftime("%d/%m %H:%M"))]
            self.salvar()
            return
        try:
            with open(self.caminho, encoding="utf-8") as f:
                self.chamados = [Chamado(**c) for c in json.load(f)]
        except Exception:
            self.chamados = []

    def salvar(self):
        try:
            with open(self.caminho, "w", encoding="utf-8") as f:
                json.dump([asdict(c) for c in self.chamados], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def adicionar(self, usuario, motivo, descricao):
        nid = max([c.id for c in self.chamados], default=0) + 1
        c = Chamado(nid, (usuario or "").strip() or "Usuário", motivo, (descricao or "").strip(), "Aberto", datetime.now().strftime("%d/%m %H:%M"))
        self.chamados.insert(0, c)
        self.salvar()
        return c

    def obter(self, cid):
        return next((c for c in self.chamados if c.id == cid), None)

    def status(self, cid, st):
        c = self.obter(cid)
        if c:
            c.status = st
            self.salvar()

    def excluir(self, cid):
        self.chamados = [c for c in self.chamados if c.id != cid]
        self.salvar()

    def filtrar(self, texto, st):
        t = (texto or "").strip().lower()
        out = [c for c in self.chamados if st in ("Todos", None) or c.status == st]
        if t:
            out = [c for c in out if t in c.motivo.lower() or t in c.descricao.lower() or t in c.usuario.lower() or t == str(c.id)]
        return out
