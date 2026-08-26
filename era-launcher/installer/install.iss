[Script]
; Inno Setup script for EraLauncher Web Installer
; Alternative to NSIS (install.nsi)
;
; Build: ISCC install.iss
;
; This packages the era-launcher-web-installer.exe into a polished
; Windows installer. The web installer downloads the actual launcher
; binary and Java at install time, similar to SKlauncher's approach.

#define MyAppName "EraLauncher"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "EraLauncher Project"
#define MyAppURL "https://github.com/EraLauncher/era-launcher"
#define MyAppExe "era-launcher.exe"
#define MyInstallerExe "era-launcher-web-installer.exe"

[Setup]
AppId={{E8A5E3B0-1234-4321-ABCD-567890ABCDEF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\EraLauncher
DefaultGroupName={#MyAppName}
OutputBaseFilename=era-launcher-web-setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
LicenseFile=LICENSE

[Files]
Source: "{#MyInstallerExe}"; DestDir: "{app}"; Flags: ignoreversion

[Run]
; Run the web installer — it downloads the launcher binary and Java
Filename: "{app}\{#MyInstallerExe}"; Parameters: "--install"; Flags: runhidden waituntilterminated postinstall
Filename: "{app}\{#MyAppExe}"; Description: "Launch EraLauncher"; Flags: nowait postinstall skipifsilent

[Icons]
Name: "{autogroup}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[UninstallDelete]
Type: filesanddirs; Name: "{app}\runtimes"
