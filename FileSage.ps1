# FileSage Launcher (PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Host.UI.RawUI.WindowTitle = "FileSage Launcher"

function Find-Python {
    $candidates = @(
        @{ Cmd = "py"; Args = @("-3") },
        @{ Cmd = "python"; Args = @() },
        @{ Cmd = "python3"; Args = @() }
    )
    foreach ($c in $candidates) {
        $cmd = Get-Command $c.Cmd -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            & $c.Cmd @($c.Args) -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return @{ Exe = $c.Cmd; Args = $c.Args }
            }
        } catch { }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "[ERROR] Se necesita Python 3.11+" -ForegroundColor Red
    Write-Host "Instala desde https://www.python.org/downloads/"
    exit 1
}

if ($args.Count -eq 0) {
    $argList = @($py.Args + @("scripts\launcher_gui.py"))
} else {
    $argList = @($py.Args + @("scripts\launcher_menu.py") + $args)
}
& $py.Exe @argList
exit $LASTEXITCODE
