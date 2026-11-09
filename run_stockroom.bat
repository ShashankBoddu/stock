@echo off
setlocal
cd /d "%~dp0"
set "STOCK_HOST=0.0.0.0"
set "STOCK_OPEN_BROWSER=1"

echo ====================================================================
echo                   STARTING STOCKROOM SERVER
echo ====================================================================
echo.
echo Local address (for this laptop):
echo   http://127.0.0.1:8080/
echo.
echo Wi-Fi address (for phones and other laptops on the same Wi-Fi):
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ips = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' }).IPAddress; foreach ($ip in $ips) { Write-Host \"  http://${ip}:8080/\" -ForegroundColor Green }"
echo.
echo NOTE: If other devices on Wi-Fi cannot open the link:
echo   Run 'enable_wifi_access.bat' once to configure Windows Firewall.
echo.
echo Keep this window open while Stockroom is being used.
echo Press Ctrl+C to stop the server.
echo ====================================================================
echo.

python server.py
if errorlevel 1 (
  echo.
  echo Stockroom could not start. Check that Python is installed and port 8080 is free.
)
pause
