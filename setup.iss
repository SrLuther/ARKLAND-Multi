; ============================================================
; Inno Setup Script — [ARKLAND]-Multi Installer
; Requer: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
; Antes de gerar o installer, rode build.bat para criar o .exe
; ============================================================

[Setup]
AppName=[ARKLAND]-Multi
AppVersion=1.0.5
AppPublisher=ARKLAND Tools
DefaultDirName={autopf}\ARKLAND-Multi
DefaultGroupName=ARKLAND-Multi
OutputDir=installer
OutputBaseFilename=ARKLAND-Multi-Setup-v1.0.5
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayName=[ARKLAND]-Multi
SetupIconFile=ig\ArkLandBR.ico
WizardImageFile=ig\ArkLandBR_wizard.png
WizardImageStretch=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "dist\ARKLAND-Multi.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\[ARKLAND]-Multi";    Filename: "{app}\ARKLAND-Multi.exe"
Name: "{userdesktop}\[ARKLAND]-Multi"; Filename: "{app}\ARKLAND-Multi.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Run]
Filename: "{app}\ARKLAND-Multi.exe"; \
  Description: "Iniciar [ARKLAND]-Multi agora"; \
  Flags: nowait postinstall skipifsilent
