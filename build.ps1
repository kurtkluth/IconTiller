$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $buildPython = Join-Path $PSScriptRoot '.venv312\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $buildPython)) { throw 'Create the Python 3.12 environment described in README.md first.' }
    & $buildPython -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
    & $buildPython -m unittest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & $buildPython -m PyInstaller --noconfirm IconTiller.spec
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
    $report = Join-Path $PSScriptRoot 'build\packaged-smoke.json'
    if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report }
    $binary = Join-Path $PSScriptRoot 'dist\IconTiller\IconTiller.exe'
    $check = Start-Process -FilePath $binary -ArgumentList @('--self-test', ('"' + $report + '"')) -WindowStyle Hidden -PassThru
    if (-not $check.WaitForExit(60000)) { $check.Kill(); throw 'Packaged smoke check timed out.' }
    if ($check.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw 'Packaged smoke check failed.' }
    if (-not (Get-Content -LiteralPath $report -Raw | ConvertFrom-Json).passed) { throw 'Packaged smoke check reported failure.' }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'DISTRIBUTION_README.txt') -Destination (Join-Path $PSScriptRoot 'dist\IconTiller\README.txt')
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'LICENSE') -Destination (Join-Path $PSScriptRoot 'dist\IconTiller\LICENSE.txt')
    Write-Host "Built and checked: $binary"
} finally { Pop-Location }
