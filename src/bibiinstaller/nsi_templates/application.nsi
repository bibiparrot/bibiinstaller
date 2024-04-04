!define PRODUCT_NAME "[[ib.appname]]"
!define PRODUCT_VERSION "[[ib.version]]"
!define PY_VERSION "[[ib.py_version]]"
!define PY_MAJOR_VERSION "[[ib.py_major_version]]"
!define BITNESS "[[ib.py_bitness]]"
!define ARCH_TAG "[[arch_tag]]"
!define INSTALLER_NAME "[[ib.installer_name]]"
!define PRODUCT_ICON "[[icon]]"

; Marker file to tell the uninstaller that it's a user installation
!define USER_INSTALL_MARKER _user_install_marker

SetCompressor lzma

!if "${NSIS_PACKEDVERSION}" >= 0x03000000
  Unicode true
  ManifestDPIAware true
!endif

!define MULTIUSER_EXECUTIONLEVEL Highest
!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_VALUENAME "InstallLocation"
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_VALUENAME "InstallLocation"
!define MULTIUSER_MUI
!define MULTIUSER_INSTALLMODE_COMMANDLINE
!define MULTIUSER_INSTALLMODE_INSTDIR "[[ib.appname]]"
[% if ib.py_bitness == 64 %]
!define MULTIUSER_INSTALLMODE_FUNCTION correct_prog_files
[% endif %]
!include MultiUser.nsh
!include FileFunc.nsh
!include LogicLib.nsh


[% block modernui %]
; Modern UI installer stuff
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "[[icon]]"
!define MUI_UNICON "[[icon]]"

; UI pages
[% block ui_pages %]
!define MUI_PAGE_CUSTOMFUNCTION_PRE validate_pre_install
!insertmacro MUI_PAGE_WELCOME
[% if license_file %]
!define MUI_PAGE_CUSTOMFUNCTION_PRE validate_updating_and_skip
!insertmacro MUI_PAGE_LICENSE [[license_file]]
[% endif %]
!insertmacro MULTIUSER_PAGE_INSTALLMODE
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Start Spyder"
!define MUI_FINISHPAGE_RUN_FUNCTION "LaunchLink"
!insertmacro MUI_PAGE_FINISH
[% endblock ui_pages %]
!insertmacro MUI_LANGUAGE "English"
[% endblock modernui %]

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "${INSTALLER_NAME}"
ShowInstDetails show

; Variables used globally
Var cmdLineInstallDir
Var previousInstallationUninstaller
Var previousInstallationLocation
Var updatingInstallation

Section -SETTINGS
  SetOutPath "$INSTDIR"
  SetOverwrite on
SectionEnd

[% block sections %]

