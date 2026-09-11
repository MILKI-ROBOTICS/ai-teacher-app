$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\mobile"
if (-not (Test-Path node_modules)) { npm install }
if (-not (Test-Path android)) { npx cap add android }
npx cap sync android
npx cap open android
