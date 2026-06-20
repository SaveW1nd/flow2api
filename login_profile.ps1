# Log a Google account into a Chrome Profile (headed browser).
# After login completes, close the browser window.
# Usage:  .\login_profile.ps1 acc1
param(
    [Parameter(Mandatory = $true)][string]$ProfileName
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "venv not found, run .\setup_workers.ps1 first" }

$profilesDir = Join-Path $root "flow_profiles"
New-Item -ItemType Directory -Force -Path $profilesDir | Out-Null
$profilePath = Join-Path $profilesDir $ProfileName

$code = @"
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(r'$profilePath', headless=False,
            args=['--disable-blink-features=AutomationControlled'])
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto('https://labs.google/fx/tools/flow')
        print('>>> Please complete Google login and open Flow, then close the browser window...')
        try:
            await page.wait_for_event('close', timeout=600000)
        except Exception:
            pass
        await ctx.close()
asyncio.run(main())
"@
& $py -c $code
Write-Host "[OK] Profile '$ProfileName' login flow finished." -ForegroundColor Green
