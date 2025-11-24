# ============================================================
#  CostTarget App - Auto Update Script
# ============================================================

$AppPath   = "C:\Python\CostTargetApp"
$VenvPath  = "$AppPath\venv\Scripts\activate"
$RunScript = "$AppPath\run_app.py"
$LogFile   = "$AppPath\update_log.txt"

Function Log($msg, $color="White") {
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host "[$timestamp] $msg" -ForegroundColor $color
    Add-Content -Path $LogFile -Value "[$timestamp] $msg"
}

# ============================================================
# Start Logging
# ============================================================
Log "=== CostTargetApp Update Started ===" "Yellow"

# ============================================================
# Kill Running Instances
# ============================================================
Log "Stopping running CostTargetApp python instances..." "Yellow"

Get-WmiObject Win32_Process |
Where-Object {
    $_.Name -eq "python.exe" -and
    $_.CommandLine -like "*run_app.py*"
} |
ForEach-Object {
    $pid = $_.ProcessId
    Log "Attempting to kill PID $pid"

    try {
        Stop-Process -Id $pid -Force -ErrorAction Stop
        Log "Killed PID $pid" "Green"
    }
    catch {
        Log "PID $pid already exited (ignored)" "DarkYellow"
    }
}

# ============================================================
# Reset Git to clean state
# ============================================================
Log "Cleaning Git repo..." "Yellow"

Set-Location $AppPath

git reset --hard | Out-Null
git clean -fd | Out-Null

$result = git pull origin main 2>&1
Log "Git pull result: $result" "Gray"

# ============================================================
# Virtual environment activation
# ============================================================
Log "Activating virtual environment..." "Yellow"

try {
    & $VenvPath
    Log "Virtual environment activated." "Green"
}
catch {
    Log "ERROR: Could not activate venv!" "Red"
    exit 1
}

# ============================================================
# Install dependencies
# ============================================================
Log "Installing dependencies (pip install)..." "Yellow"

pip install -r requirements.txt --quiet
Log "Dependencies updated." "Green"

# ============================================================
# Start application in background
# ============================================================
Log "Starting CostTargetApp service..." "Yellow"

Start-Process "python.exe" -ArgumentList $RunScript -WorkingDirectory $AppPath

Start-Sleep -Seconds 2

# Verify app launched
$running = Get-Process python | Where-Object { $_.StartInfo.Arguments -like "*run_app.py*" }

if ($running) {
    Log "CostTarget App successfully started (PID $($running.Id))." "Green"
} else {
    Log "ERROR: App did not start!" "Red"
}

Log "=== Update Completed ===" "Cyan"
