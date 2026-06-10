@echo off
REM Loads the Distributed SMB Docker images from the bundled tar.gz files.
REM Run this once per machine before starting the game.

cd /d "%~dp0"

echo ==^> Loading distributed-smb-lobby
docker load < smb-lobby.tar.gz
if errorlevel 1 goto :error

echo ==^> Loading distributed-smb-gameevents
docker load < smb-gameevents.tar.gz
if errorlevel 1 goto :error

echo ==^> Done. Images available:
docker images | findstr distributed-smb

goto :eof

:error
echo Setup failed.
exit /b 1
