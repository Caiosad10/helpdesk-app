"""Servidor estatico do build/web (PWA) com cabecalhos de isolamento de origem cruzada.

    python serve_pwa.py [porta]

# [CLAUDE 24/09] O 'python -m http.server' simples nao manda Cross-Origin-Opener-Policy
# nem Cross-Origin-Embedder-Policy. O build do Flet (flutter.js/main.dart.js) referencia
# SharedArrayBuffer/crossOriginIsolated -- sem esses dois cabecalhos, o navegador nega
# SharedArrayBuffer e o runtime Python-no-worker do Flet pode falhar de forma silenciosa
# em navegadores mais rigorosos (reproduzido: Chrome Android falhava com "Failed to
# fetch" mesmo com CORS/rede provados OK via pagina de diagnostico; Chrome desktop mais
# antigo tolerava sem isolamento). Esse script serve os mesmos arquivos do http.server
# padrao, so acrescentando os dois cabecalhos em toda resposta.
"""
import sys
import functools
import http.server


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8553
    diretorio = str((__import__("pathlib").Path(__file__).with_name("build") / "web"))
    handler = functools.partial(Handler, directory=diretorio)
    with http.server.ThreadingHTTPServer(("0.0.0.0", porta), handler) as httpd:
        print(f"Servindo {diretorio} em http://0.0.0.0:{porta} (com COOP/COEP)")
        httpd.serve_forever()
