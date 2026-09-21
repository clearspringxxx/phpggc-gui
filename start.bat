@echo off
cd /d "%~dp0"
start "" "%~dp0runtime\python\pythonw.exe" "%~dp0app\main.py"
