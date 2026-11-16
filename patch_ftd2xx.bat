@echo off
chcp 65001 >nul
rem Перетащите папку Galletto на этот файл
rem или запустите: patch_ftd2xx.bat "C:\путь\к\GALLETTO_1260" [--check | --restore]
if "%~1"=="" (
  echo Использование: patch_ftd2xx.bat "C:\путь\к\GALLETTO_1260" [--check ^| --restore]
  pause
  exit /b 1
)
python "%~dp0patch_ftd2xx.py" "%~1" %2
pause
