@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
call .venv\Scripts\activate.bat

:: Point to the main physics repository
set PYTHONPATH=C:\Users\sruji\Projects\masters_thesis;C:\Users\sruji\Projects\masters_thesis\self_energy;C:\Users\sruji\Projects\masters_thesis\susceptibility;%PYTHONPATH%

python pyside6_studio\main.py
pause
