Write-Host "Starting Local WhatsApp Server..."
Write-Host "Please wait a moment. A QR Code will appear below."
Write-Host "Scan it with your WhatsApp app (Linked Devices) to connect!"
$env:PUPPETEER_CACHE_DIR = Join-Path $PSScriptRoot ".puppeteer_cache"
node server.js
