@echo off
REM Mostra o IP da LAN e sobe backend + app web (PWA) + app desktop
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do set IP=%%a
set IP=%IP: =%
echo ============================================
echo  HELPDESK - USO REAL - TEMPO REAL
echo  IP do notebook: %IP%
echo  Celular / outro PC (app web, instalavel na tela inicial):
echo     http://%IP%:8553
echo  Notebook (app desktop): abrindo automaticamente
echo  Docs da API: http://127.0.0.1:8000/docs
echo ============================================
start "HelpDesk API" cmd /k "cd /d %~dp0 && python -m uvicorn server:app --host 0.0.0.0 --port 8000"
timeout /t 5 >nul
start "HelpDesk PWA" cmd /k "cd /d %~dp0build\web && python -m http.server 8553 --bind 0.0.0.0"
timeout /t 2 >nul
start "HelpDesk App TI" cmd /k "cd /d %~dp0 && python main.py"
