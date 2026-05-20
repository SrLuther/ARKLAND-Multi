; ============================================================
; Inno Setup Script â€” ARKLAND - Server Manager Installer
; Requer: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
; Antes de gerar o installer, rode build.bat para criar o .exe
;
; InstalaÃ§Ã£o silenciosa:
;   ARKLAND-ServerManager-Setup-vX.Y.Z.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
; ============================================================

[Setup]
AppName=ARKLAND - Server Manager
AppVersion=1.3.8
AppPublisher=ARKLAND Tools
AppPublisherURL=https://github.com/SrLuther/ARKLAND-Multi
AppSupportURL=https://github.com/SrLuther/ARKLAND-Multi/issues
AppUpdatesURL=https://github.com/SrLuther/ARKLAND-Multi/releases
DefaultDirName={autopf}\ARKLAND-ServerManager
DefaultGroupName=ARKLAND-ServerManager
OutputDir=installer
OutputBaseFilename=ARKLAND-Multi-Setup-v1.3.8
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
; NÃ£o exige UAC (instala por usuÃ¡rio se nÃ£o admin)
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
; Fecha instÃ¢ncia anterior automaticamente durante atualizaÃ§Ã£o
CloseApplications=yes
CloseApplicationsFilter=*ARKLAND-ServerManager.exe
RestartApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "dist\ARKLAND-ServerManager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\ARKLAND-Updater.exe";       DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ARKLAND - Server Manager";       Filename: "{app}\ARKLAND-ServerManager.exe"
Name: "{userdesktop}\ARKLAND - Server Manager"; Filename: "{app}\ARKLAND-ServerManager.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Ã¡rea de trabalho"; GroupDescription: "Atalhos:"

[Run]
; Abre o app ao final da instalaÃ§Ã£o (sÃ³ no modo nÃ£o-silencioso)
Filename: "{app}\ARKLAND-ServerManager.exe"; \
  Description: "Iniciar ARKLAND - Server Manager agora"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove dados do usuÃ¡rio ao desinstalar (sÃ³ se o usuÃ¡rio confirmar â€” use comentÃ¡rio para remover)
; Type: filesandordirs; Name: "{userappdata}\ARKLAND-ServerManager"
