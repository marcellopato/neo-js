; Inno Setup Script for Neo Assistente por Voz (Windows 10/11)
[Setup]
AppId={{9F4E2B51-73A8-4E2A-9D1C-6C873E9F4A10}
AppName=Neo Assistente por Voz
AppVersion=1.1.0
AppPublisher=Marcello Pato (Neo.JS)
AppPublisherURL=https://github.com/marcellopato/neo-js
DefaultDirName={localappdata}\Programs\NeoAssistente
DefaultGroupName=Neo Assistente por Voz
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Neo-Assistente-Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"
Name: "startupicon"; Description: "Iniciar o Neo automaticamente junto com o Windows (Recomendado)"; GroupDescription: "Inicialização:"

[Files]
Source: "..\dist\NeoAssistente\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Neo Assistente por Voz"; Filename: "{app}\NeoAssistente.exe"; Parameters: "--setup"
Name: "{autodesktop}\Neo Assistente por Voz"; Filename: "{app}\NeoAssistente.exe"; Parameters: "--setup"; Tasks: desktopicon
Name: "{userstartup}\Neo Assistente por Voz"; Filename: "{app}\NeoAssistente.exe"; Tasks: startupicon

[Run]
Filename: "{app}\NeoAssistente.exe"; Parameters: "--setup"; Description: "Abrir o Neo Assistente agora para configurar"; Flags: nowait postinstall

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM NeoAssistente.exe /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
