@echo off
setlocal EnableDelayedExpansion
title ARKLAND - Configurar banco de dados

echo ============================================================
echo   ARKLAND - Bancos arkland_shop + ark_permission
echo ============================================================
echo.

:: ── Localiza o mysql.exe / mariadb.exe ─────────────────────
set MYSQL_EXE=

for %%D in (
    "C:\Program Files\MariaDB 11.4\bin\mysql.exe"
    "C:\Program Files\MariaDB 11.3\bin\mysql.exe"
    "C:\Program Files\MariaDB 11.2\bin\mysql.exe"
    "C:\Program Files\MariaDB 11.1\bin\mysql.exe"
    "C:\Program Files\MariaDB 11.0\bin\mysql.exe"
    "C:\Program Files\MariaDB 10.11\bin\mysql.exe"
    "C:\Program Files\MariaDB 10.6\bin\mysql.exe"
    "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
    "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe"
    "C:\xampp\mysql\bin\mysql.exe"
    "C:\wamp64\bin\mysql\mysql8.0.31\bin\mysql.exe"
) do (
    if exist %%D (
        set "MYSQL_EXE=%%~D"
        goto :found
    )
)

:: Tenta PATH
where mysql >nul 2>&1
if !errorlevel! == 0 (
    set "MYSQL_EXE=mysql"
    goto :found
)
where mariadb >nul 2>&1
if !errorlevel! == 0 (
    set "MYSQL_EXE=mariadb"
    goto :found
)

echo [ERRO] mysql.exe / mariadb.exe nao encontrado.
echo.
echo   Opcoes:
echo   1) Instale o MariaDB: https://mariadb.org/download/
echo   2) Adicione a pasta bin do MariaDB ao PATH do Windows
echo   3) Edite este .bat e defina MYSQL_EXE manualmente
echo.
pause
exit /b 1

:found
echo   Cliente: %MYSQL_EXE%
echo.

:: ── Pede senha do root ──────────────────────────────────────
set /p ROOT_PASS=Digite a senha do usuario root do MySQL/MariaDB: 

:: ── Pede senha para o usuario arkland ──────────────────────
echo.
set /p ARKLAND_PASS=Defina uma senha para o usuario 'arkland' da loja: 

:: ── Substitui placeholder no SQL ───────────────────────────
set "SQL_FILE=%~dp0setup_db.sql"
set "SQL_TMP=%~dp0setup_db_tmp.sql"

powershell -NoProfile -Command ^
  "(Get-Content '%SQL_FILE%') -replace 'SUA_SENHA_AQUI', '%ARKLAND_PASS%' | Set-Content '%SQL_TMP%' -Encoding UTF8"

echo.
echo [1/2] Criando banco de dados...
"%MYSQL_EXE%" -u root -p%ROOT_PASS% < "%SQL_TMP%"
if !errorlevel! neq 0 (
    del /f "%SQL_TMP%" 2>nul
    echo.
    echo [ERRO] Falha ao conectar ou executar o SQL.
    echo   Verifique a senha do root e se o MariaDB esta rodando.
    pause
    exit /b 1
)

del /f "%SQL_TMP%" 2>nul

echo.
echo [2/2] Atualizando config.json do CustomShop...

:: ── Atualiza configs do CustomShop e Permissions ────────────
set "CFG_CS=%~dp0plugin\CustomShop\bin\config.json"
if exist "%CFG_CS%" (
    powershell -NoProfile -Command ^
      "(Get-Content '%CFG_CS%') -replace '\"Password\":\s*\"[^\"]*\"', '\"Password\": \"%ARKLAND_PASS%\"' | Set-Content '%CFG_CS%' -Encoding UTF8"
    echo   CustomShop config.json atualizado.
)

set "CFG_PERM=%~dp0plugin\Permissions\configs\config.json"
if exist "%CFG_PERM%" (
    powershell -NoProfile -Command ^
      "(Get-Content '%CFG_PERM%') -replace '\"MysqlPass\":\s*\"[^\"]*\"', '\"MysqlPass\": \"%ARKLAND_PASS%\"' | Set-Content '%CFG_PERM%' -Encoding UTF8"
    echo   Permissions config.json atualizado.
)

echo.
echo ============================================================
echo   BANCOS CRIADOS COM SUCESSO!
echo.
echo   Host     : 127.0.0.1
echo   Porta    : 3306
echo   Usuario  : arkland
echo   Senha    : (a que voce definiu acima)
echo.
echo   Bancos:
echo     - arkland_shop    (CustomShop + Web Store)
echo     - ark_permission  (Permissions.dll — tabelas criadas no 1o start)
echo.
echo   Configure esses valores em:
echo     - CustomShop: ArkApi/Plugins/CustomShop/config.json ^> Database
echo     - Permissions: ArkApi/Plugins/Permissions/config.json
echo     - App ARKLAND: aba Loja ^> Web Store ^> Banco de dados
echo ============================================================
echo.
pause
