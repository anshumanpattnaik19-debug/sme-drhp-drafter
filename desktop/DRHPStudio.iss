; DRHP Studio installer (Inno Setup 6). Build with:
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" desktop\DRHPStudio.iss
; Requires the frozen app first in build\pyi\dist\DRHPStudio (see docs\INSTALLER.md for the PyInstaller command)
; Installs per user (no administrator rights). Issuer data is kept in %LOCALAPPDATA%\DRHP Studio and is not removed
; by the uninstaller.

#define MyAppName "DRHP Studio"
#define MyAppVersion "1.0.0"
#define MyAppExe "DRHPStudio.exe"

[Setup]
AppId={{4DED5FC8-DB33-41FD-BAAC-101A30A01E61}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=DRHP Studio project
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\build\installer
OutputBaseFilename=DRHPStudio-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExe}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\build\pyi\dist\DRHPStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Start {#MyAppName} now"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
