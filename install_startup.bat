@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
echo Set o = CreateObject("WScript.Shell") > "%TEMP%\kbu_keeper.vbs"
echo o.Run "pythonw ""%~dp0kbu_wifi_keeper.py""", 0, False >> "%TEMP%\kbu_keeper.vbs"
copy /Y "%TEMP%\kbu_keeper.vbs" "%STARTUP%\KBUWifiKeeper.vbs" >nul
start "" pythonw "%~dp0kbu_wifi_keeper.py"
echo Installed. Green tray icon = running. Right-click for ON/OFF.
pause
