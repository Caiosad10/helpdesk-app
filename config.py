"""Config central: URL do backend (notebook) + fallback local."""
import os
import sys


def _api_url() -> str:
    override = os.environ.get("HELPDESK_API")
    if override:
        return override.rstrip("/")
    # [CLAUDE 24/09] No build web (Pyodide, sys.platform == "emscripten") nao existe
    # variavel de ambiente de verdade por tras do navegador -- o que for embutido no
    # build e o que vale sempre, mesmo se o IP da rede mudar depois. Por isso, no web,
    # descobrimos o host em tempo real pela propria URL que o navegador usou pra abrir
    # a PWA: se o celular abriu via http://192.168.x.x:8553, o backend deve estar no
    # mesmo IP, na porta 8000. Isso evita ter que reconstruir o build toda vez que o IP
    # do notebook mudar (rede DHCP).
    # ACHADO (confirmado ao vivo, celular Android real): o Python do Flet roda dentro de
    # um Web Worker (nao na thread/pagina principal) -- e dentro de um Worker o objeto
    # `window` NAO EXISTE (so existe na pagina principal), entao `js.window.location`
    # falhava silenciosamente (except generico engolia o erro) e caia sempre no fallback
    # 127.0.0.1, que no celular aponta pro proprio celular (nada escutando ali) -> "Failed
    # to fetch" na hora, sempre, em qualquer chamada. `js.location` (sem `.window`) existe
    # tanto na pagina principal quanto dentro de um Worker (e' global em ambos), entao
    # funciona nos dois ambientes -- mantido `js.window.location` como fallback so por
    # seguranca, caso algum ambiente futuro so exponha via `window`.
    if sys.platform == "emscripten":
        try:
            import js  # type: ignore

            host = ""
            try:
                host = str(js.location.hostname)
            except Exception:
                pass
            if not host:
                host = str(js.window.location.hostname)
            if host:
                return f"http://{host}:8000"
        except Exception:
            pass
    return "http://127.0.0.1:8000"


# Troque pelo IP fixo do seu notebook na rede da empresa se quiser forcar manualmente
# (variavel de ambiente HELPDESK_API). Ex: "http://192.168.1.100:8000"
API_URL = _api_url()

# Timeout curto p/ cair rapido pro modo offline (arquivo local)
API_TIMEOUT = float(os.environ.get("HELPDESK_TIMEOUT", "2.5"))
