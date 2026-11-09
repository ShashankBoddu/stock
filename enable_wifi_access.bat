@echo off
setlocal EnableDelayedExpansion
title Stockroom - Wi-Fi Network Access Setup
color 0b

echo ====================================================================
echo             STOCKROOM - SAME WI-FI ACCESS SETUP
echo ====================================================================
echo.

:: Check for administrative rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Administrator rights required to update Windows Firewall.
    echo Prompting for administrator permissions...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo [1/4] Removing old or blocking firewall rules for Python...
netsh advfirewall firewall delete rule name="Python" >nul 2>&1
netsh advfirewall firewall delete rule name="Stockroom Web Server (Port 8080)" >nul 2>&1
netsh advfirewall firewall delete rule name="Stockroom Python (python.exe)" >nul 2>&1

echo [2/4] Adding Inbound Firewall Rule for Port 8080 (TCP)...
netsh advfirewall firewall add rule name="Stockroom Web Server (Port 8080)" dir=in action=allow protocol=TCP localport=8080 profile=any >nul
if %errorlevel% equ 0 (
    echo       * Port 8080 allowed successfully.
) else (
    echo       * Warning: Could not add port 8080 rule.
)

echo [3/4] Adding Inbound Firewall Rule for Python executable...
for /f "delims=" %%I in ('where python 2^>nul') do (
    netsh advfirewall firewall add rule name="Stockroom Python (%%~nxI)" dir=in action=allow program="%%I" profile=any >nul 2>&1
    echo       * Allowed Python binary: %%I
)

echo [4/4] Setting Wi-Fi network profile to Private (allowing local network discovery)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$wifi = Get-NetConnectionProfile | Where-Object { $_.IPv4Connectivity -eq 'Internet' -or $_.InterfaceAlias -match 'Wi-Fi|Wireless|WLAN' }; if ($wifi) { $wifi | Set-NetConnectionProfile -NetworkCategory Private; Write-Host '      * Set network profile' $wifi.Name 'to Private.' } else { Write-Host '      * No active Wi-Fi profile found.' }"

echo.
echo ====================================================================
echo                     SETUP COMPLETE!
echo ====================================================================
echo.
echo Your Laptop's Wi-Fi URL:
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ips = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' }).IPAddress; foreach ($ip in $ips) { Write-Host \"  >> http://${ip}:8080/\" -ForegroundColor Green }"
echo.
echo Anyone connected to this same Wi-Fi can now open that URL in their
echo mobile phone or computer browser!
echo.
echo Keep 'run_stockroom.bat' running on this laptop while others use it.
echo ====================================================================
echo.
pause

