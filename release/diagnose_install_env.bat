@echo off
REM Collect diagnosis info on a machine where install.exe appears to do nothing.
REM Run this from the folder that contains install.exe:
REM     diagnose_install_env.bat
REM It only reads. Nothing is installed, changed or deleted.
REM A file named nanoamp_diagnose.txt is produced - please send that back.

setlocal enabledelayedexpansion
set OUT=nanoamp_diagnose.txt
if exist "%OUT%" del "%OUT%"

echo =============== nanoamp install diagnosis ===============>>"%OUT%"
echo.>>"%OUT%"

echo --- 1. Windows version --->>"%OUT%"
ver>>"%OUT%" 2>&1
wmic os get Caption,Version,BuildNumber,OSArchitecture /value>>"%OUT%" 2>&1

echo.>>"%OUT%"
echo --- 2. memory and CPU --->>"%OUT%"
wmic computersystem get TotalPhysicalMemory /value>>"%OUT%" 2>&1
wmic os get FreePhysicalMemory /value>>"%OUT%" 2>&1
wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors /value>>"%OUT%" 2>&1

echo.>>"%OUT%"
echo --- 3. free disk space --->>"%OUT%"
wmic logicaldisk get DeviceID,Size,FreeSpace /value>>"%OUT%" 2>&1

echo.>>"%OUT%"
echo --- 4. is the bundle complete? --->>"%OUT%"
for %%F in (install.exe _offline "_offline\r\R-4.6.1-win.exe" "_offline\r-packages\bin\windows\contrib\4.6\PACKAGES" "01_R-package\nanoamp_0.1.0.tar.gz" "03_GUI\nanoamp.exe") do call :check "%%F" "%%F"
echo.>>"%OUT%"
echo R package .zip count, expect 109:>>"%OUT%"
set ZIPS=0
for %%Z in ("_offline\r-packages\bin\windows\contrib\4.6\*.zip") do set /a ZIPS+=1
echo   !ZIPS!>>"%OUT%"

echo.>>"%OUT%"
echo --- 5. previous attempts / existing install --->>"%OUT%"
call :check "%LOCALAPPDATA%\nanoamp" "install dir"
if not exist "%LOCALAPPDATA%\nanoamp\config.ini" goto nocfg
echo config.ini contents:>>"%OUT%"
type "%LOCALAPPDATA%\nanoamp\config.ini">>"%OUT%" 2>&1
goto cfgdone
:nocfg
echo MISSING config.ini - the install never finished>>"%OUT%"
:cfgdone
call :check "%LOCALAPPDATA%\nanoamp\R\lib\nanoamp" "nanoamp R package"
call :check "%LOCALAPPDATA%\nanoamp\app\nanoamp.exe" "GUI exe"
call :check "%LOCALAPPDATA%\nanoamp\bin\minimap2.exe" "minimap2"
call :check "%LOCALAPPDATA%\nanoamp\bin\nanoamp.cmd" "CLI launcher"
call :check "%LOCALAPPDATA%\nanoamp.path" "location pointer"
call :check "D:\nanoamp" "D:\nanoamp"

echo.>>"%OUT%"
echo --- 6. is R already installed? --->>"%OUT%"
call :check "C:\Program Files\R" "R (Program Files)"
call :check "C:\Program Files (x86)\R" "R (Program Files x86)"
call :check "D:\tools\R" "R (D:\tools\R)"
where Rscript>>"%OUT%" 2>&1
echo NANOAMP_RSCRIPT=%NANOAMP_RSCRIPT%>>"%OUT%"

echo.>>"%OUT%"
echo --- 7. leftover installer / R processes --->>"%OUT%"
tasklist /FI "IMAGENAME eq install.exe" /FO CSV /NH>>"%OUT%" 2>&1
tasklist /FI "IMAGENAME eq R-4.6.1-win.exe" /FO CSV /NH>>"%OUT%" 2>&1
tasklist /FI "IMAGENAME eq Rscript.exe" /FO CSV /NH>>"%OUT%" 2>&1

echo.>>"%OUT%"
echo --- 8. installer log --->>"%OUT%"
if exist "nanoamp_install.log" goto loghere
if exist "%LOCALAPPDATA%\nanoamp_install.log" goto loglocal
echo NO LOG FILE FOUND.>>"%OUT%"
echo That means the click never reached the installers first logged step.>>"%OUT%"
goto logdone
:loghere
echo log found next to install.exe>>"%OUT%"
powershell -NoProfile -Command "Get-Content -LiteralPath 'nanoamp_install.log' -Tail 40">>"%OUT%" 2>&1
goto logdone
:loglocal
echo log found in LOCALAPPDATA>>"%OUT%"
powershell -NoProfile -Command "Get-Content -LiteralPath '%LOCALAPPDATA%\nanoamp_install.log' -Tail 40">>"%OUT%" 2>&1
:logdone

echo.>>"%OUT%"
echo --- 9. recent application errors, last 10 --->>"%OUT%"
wevtutil qe Application /c:10 /rd:true /q:*[System[Level=2]] /f:text>>"%OUT%" 2>&1

echo.>>"%OUT%"
echo =============== end ===============>>"%OUT%"

echo.
echo Done. A file named %OUT% was created in this folder.
echo Please send that file back.
echo.
type "%OUT%"
echo.
pause
exit /b 0

:check
REM %1 = path, %2 = label. Avoids nested parentheses, which break on paths
REM such as "C:\Program Files (x86)\R".
if exist %1 echo OK      %~2>>"%OUT%"
if not exist %1 echo MISSING %~2>>"%OUT%"
exit /b 0
