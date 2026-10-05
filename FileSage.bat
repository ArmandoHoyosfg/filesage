@echo off
setlocal EnableExtensions EnableDelayedExpansion
title FileSage Launcher
color 0B
cd /d "%~dp0"

echo.
echo  ================================================================
echo                    FileSage  -  Iniciando launcher
echo  ================================================================
echo.

REM --- Preferir py -3 (launcher oficial Windows), luego python ---
set "PYEXE="
where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
  if !ERRORLEVEL!==0 set "PYEXE=py -3"
)
if not defined PYEXE (
  where python >nul 2>&1
  if %ERRORLEVEL%==0 (
    python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
    if !ERRORLEVEL!==0 set "PYEXE=python"
  )
)
if not defined PYEXE (
  where python3 >nul 2>&1
  if %ERRORLEVEL%==0 (
    python3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
    if !ERRORLEVEL!==0 set "PYEXE=python3"
  )
)

if not defined PYEXE (
  color 0C
  echo  [ERROR] No se encontro Python 3.11 o superior.
  echo.
  echo  Instala desde https://www.python.org/downloads/
  echo  Marca "Add python.exe to PATH" durante la instalacion.
  echo  En Windows evita el acceso directo falso de Microsoft Store.
  echo.
  pause
  exit /b 1
)

echo  Interprete: %PYEXE%
echo.

REM Atajos: FileSage.bat web ^| browser ^| gui ^| check ^| install ^| integrity
if /I "%~1"=="web" goto RUN_WEB
if /I "%~1"=="browser" goto RUN_BROWSER
if /I "%~1"=="gui" goto RUN_GUI
if /I "%~1"=="check" goto RUN_CHECK
if /I "%~1"=="install" goto RUN_INSTALL
if /I "%~1"=="integrity" goto RUN_INTEGRITY

REM Launcher grafico (Tkinter). Si falla, menu de consola.
echo  Abriendo launcher grafico...
%PYEXE% scripts\launcher_gui.py
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" (
  echo.
  echo  GUI no disponible — abriendo menu de consola...
  %PYEXE% scripts\launcher_menu.py
  set "EC=!ERRORLEVEL!"
)
if not "!EC!"=="0" (
  color 0C
  echo.
  echo  El launcher termino con codigo !EC!
  pause
)
exit /b !EC!

:RUN_WEB
%PYEXE% scripts\launcher_menu.py --web
exit /b %ERRORLEVEL%

:RUN_BROWSER
%PYEXE% scripts\launcher_menu.py --browser
exit /b %ERRORLEVEL%

:RUN_GUI
%PYEXE% scripts\launcher_menu.py --gui
exit /b %ERRORLEVEL%

:RUN_CHECK
%PYEXE% scripts\launcher_menu.py --check
pause
exit /b %ERRORLEVEL%

:RUN_INSTALL
%PYEXE% scripts\launcher_menu.py --install
pause
exit /b %ERRORLEVEL%

:RUN_INTEGRITY
%PYEXE% scripts\launcher_menu.py --integrity
pause
exit /b %ERRORLEVEL%
