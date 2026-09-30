@echo off
REM Libera as portas 8000 (API) e 8553 (app web/PWA) no firewall do Windows (rodar 1x como Admin)
REM [CLAUDE 24/09] profile=private nao bastava: o Windows classifica muitas redes Wi-Fi
REM (principalmente sem dominio/empresa configurado) como "Publica", e nesse caso a regra
REM "private" e ignorada -- o firewall bloqueia o celular mesmo com o servidor rodando.
REM Trocado pra profile=any (vale em qualquer perfil de rede: dominio, privada ou publica).
netsh advfirewall firewall delete rule name="HelpDesk 8000" >nul 2>&1
netsh advfirewall firewall add rule name="HelpDesk 8000" dir=in action=allow protocol=TCP localport=8000 profile=any
netsh advfirewall firewall delete rule name="HelpDesk 8553" >nul 2>&1
netsh advfirewall firewall add rule name="HelpDesk 8553" dir=in action=allow protocol=TCP localport=8553 profile=any
echo Regras criadas (portas 8000 e 8553, qualquer perfil de rede). Rode iniciar_helpdesk.bat normalmente.
pause
