@echo off
REM Install a nanoamp.cmd wrapper into a directory on PATH.
setlocal
set "DEST=%~1"
if "%DEST%"=="" set "DEST=%USERPROFILE%\bin"
if not exist "%DEST%" mkdir "%DEST%"

> "%DEST%\nanoamp.cmd" echo @echo off
>> "%DEST%\nanoamp.cmd" echo Rscript --vanilla "%~dp0nanoamp.R" %%*

echo Installed: %DEST%\nanoamp.cmd
echo Add %DEST% to PATH if it is not there yet.
endlocal
