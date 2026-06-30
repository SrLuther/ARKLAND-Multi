; ============================================================
; Inno Setup Script ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ARKLAND - Server Manager Installer
; Requer: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
; Antes de gerar o installer, rode build.bat para criar o .exe
;
; InstalaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o silenciosa:
;   ARKLAND-ServerManager-Setup-vX.Y.Z.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
; ============================================================

; Atualizado automaticamente por _release.ps1
#define ReleaseVersion "1.9.168"

[Setup]
AppName=ARKLAND - Server Manager
AppVersion={#ReleaseVersion}
AppPublisher=ARKLAND Tools
AppPublisherURL=https://github.com/SrLuther/ARKLAND-Multi
AppSupportURL=https://github.com/SrLuther/ARKLAND-Multi/issues
AppUpdatesURL=https://github.com/SrLuther/ARKLAND-Multi/releases
DefaultDirName={autopf}\ARKLAND-ServerManager
DefaultGroupName=ARKLAND-ServerManager
OutputDir=installer
OutputBaseFilename=ARKLAND-Multi-Setup-v{#ReleaseVersion}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
; NÃƒÆ’Ã‚Â£o exige UAC (instala por usuÃƒÆ’Ã‚Â¡rio se nÃƒÆ’Ã‚Â£o admin)
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
; Fecha instÃƒÆ’Ã‚Â¢ncia anterior automaticamente durante atualizaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o
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
Name: "desktopicon"; Description: "Criar atalho na ÃƒÆ’Ã‚Â¡rea de trabalho"; GroupDescription: "Atalhos:"

[Run]
; Abre o app ao final da instalaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o (sÃƒÆ’Ã‚Â³ no modo nÃƒÆ’Ã‚Â£o-silencioso)
Filename: "{app}\ARKLAND-ServerManager.exe"; \
  Description: "Iniciar ARKLAND - Server Manager agora"; \
  Flags: nowait postinstall skipifsilent shellexec runascurrentuser

[UninstallDelete]
; Remove dados do usuÃƒÆ’Ã‚Â¡rio ao desinstalar (sÃƒÆ’Ã‚Â³ se o usuÃƒÆ’Ã‚Â¡rio confirmar ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â use comentÃƒÆ’Ã‚Â¡rio para remover)
; Type: filesandordirs; Name: "{userappdata}\ARKLAND-ServerManager"
