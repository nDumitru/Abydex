; Inno Setup script - builds Forja3D-Setup-<version>.exe
; The app folder (build\app) is prepared by packaging\windows\build.ps1
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6E0B7C9A-3F1D-4C55-9C1E-F0A1D3D3F3D1}
AppName=Forja3D
AppVersion={#AppVersion}
AppPublisher=Forja3D contributors
DefaultDirName={localappdata}\Programs\Forja3D
DefaultGroupName=Forja3D
; per-user install: no admin needed, and AI engines can be installed later without admin
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=Forja3D-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
WizardStyle=modern
LicenseFile=..\..\LICENSE
UninstallDisplayName=Forja3D

[Languages]
; Romanian is not bundled with Inno Setup (unofficial translation) - English for now
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\build\app\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Forja3D"; Filename: "{app}\Forja3D.cmd"; WorkingDir: "{app}"
Name: "{group}\Forja3D - linie de comanda"; Filename: "{cmd}"; Parameters: "/k ""{app}\bin\forja3d.cmd"" --help"; WorkingDir: "{userdocs}"
Name: "{group}\{cm:UninstallProgram,Forja3D}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Forja3D"; Filename: "{app}\Forja3D.cmd"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Forja3D.cmd"; Description: "{cm:LaunchProgram,Forja3D}"; Flags: nowait postinstall skipifsilent shellexec
