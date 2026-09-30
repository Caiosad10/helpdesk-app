# HelpDesk — Flet (desktop-first, mobile-ready) + FastAPI local

Foco atual: **desktop primeiro**, mesma base pronta pro **APK depois**.
Sem KivyMD, sem Buildozer.

## 0) Instalação
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 1) Teste completo em 2 cliques (recomendado)
Duplo-clique em `iniciar_helpdesk.bat` — abre 3 janelas:
- API em `http://127.0.0.1:8000` (docs em `/docs`)
- PWA (build web) em `http://<IP-da-LAN>:8553`, instalável na tela inicial do celular
- App Flet em janela 410x860 (cara de celular no PC)

Ou manual:
```powershell
python -m uvicorn server:app --host 0.0.0.0 --port 8000
python main.py
```

## 2) Logins de teste (pré-definidos, sem dados reais)
Na primeira execução a API cria o `usuarios.json` a partir do `usuarios.exemplo.json`
versionado. Se preferir criar na mão:
```powershell
Copy-Item usuarios.exemplo.json usuarios.json
```

| Usuário | Senha   | Papel |
| ------- | ------- | ----- |
| `ti`    | `ti123` | TI — vê tudo, muda status, gestão de usuários/motivos |
| `maria` | `1234`  | Funcionário — vê só os próprios chamados |
| `joao`  | `1234`  | Funcionário — vê só os próprios chamados |

Essas credenciais são **públicas de propósito**: quem clonar o repositório (ou só quiser
testar o app) entra com elas. As senhas ficam gravadas como SHA-256 em `usuarios.json`
(arquivo **fora do Git**). Em produção, troque-as — a tela de gestão do TI cria/exclui usuários.

## 3) Roteiro de teste robusto
1. Login `maria/1234` → `+` → abre chamado → aparece só pra ela
2. Clica `Abrir >` → vê detalhe → status travado (só TI muda) → volta
3. Sai (ícone logout) → login `ti/ti123` → vê chamado da maria + quem abriu
4. TI abre detalhe → muda `Em atendimento` → Salvar → busca/filtro funcionam
5. Desliga a API (fecha janela) → app continua em modo offline
6. `GET /health`, `/docs` no navegador

## 4) Arquivos
- `main.py`, `nav.py` (login), `home.py`, `detail.py`, `gestao.py`, `ui.py`, `theme.py`, `notify.py`
- `server.py` (FastAPI + SQLite `helpdesk.db`), `auth.py`, `api.py`, `config.py`, `models.py`, `serve_pwa.py`
- `mobile.html` = interface web/PWA (servida em `/mobile`), `assets/icon.png`
- `t12_gestao.py` = testes da tela de gestão (`python t12_gestao.py`)
- `legacy/` = código Kivy antigo guardado (não entra no build)
- `usuarios.exemplo.json` = credenciais de teste (o `usuarios.json` real fica fora do Git)

## 5) Rede da empresa (seu notebook = servidor)
```powershell
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```
Libere porta 8000 no firewall, reserve IP no roteador (`liberar_firewall.bat` roda as regras
de 8000 e 8553; precisa ser executado 1x como Admin).
Nos outros PCs: `HELPDESK_API=http://SEU-IP:8000 python main.py`.
Backup = copiar `helpdesk.db` + `usuarios.json` (os dois ficam fora do Git).

## 6) EXE / PWA / APK depois
```powershell
flet pack main.py --name HelpDesk
flet build web    # gera build/web (servido por serve_pwa.py na porta 8553)
flet build apk
```

## 7) Versionamento (Git/GitHub)
Repositório: **https://github.com/Caiosad10/helpdesk-app**

O repo guarda código-fonte, configuração, testes e documentação. Ficam de fora (`.gitignore`):
- dados locais: `usuarios.json`, `chamados.json`, `helpdesk.db` e `*_backup_*`
- artefatos gerados: `build/`, `dist/`, `*.exe` (o `build/web` da PWA se refaz com `flet build web`)
- snapshots locais antigos: `versao_estavel_*/` e `backup_pre_v1/`
- `*.log` e `.claude/` (config local da IDE)

Versionados de propósito: `usuarios.exemplo.json` (credenciais de teste — seção 2),
`t12_gestao.py` (testes) e `NOTAS_AGENTES.md` (histórico de desenvolvimento).

Clonar e rodar em outra máquina:
```powershell
git clone https://github.com/Caiosad10/helpdesk-app.git
cd helpdesk-app
pip install -r requirements.txt
python -m uvicorn server:app --port 8000   # usuarios.json é criado sozinho (logins da seção 2)
```

Primeiro envio, caso o projeto ainda não tenha remote:
```powershell
git remote add origin https://github.com/Caiosad10/helpdesk-app.git
git push -u origin main
```

> **Nota (projeto dentro do OneDrive):** a pasta `.git` também é sincronizada, o que pode
> gerar conflitos se o repositório for aberto em duas máquinas ao mesmo tempo. Se der
> problema, o GitHub é a fonte da verdade — clone de novo em outra pasta.
