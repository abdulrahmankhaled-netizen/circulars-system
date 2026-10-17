@echo off
chcp 65001 >nul

REM تشغيل النسخة الصامتة
start "" wscript.exe "%~dp0start_silent.vbs"