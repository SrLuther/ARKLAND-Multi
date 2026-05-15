; ============================================================
; Inno Setup Script — ARKLAND - Server Manager Installer
; Requer: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
; Antes de gerar o installer, rode build.bat para criar o .exe
;
; Instalação silenciosa:
;   ARKLAND-ServerManager-Setup-vX.Y.Z.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
; ============================================================

[Setup]
AppName=ARKLAND - Server Manager
AppVersion=1.1.9
AppPublisher=ARKLAND Tools
AppPublisherURL=https://github.com/SrLuther/ARKLAND-Multi
AppSupportURL=https://github.com/SrLuther/ARKLAND-Multi/issues
AppUpdatesURL=https://github.com/SrLuther/ARKLAND-Multi/releases
DefaultDirName={autopf}\ARKLAND-ServerManager
DefaultGroupName=ARKLAND-ServerManager
OutputDir=installer
OutputBaseFilename=ARKLAND-Multi-Setup-v1.1.9
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
; Não exige UAC (instala por usuário se não admin)
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
; Fecha instância anterior automaticamente durante atualização
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
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Run]
; Abre o app ao final da instalação (só no modo não-silencioso)
Filename: "{app}\ARKLAND-ServerManager.exe"; \
  Description: "Iniciar ARKLAND - Server Manager agora"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove dados do usuário ao desinstalar (só se o usuário confirmar — use comentário para remover)
; Type: filesandordirs; Name: "{userappdata}\ARKLAND-ServerManager"