Section "!${PRODUCT_NAME}" sec_app
  SetRegView [[ib.py_bitness]]
  SectionIn RO
  File ${PRODUCT_ICON}
  [% block install_pkgs %]
    [#
      Extend this block if you need to remove the pkgs directory if it already
      exists from previous installations (when upgrading without uninstalling).
      https://github.com/takluyver/pynsist/issues/66
      Example:
      [% block install_pkgs %]
        RMDir /r "$INSTDIR\pkgs"
        [[ super() ]]
      [% endblock install_pkgs %]
    #]
    ; Copy pkgs data
    SetOutPath "$INSTDIR\pkgs"
    File /r "pkgs\*.*"
  [% endblock install_pkgs %]
  SetOutPath "$INSTDIR"

  ; Marker file for per-user install
  StrCmp $MultiUser.InstallMode CurrentUser 0 +3
    FileOpen $0 "$INSTDIR\${USER_INSTALL_MARKER}" w
    FileClose $0
    SetFileAttributes "$INSTDIR\${USER_INSTALL_MARKER}" HIDDEN

  [% block install_files %]
  ; Install files
  [% for destination, group in grouped_files %]
    SetOutPath "[[destination]]"
    SetOverwrite on
    [% for file in group %]
      File "[[ file ]]"
    [% endfor %]
  [% endfor %]

  ; Install directories
  [% for dir, destination in ib.install_dirs %]
    SetOutPath "[[ pjoin(destination, dir) ]]"
    File /r "[[dir]]\*.*"
  [% endfor %]

  ; Install MSVCRT if it's not already on the system
  IfFileExists "$SYSDIR\ucrtbase.dll" skip_msvcrt
  SetOutPath $INSTDIR\Python
  [% for file in ib.msvcrt_files %]
    File msvcrt\[[file]]
  [% endfor %]
  skip_msvcrt:

  [% endblock install_files %]

  [% block install_shortcuts %]
  ; Install shortcuts
  ; The output path becomes the working directory for shortcuts
  SetOutPath "%HOMEDRIVE%\%HOMEPATH%"
  [% if single_shortcut %]
    [% for scname, sc in ib.shortcuts.items() %]
    CreateShortCut "$SMPROGRAMS\[[scname]].lnk" "[[sc['target'] ]]" \
      '[[ sc['parameters'] ]]' "$INSTDIR\[[ sc['icon'] ]]"
    ; Set AppUserModelID for pinned shortcuts
    WinShell::SetLnkAUMI "$SMPROGRAMS\[[scname]].lnk" "[[scname]].${PRODUCT_NAME}"
    [% endfor %]
  [% else %]
    [# Multiple shortcuts: create a directory for them #]
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    [% for scname, sc in ib.shortcuts.items() %]
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\[[scname]].lnk" "[[sc['target'] ]]" \
      '[[ sc['parameters'] ]]' "$INSTDIR\[[ sc['icon'] ]]"
    [% endfor %]
    ; Set AppUserModelID for pinned shortcuts
    WinShell::SetLnkAUMI "$SMPROGRAMS\${PRODUCT_NAME}\[[scname]].lnk" "[[scname]].${PRODUCT_NAME}"
  [% endif %]
  SetOutPath "$INSTDIR"

  ; Set context menu entry
  WriteRegStr SHCTX "Software\Classes\*\shell\edit_with_${PRODUCT_NAME}" "MUIVerb" "Edit with ${PRODUCT_NAME}"
  WriteRegStr SHCTX "Software\Classes\*\shell\edit_with_${PRODUCT_NAME}" "Icon" "$INSTDIR\${PRODUCT_ICON}"
  WriteRegStr SHCTX "Software\Classes\*\shell\edit_with_${PRODUCT_NAME}\command" "" \
    '"$INSTDIR\Python\pythonw.exe" "$INSTDIR\${PRODUCT_NAME}.launch.pyw" "%1"'

  [% endblock install_shortcuts %]

  [% block install_commands %]
  [% if has_commands %]
    DetailPrint "Setting up command-line launchers..."

    StrCmp $MultiUser.InstallMode CurrentUser 0 AddSysPathSystem
      ; Add to PATH for current user
      nsExec::ExecToLog '[[ python ]] -Es "$INSTDIR\_system_path.py" add_user "$INSTDIR\bin"'
      GoTo AddedSysPath
    AddSysPathSystem:
      ; Add to PATH for all users
      nsExec::ExecToLog '[[ python ]] -Es "$INSTDIR\_system_path.py" add "$INSTDIR\bin"'
    AddedSysPath:
  [% endif %]
  [% endblock install_commands %]

  ; Byte-compile Python files.
  DetailPrint "Byte-compiling Python modules..."
  nsExec::ExecToLog '[[ python ]] -m compileall -q "$INSTDIR\pkgs"'
  WriteUninstaller $INSTDIR\uninstall.exe
  ; Add ourselves to Add/remove programs
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "InstallLocation" "$INSTDIR"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "DisplayIcon" "$INSTDIR\${PRODUCT_ICON}"
  [% if ib.publisher is not none %]
    WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                     "Publisher" "[[ib.publisher]]"
  [% endif %]
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "NoModify" 1
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                   "NoRepair" 1

  ; Check if we need to reboot
  IfRebootFlag 0 noreboot
    MessageBox MB_YESNO "A reboot is required to finish the installation. Do you wish to reboot now?" \
                /SD IDNO IDNO noreboot
      Reboot
  noreboot:
SectionEnd

Section "Uninstall"
  SetRegView [[ib.py_bitness]]
  SetShellVarContext all
  IfFileExists "$INSTDIR\${USER_INSTALL_MARKER}" 0 +3
    SetShellVarContext current
    Delete "$INSTDIR\${USER_INSTALL_MARKER}"

  Delete $INSTDIR\uninstall.exe
  Delete "$INSTDIR\${PRODUCT_ICON}"
  RMDir /r "$INSTDIR\pkgs"

  ; Remove ourselves from %PATH%
  [% block uninstall_commands %]
  [% if has_commands %]
    nsExec::ExecToLog '[[ python ]] -Es "$INSTDIR\_system_path.py" remove "$INSTDIR\bin"'
  [% endif %]
  [% endblock uninstall_commands %]

  [% block uninstall_files %]
  ; Uninstall files
  [% for file, destination in ib.install_files %]
    Delete "[[pjoin(destination, file)]]"
  [% endfor %]
  ; Uninstall directories
  [% for dir, destination in ib.install_dirs %]
    RMDir /r "[[pjoin(destination, dir)]]"
  [% endfor %]
  [% endblock uninstall_files %]

  [% block uninstall_shortcuts %]
  ; Uninstall shortcuts
  [% if single_shortcut %]
    [% for scname in ib.shortcuts %]
      WinShell::UninstAppUserModelId "[[scname]].${PRODUCT_NAME}"
      WinShell::UninstShortcut "$SMPROGRAMS\[[scname]].lnk"
      Delete "$SMPROGRAMS\[[scname]].lnk"
    [% endfor %]
  [% else %]
    [% for scname in ib.shortcuts %]
      WinShell::UninstAppUserModelId "[[scname]].${PRODUCT_NAME}"
      WinShell::UninstShortcut "$SMPROGRAMS\${PRODUCT_NAME}\[[scname]].lnk"
    [% endfor %]
    RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
  [% endif %]
  DeleteRegKey SHCTX "Software\Classes\*\shell\edit_with_${PRODUCT_NAME}"
  [% endblock uninstall_shortcuts %]
  RMDir $INSTDIR
  DeleteRegKey SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd

[% endblock sections %]

; Functions

Function trim_quotes
  Exch $R0
  Push $R1

    StrCpy $R1 $R0 1
    StrCmp $R1 `"` 0 +2
      StrCpy $R0 $R0 `` 1
    StrCpy $R1 $R0 1 -1
    StrCmp $R1 `"` 0 +2
      StrCpy $R0 $R0 -1

  Pop $R1
  Exch $R0
FunctionEnd

!macro _TrimQuotes Input Output
  Push `${Input}`
  Call trim_quotes
  Pop ${Output}
!macroend
!define TrimQuotes `!insertmacro _TrimQuotes`

Function .onMouseOverSection
    ; Find which section the mouse is over, and set the corresponding description.
    FindWindow $R0 "#32770" "" $HWNDPARENT
    GetDlgItem $R0 $R0 1043 ; description item (must be added to the UI)

    [% block mouseover_messages %]
    StrCmp $0 ${sec_app} "" +2
      SendMessage $R0 ${WM_SETTEXT} 0 "STR:${PRODUCT_NAME}"

    [% endblock mouseover_messages %]
FunctionEnd

Function .onInit
  ; Multiuser.nsh breaks /D command line parameter. Parse /INSTDIR instead.
  ; Cribbing from https://nsis-dev.github.io/NSIS-Forums/html/t-299280.html
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} '$0' "/INSTDIR=" $1
  IfErrors +2  ; Error means flag not found
    StrCpy $cmdLineInstallDir $1
  ClearErrors
 
  !insertmacro MULTIUSER_INIT

  ; If cmd line included /INSTDIR, override the install dir set by MultiUser
  StrCmp $cmdLineInstallDir "" +2
    StrCpy $INSTDIR $cmdLineInstallDir 
FunctionEnd

Function un.onInit
  !insertmacro MULTIUSER_UNINIT
FunctionEnd

[% if ib.py_bitness == 64 %]
Function correct_prog_files
  ; The multiuser machinery doesn't know about the different Program files
  ; folder for 64-bit applications. Override the install dir it set.
  StrCmp $MultiUser.InstallMode AllUsers 0 +2
    StrCpy $INSTDIR "$PROGRAMFILES64\${MULTIUSER_INSTALLMODE_INSTDIR}"
FunctionEnd
[% endif %]

Function LaunchLink
 Exec '"$WINDIR\explorer.exe" "$SMPROGRAMS\Spyder.lnk"'
FunctionEnd

Function validate_updating_and_skip
  ${If} $updatingInstallation == 1
    Abort
  ${EndIf}
FunctionEnd

Function validate_pre_install

  ; Check to see if application is already installed for all the users and installation location (need for admin rights to proceed if that is the case)
  SetRegView [[ib.py_bitness]]
  ReadRegStr $previousInstallationLocation HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                                              "InstallLocation"
  ReadRegStr $previousInstallationUninstaller HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                                              "UninstallString"
  ${IfNot} $MultiUser.Privileges == "Admin"
      ${AndIfNot} $previousInstallationUninstaller == ""
          MessageBox MB_OK|MB_ICONSTOP|MB_TOPMOST "${PRODUCT_NAME} is installed for all users and the current user doesn't have permissions to modify it.\
                                       $\r$\n$\r$\nIf you want to modify the current installation you need to use an account with Administrator rights." \
                                       /SD IDOK IDOK NoUninstall
  ${EndIf}

  ; Validate if application is currently running
  FindWindow $0 "" "${PRODUCT_NAME}"
  IntCmp $0 0 notRunning
    MessageBox MB_YESNO|MB_ICONINFORMATION|MB_TOPMOST "${PRODUCT_NAME} is running. It is necessary to close it before installing a new version. Do you want to close ${PRODUCT_NAME} now?" \
                                                      /SD IDYES IDYES Confirm IDNO NoClose
          Confirm:
            MessageBox MB_YESNO|MB_ICONINFORMATION|MB_TOPMOST "All unsaved files and changes will be lost. In addition, any program that you are running in ${PRODUCT_NAME}'s IPython console will be stopped. \
                                                              $\r$\n$\r$\nAre you sure you want to close ${PRODUCT_NAME}?" \
                                                              /SD IDYES IDYES CloseSpyder IDNO NoClose
            CloseSpyder:
              Banner::show /set 76 "Please wait while closing ${PRODUCT_NAME}..." " "
              nsExec::Exec 'TaskKill /FI "WINDOWTITLE eq Spyder" /F /T'
              Banner::destroy
              GoTo notRunning
          NoClose:
            Quit
  notRunning:
  ${If} $previousInstallationUninstaller == ""
      ReadRegStr $previousInstallationLocation HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                                              "InstallLocation"
      ReadRegStr $previousInstallationUninstaller HKCU "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                                              "UninstallString"
  ${EndIf}

  ; Remove quotes
  ${TrimQuotes} $previousInstallationLocation $previousInstallationLocation
  ${TrimQuotes} $previousInstallationUninstaller $previousInstallationUninstaller

  ; Validate if a previous installation actually exists and proceed with the uninstall and marking the execution as an update if needed
  IfFileExists $previousInstallationUninstaller Installed NotInstalled
  Installed:
    MessageBox MB_YESNO|MB_ICONINFORMATION|MB_TOPMOST "${PRODUCT_NAME} is already installed. Uninstall the existing version?" \
                                            /SD IDYES IDYES UninstallPreviousInstallation IDNO NoUninstall
  UninstallPreviousInstallation:
    Banner::show /set 76 "Please wait while uninstalling ${PRODUCT_NAME}..." " "
    CreateDirectory $TEMP\spyder-uninstaller
    CopyFiles /SILENT "$previousInstallationUninstaller" $TEMP\spyder-uninstaller\uninstall.exe
    ExecWait '"$TEMP\spyder-uninstaller\uninstall.exe" /S _?=$previousInstallationLocation'
    RMDir /r $TEMP\spyder-uninstaller
    Banner::destroy
    StrCpy $updatingInstallation 1
    Abort
    GoTo NotInstalled
  NoUninstall:
    Quit
  NotInstalled:
FunctionEnd
