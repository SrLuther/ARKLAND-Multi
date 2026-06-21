; ============================================================
; Inno Setup Script Ã¢â‚¬â€ ARKLAND - Server Manager Installer
; Requer: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
; Antes de gerar o installer, rode build.bat para criar o .exe
;
; InstalaÃƒÂ§ÃƒÂ£o silenciosa:
;   ARKLAND-ServerManager-Setup-vX.Y.Z.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
; ============================================================

[Setup]
AppName=ARKLAND - Server Manager
AppVersion=1.9.50
AppPublisher=ARKLAND Tools
AppPublisherURL=https://github.com/SrLuther/ARKLAND-Multi
AppSupportURL=https://github.com/SrLuther/ARKLAND-Multi/issues
AppUpdatesURL=https://github.com/SrLuther/ARKLAND-Multi/releases
DefaultDirName={autopf}\ARKLAND-ServerManager
DefaultGroupName=ARKLAND-ServerManager
OutputDir=installer
OutputBaseFilename=ARKLAND-Multi-Setup-v1.9.50
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
; NÃƒÂ£o exige UAC (instala por usuÃƒÂ¡rio se nÃƒÂ£o admin)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName=ARKLAND - Server Manager
SetupIconFile=ig\ArkLandBR.ico
WizardImageFile=ig\ArkLandBR_wizard.png
WizardImageStretch=no
; Permite /VERYSILENT, /SILENT etc.
DisableWelcomePage=no
DisableDirPage=auto
DisableProgramGroupPage=yes
; Fecha instÃƒÂ¢ncia anterior automaticamente durante atualizaÃƒÂ§ÃƒÂ£o
CloseApplications=yes
CloseApplicationsFilter=*ARKLAND*.exe
RestartApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "dist\ARKLAND-ServerManager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\ARKLAND-Updater.exe";       DestDir: "{app}"; Flags: ignoreversion
Source: "dist\ARKLAND-WebStore.exe";       DestDir: "{app}"; Flags: ignoreversion
Source: "setup_db.sql"; DestDir: "{userappdata}\ARKLAND-ServerManager"; Flags: ignoreversion
Source: "setup_db.bat"; DestDir: "{userappdata}\ARKLAND-ServerManager"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{group}\ARKLAND - Server Manager";       Filename: "{app}\ARKLAND-ServerManager.exe"
Name: "{userdesktop}\ARKLAND - Server Manager"; Filename: "{app}\ARKLAND-ServerManager.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na ÃƒÂ¡rea de trabalho"; GroupDescription: "Atalhos:"

[Run]
; Abre o app ao final da instalaÃƒÂ§ÃƒÂ£o (sÃƒÂ³ no modo nÃƒÂ£o-silencioso)
Filename: "{app}\ARKLAND-ServerManager.exe"; \
  Description: "Iniciar ARKLAND - Server Manager agora"; \
  Flags: nowait postinstall skipifsilent shellexec runascurrentuser

[UninstallDelete]
; Remove dados do usuÃƒÂ¡rio ao desinstalar (sÃƒÂ³ se o usuÃƒÂ¡rio confirmar Ã¢â‚¬â€ use comentÃƒÂ¡rio para remover)
; Type: filesandordirs; Name: "{userappdata}\ARKLAND-ServerManager"
