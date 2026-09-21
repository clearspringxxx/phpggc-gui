@echo off
cd /d "%~dp0"
echo PHPGGC GUI debug mode. Close the window to exit.
"%~dp0runtime\python\python.exe" "%~dp0app\main.py"
pause
