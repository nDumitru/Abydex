; Inno Setup script - builds Abydex-Setup-<version>.exe
; The app folder (build\app) is prepared by packaging\windows\build.ps1
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
; numeric part only (0.2.0-beta.1 -> 0.2.0), Windows file versions must be numbers
#ifndef NumVersion
  #define NumVersion "0.1.0"
#endif

[Setup]
AppId={{6E0B7C9A-3F1D-4C55-9C1E-F0A1D3D3F3D1}
AppName=Abydex
AppVersion={#AppVersion}
AppPublisher=Abydex contributors
AppPublisherURL=https://github.com/nDumitru/abydex
AppUpdatesURL=https://github.com/nDumitru/abydex/releases
VersionInfoVersion={#NumVersion}
DefaultDirName={localappdata}\Programs\Abydex
DefaultGroupName=Abydex
; per-user install: no admin needed, and AI engines can be installed later without admin
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=Abydex-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
WizardStyle=modern
LicenseFile=..\..\LICENSE
UninstallDisplayName=Abydex
SetupIconFile=..\..\abydex\webui\static\abydex.ico
UninstallDisplayIcon={app}\abydex.ico
; same AppId as Forja3D (the old name): installing Abydex upgrades it in place

[Languages]
; Romanian is not bundled with Inno Setup (unofficial translation) - English for now
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; leftovers of the old name (Forja3D, before v0.3.0)
Type: files; Name: "{app}\Forja3D.cmd"
Type: filesandordirs; Name: "{app}\python\Lib\site-packages\forja3d"
Type: filesandordirs; Name: "{app}\python\Lib\site-packages\forja3d-*.dist-info"
Type: filesandordirs; Name: "{autoprograms}\Forja3D"
Type: files; Name: "{autodesktop}\Forja3D.lnk"

[Files]
Source: "..\..\build\app\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Abydex"; Filename: "{app}\Abydex.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\abydex.ico"
Name: "{group}\Abydex - linie de comanda"; Filename: "{cmd}"; Parameters: "/k ""{app}\bin\abydex.cmd"" --help"; WorkingDir: "{userdocs}"
Name: "{group}\{cm:UninstallProgram,Abydex}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Abydex"; Filename: "{app}\Abydex.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\abydex.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\Abydex.cmd"; Description: "{cm:LaunchProgram,Abydex}"; Flags: nowait postinstall skipifsilent shellexec
