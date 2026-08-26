; NSIS Installer script for EraLauncher Web Installer
; Inspired by SKlauncher-4.0.29-web-setup.exe
;
; This script packages the era-launcher-web-installer binary into a
; polished Windows installer with progress bar, license agreement,
; and installation directory selection.
;
; Build: makensis install.nsi
;
; Prerequisites:
;   - era-launcher-web-installer.exe (built from src/bin/era-launcher-web-installer.rs)
;   - Or use the pre-built bootstrap from GitHub releases

!define APP_NAME "EraLauncher"
!define APP_VERSION "0.1.0"
!define APP_PUBLISHER "EraLauncher Project"
!define APP_WEBSITE "https://github.com/EraLauncher/era-launcher"
!define INSTALLER_NAME "era-launcher-web-setup"
!define UNINSTALL_REGKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\EraLauncher"

;--------------------------------
; Includes
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

;--------------------------------
; Variables
Var StartMenuFolder
Var StartMenuFolderHandle
Var Shortcuts
Var InstallJava

;--------------------------------
; General
Name "EraLauncher ${APP_VERSION}"
OutFile "${INSTALLER_NAME}.exe"
InstallDir "$LOCALAPPDATA\EraLauncher"
InstallDirRegKey HKLM "${UNINSTALL_REGKEY}" "Install_Dir"
ShowInstCreatorError show

; Set the window icon
!define MUI_ICON "assets\installer_icon.ico"
!define MUI_UNICON "assets\uninstaller_icon.ico"

;--------------------------------
; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
; Language
!insertmacro MUI_LANGUAGE "English"

;--------------------------------
; Settings
RequestExecutionLevel user

;--------------------------------
; Welcome page
!insertmacro MUI_WELCOMEFUNC_INSTALLSTART
function .onInit
    StrCpy $InstallJava 1
    StrCpy $Shortcuts 1
function .onInitEnd

!insertmacro MUI_WELCOMEFUNC_INSTALLEND

;--------------------------------
; Install
Section "MainSection" SEC01
    ; Set output path
    SetOutPath "$INSTDIR"

    ; Copy the web installer
    File "era-launcher-web-installer.exe"

    ; Run the web installer with appropriate flags
    ; The web installer downloads:
    ; 1. era-launcher binary from GitHub releases
    ; 2. Java JRE from Adoptium/Temurin (if --no-java not passed)
    ; 3. Creates desktop shortcut (if --no-shortcut not passed)
    ;
    ; SKlauncher approach: download at install time, not bundled in installer

    nsExec::ExecToLog '"$INSTDIR\era-launcher-web-installer.exe" --install'

    ; Wait for the web installer to complete
    ; (it runs synchronously)

    ; Remove the web installer after completion
    Delete "$INSTDIR\era-launcher-web-installer.exe"

    WriteRegStr HKLM "${UNINSTALL_REGKEY}" "Install_Dir" "$INSTDIR"
    WriteRegStr HKLM "${UNINSTALL_REGKEY}" "DisplayIcon" "$INSTDIR\era-launcher.exe"
    WriteRegStr HKLM "${UNINSTALL_REGKEY}" "DisplayName" "EraLauncher"
    WriteRegStr HKLM "${UNINSTALL_REGKEY}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKLM "${UNINSTALL_REGKEY}" "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKLM "${UNINSTALL_REGKEY}" "URLInfoAbout" "${APP_WEBSITE}"
    WriteRegDWORD HKLM "${UNINSTALL_REGKEY}" "NoModify" 1
    WriteRegDWORD HKLM "${UNINSTALL_REGKEY}" "NoRepair" 1
    WriteRegStr HKLM "${UNINSTALL_REGKEY}" "UninstallString" "$\"$INSTDIR\uninstall.exe\""
SectionEnd

Section "Start Menu Shortcuts"
    SetOutPath "$INSTDIR"
    CreateDirectory "$SMPROGRAMS\EraLauncher"
    CreateShortCut "$SMPROGRAMS\EraLauncher\EraLauncher.lnk" "$INSTDIR\era-launcher.exe"
    CreateShortCut "$SMPROGRAMS\EraLauncher\Uninstall EraLauncher.lnk" "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\era-launcher.exe"
    Delete "$INSTDIR\uninstall.exe"
    RMDir /r "$INSTDIR\runtimes"
    RMDir "$INSTDIR"
    Delete "$SMPROGRAMS\EraLauncher\EraLauncher.lnk"
    Delete "$SMPROGRAMS\EraLauncher\Uninstall EraLauncher.lnk"
    RMDir "$SMPROGRAMS\EraLauncher"
    DeleteRegKey HKLM "${UNINSTALL_REGKEY}"
SectionEnd
