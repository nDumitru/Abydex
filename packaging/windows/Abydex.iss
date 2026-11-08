; Inno Setup script - builds Abydex-Setup-<version>.exe
; The app folder (build\app) is prepared by packaging\windows\build.ps1
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
; numeric part only (0.2.0-beta.1 -> 0.2.0), Windows file versions must be numbers
; name used before v0.3.0 (only to clean up its files on upgrade)
#define OldApp "Forja3D"
#define OldPkg "forja3d"
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
; same AppId as the versions before v0.3.0: installing Abydex upgrades them in place

[Languages]
; Romanian is not bundled with Inno Setup (unofficial translation) - English for now
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; leftovers of the versions before v0.3.0 (old app name, see abydex/legacy.py)
Type: files; Name: "{app}\{#OldApp}.cmd"
Type: filesandordirs; Name: "{app}\python\Lib\site-packages\{#OldPkg}"
Type: filesandordirs; Name: "{app}\python\Lib\site-packages\{#OldPkg}-*.dist-info"
Type: filesandordirs; Name: "{autoprograms}\{#OldApp}"
Type: files; Name: "{autodesktop}\{#OldApp}.lnk"

[Files]
Source: "..\..\build\app\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Abydex"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m abydex app"; WorkingDir: "{app}"; IconFilename: "{app}\abydex.ico"; AppUserModelID: "Abydex.Desktop"
Name: "{group}\Abydex (mod depanare)"; Filename: "{app}\Abydex.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\abydex.ico"
Name: "{group}\Abydex - linie de comanda"; Filename: "{cmd}"; Parameters: "/k ""{app}\bin\abydex.cmd"" --help"; WorkingDir: "{userdocs}"
Name: "{group}\{cm:UninstallProgram,Abydex}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Abydex"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m abydex app"; WorkingDir: "{app}"; IconFilename: "{app}\abydex.ico"; AppUserModelID: "Abydex.Desktop"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-m abydex app"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,Abydex}"; Flags: nowait postinstall skipifsilent
; update started from inside the app (silent install): start the new version when done
Filename: "{app}\python\pythonw.exe"; Parameters: "-m abydex app"; WorkingDir: "{app}"; Flags: nowait; Check: AutoStart

[Code]
function AutoStart: Boolean;
begin
  Result := ExpandConstant('{param:AUTOSTART|0}') = '1';
end;
