@echo off
:: Duplo-clique como Administrador na maquina SHOPBASE (loja Host)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_loja_https.ps1" -Force
pause
