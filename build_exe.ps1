$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pythonArgsPrefix = @($venvPython)
}
else {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        $pythonArgsPrefix = @("py", "-3")
    }
    else {
        throw "Could not find a Python interpreter. Create .venv or install Python/py launcher."
    }
}

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    if ($pythonArgsPrefix[0] -eq "py") {
        & py -3 @Args
    }
    else {
        & $pythonArgsPrefix[0] @Args
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
}

Invoke-Python -Args @("-m", "pip", "install", "--upgrade", "pip", "pyinstaller")
Invoke-Python -Args @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "ScanningMagnetometry",
    "--add-data", "configs;configs",
    "main.py"
)

$exePath = Join-Path $scriptDir "dist\ScanningMagnetometry.exe"
if (Test-Path $exePath) {
    Write-Host "Build completed: $exePath"
}
else {
    throw "Build finished but executable was not found at $exePath"
}
