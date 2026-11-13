@echo off
rem T09 supply, way 1: an operator-edited launcher that names the packaged
rem shell's backend and workspace before LabCairn.exe starts. The shell itself
rem reads only the environment (LABCAIRN_SHELL_CLI, LABCAIRN_SHELL_WORKSPACE);
rem this template ships beside the installer so the values are set in one
rem editable place instead of being guessed at startup. Copy it next to the
rem installed LabCairn.exe, edit the two set lines, and run it instead of the
rem exe. The environment always wins over resources\shell-env.json.
setlocal
rem EDIT ME: absolute path to the labcairn entry point the installation carries.
set "LABCAIRN_SHELL_CLI=C:\Program Files\LabCairn\backend\labcairn.exe"
rem EDIT ME: absolute path to the workspace the runs share.
set "LABCAIRN_SHELL_WORKSPACE=C:\Users\%USERNAME%\LabCairn-workspace"
start "" "%~dp0LabCairn.exe"
endlocal
