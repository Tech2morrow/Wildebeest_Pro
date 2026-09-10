[CmdletBinding()]
param(
    [string]$PythonExecutable = "python",
    [switch]$StrictTools
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

if (-not (Get-Command $PythonExecutable -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Pass -PythonExecutable with a Python 3.11+ path."
}
& $PythonExecutable -c "import yaml"
if ($LASTEXITCODE -ne 0) {
    throw "PyYAML is required. Run: $PythonExecutable -m pip install -r requirements-ci.txt"
}
& $PythonExecutable -m unittest discover -s tools/tests -v
if ($LASTEXITCODE -ne 0) { throw "Protocol tests failed." }

if (Get-Command node -ErrorAction SilentlyContinue) {
    & node --test dashboard/test/*.test.mjs
    if ($LASTEXITCODE -ne 0) { throw "Dashboard tests failed." }
} elseif ($StrictTools) {
    throw "Node.js is required in strict mode."
} else {
    Write-Warning "Node.js is unavailable; dashboard tests skipped."
}

& $PythonExecutable tools/robot_doctor.py
if ($LASTEXITCODE -ne 0) { throw "Repository preflight failed." }

& $PythonExecutable ros1_ws/tools/run_checks.py
if ($LASTEXITCODE -ne 0) { throw "ROS 1 static checks failed." }

& $PythonExecutable ros2_ws/scripts/validate_workspace.py
if ($LASTEXITCODE -ne 0) { throw "ROS 2 static checks failed." }
