param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Example,

    [switch]$Run
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$ExampleDir = Join-Path $RepoRoot $Example

function Show-Usage {
    Write-Host "Usage: .\setup.ps1 <example-folder> [-Run]"
    Write-Host ""
    Write-Host "Sets up a Fetch.ai Innovation Lab example for local development."
    Write-Host ""
    Write-Host "Arguments:"
    Write-Host "  <example-folder>   Name of the example folder (e.g. fetch-hackathon-quickstarter)"
    Write-Host "  -Run               Automatically run the agent after setup (optional)"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\setup.ps1 fetch-hackathon-quickstarter"
    Write-Host "  .\setup.ps1 gemini-quickstart/01-basic-gemini-agent -Run"
    Write-Host "  .\setup.ps1 fet-example"
}

function Get-CompatiblePython {
    $candidates = @(
        [pscustomobject]@{ Command = "python"; Arguments = @() },
        [pscustomobject]@{ Command = "py"; Arguments = @("-3") }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) {
            continue
        }

        $versionOutput = & $candidate.Command @($candidate.Arguments + @("--version")) 2>&1
        if ($LASTEXITCODE -ne 0) {
            continue
        }

        $versionMatch = [regex]::Match(($versionOutput | Out-String), "(?<version>\d+\.\d+(\.\d+)?)")
        if (-not $versionMatch.Success) {
            continue
        }

        $version = [version]$versionMatch.Groups["version"].Value
        if ($version -ge [version]"3.10") {
            return [pscustomobject]@{
                Command = $candidate.Command
                Arguments = $candidate.Arguments
                Version = $versionOutput
            }
        }
    }

    return $null
}

function Invoke-PythonCommand {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Python,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Python.Command @($Python.Arguments + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

if (-not (Test-Path -Path $ExampleDir -PathType Container)) {
    Write-Host "Error: Example folder '$Example' not found."
    Write-Host ""
    Write-Host "Available examples:"
    Get-ChildItem -Path $RepoRoot -Directory |
        Where-Object {
            -not $_.Name.StartsWith(".") -and
            $_.Name -notin @("docs", ".github", "tests") -and
            (
                (Test-Path (Join-Path $_.FullName "requirements.txt")) -or
                (Test-Path (Join-Path $_.FullName "agent.py")) -or
                (Test-Path (Join-Path $_.FullName "main.py"))
            )
        } |
        ForEach-Object { Write-Host "  $($_.Name)" }
    Write-Host ""
    Show-Usage
    exit 1
}

Write-Host "=== Fetch.ai Innovation Lab Setup ==="
Write-Host "Example: $Example"
Write-Host ""

Set-Location $ExampleDir

$Python = Get-CompatiblePython
if ($null -eq $Python) {
    Write-Host "Error: Python 3.10+ is required but not found."
    Write-Host "Install Python from https://www.python.org/downloads/"
    exit 1
}

Write-Host "[1/4] Using $($Python.Version)"

if (-not (Test-Path -Path ".venv" -PathType Container)) {
    Write-Host "[2/4] Creating virtual environment..."
    Invoke-PythonCommand -Python $Python -Arguments @("-m", "venv", ".venv")
} else {
    Write-Host "[2/4] Virtual environment already exists."
}

$VenvPython = Join-Path $ExampleDir ".venv\Scripts\python.exe"
if (-not (Test-Path -Path $VenvPython -PathType Leaf)) {
    Write-Host "Error: Expected virtual environment Python not found at $VenvPython"
    exit 1
}

if (Test-Path -Path "requirements.txt" -PathType Leaf) {
    Write-Host "[3/4] Installing dependencies..."
    & $VenvPython -m pip install -q --upgrade pip
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $VenvPython -m pip install -q -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "[3/4] No requirements.txt found - skipping dependency install."
}

if ((Test-Path -Path ".env.example" -PathType Leaf) -and -not (Test-Path -Path ".env" -PathType Leaf)) {
    Copy-Item -Path ".env.example" -Destination ".env"
    Write-Host "[4/4] Created .env from .env.example - edit it with your API keys."
} elseif (Test-Path -Path ".env" -PathType Leaf) {
    Write-Host "[4/4] .env already exists - skipping."
} else {
    Write-Host "[4/4] No .env.example found - no environment variables needed."
}

$EntryFile = $null
foreach ($candidate in @("agent.py", "main.py", "workflow.py", "app.py")) {
    if (Test-Path -Path $candidate -PathType Leaf) {
        $EntryFile = $candidate
        break
    }
}

Write-Host ""
Write-Host "=== Setup Complete ==="
Write-Host ""
Write-Host "To activate the environment:"
Write-Host "  cd $Example; .\.venv\Scripts\Activate.ps1"
Write-Host ""

if ($null -ne $EntryFile) {
    if ($Run) {
        Write-Host "Starting agent..."
        & $VenvPython $EntryFile
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } else {
        Write-Host "To run the agent:"
        Write-Host "  python $EntryFile"
    }
} else {
    Write-Host "Check the example's README.md for run instructions."
}
