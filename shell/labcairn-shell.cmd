@echo off
rem T09 supply, way 1: an operator-edited launcher that names the packaged
rem shell's backend and workspace before LabCairn.exe starts. The shell itself
rem reads only the environment (LABCAIRN_SHELL_CLI, LABCAIRN_SHELL_WORKSPACE);
rem this template ships beside the installer so the values are set in one
rem editable place instead of being guessed at startup. Copy it next to the
rem installed LabCairn.exe, edit the two set lines, and run it instead of the
rem exe. The environment always wins over resources\shell-env.json, so this
rem launcher is the override; a package whose resources\shell-env.json already
rem names the frozen backend (resources\backend\labcairn) and the workspace
rem needs no launcher at all.
setlocal
rem EDIT ME: absolute path to the labcairn entry point the installation carries
rem (the frozen service ships at resources\backend\labcairn\labcairn.exe).
set "LABCAIRN_SHELL_CLI=C:\Program Files\LabCairn\resources\backend\labcairn\labcairn.exe"
rem EDIT ME: absolute path to the workspace the runs share.
set "LABCAIRN_SHELL_WORKSPACE=C:\Users\%USERNAME%\LabCairn-workspace"
start "" "%~dp0LabCairn.exe"
endlocal
