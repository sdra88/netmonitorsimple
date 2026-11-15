@echo off
rem Start NetSpeed Monitor without a console window (portable, no Python needed).
rem Keep this .bat next to NetSpeedMonitor.exe. Change the path only if you move that exe.
start "" "%~dp0NetSpeedMonitor.exe"
