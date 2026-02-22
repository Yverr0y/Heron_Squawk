@echo off
cd /d %~dp0

REM Set your Heltec device COM port below
set PORT=COM15

echo Uploading files to Heltec on %PORT%...
for %%f in (*.py) do (
    echo Copying %%f...
    mpremote connect %PORT% cp --force "%%f" :
)
echo Done! Resetting device...
mpremote connect %PORT% reset
pause
