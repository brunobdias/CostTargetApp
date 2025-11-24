# ============================================================
#  CostTarget App - Auto Update Script (Service Version)
# ============================================================

$ServiceName = "CostTargetApp"
$AppPath     = "C:\Python\CostTargetApp"
$VenvPath    = "$AppPath\venv\Scripts\activate"
$LogFile     = "$AppPath\update_log.txt"

Function Log($msg, $color="White") {
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host "[$timestamp] $msg" -ForegroundColor $color
    Add-Content -Path $LogFile -Value "[$timestamp] $msg"
}

Log ""
Log "=== CostTargetApp Update Started ===" "Yellow"

# ============================================================
# Stop Windows Service
# ============================================================
Log "Stopping $ServiceName service..." "Yellow"

try {
    Stop-Service -Name $ServiceName -Force -ErrorAction Stop
    Log "Service stopped successfully." "Green"
}
catch {
    Log "Service was not running or failed to stop (ignored)." "DarkYellow"
}

Start-Sleep -Seconds 2


# ============================================================
# Git Reset + Pull Latest Files
# ============================================================
Log "Cleaning Git repository..." "Yellow"

Set-Location $AppPath

git reset --hard | Out-Null
git clean -fd | Out-Null

$result = git pull origin main 2>&1
Log "Git pull result: $result" "Gray"


# ============================================================
# Activate Virtual Environment
# ============================================================
Log "Activating virtual environment..." "Yellow"

try {
    & $VenvPath
    Log "Venv activated." "Green"
}
catch {
    Log "ERROR: Could not activate venv!" "Red"
    exit 1
}


# ============================================================
# Install dependencies
# ============================================================
Log "Installing dependencies..." "Yellow"

pip install -r requirements.txt --quiet
Log "Dependencies updated." "Green"


# ============================================================
# Start Windows Service Again
# ============================================================
Log "Starting $ServiceName service..." "Yellow"

try {
    Start-Service -Name $ServiceName -ErrorAction Stop
    Log "Service started successfully." "Green"
}
catch {
    Log "ERROR: Service failed to start!" "Red"
    exit 1
}

# Final Confirmation
$svc = Get-Service -Name $ServiceName
if ($svc.Status -eq "Running") {
    Log "Service is RUNNING." "Green"
} else {
    Log "Service is NOT running — check logs!" "Red"
}

Log "=== Update Completed ===" "Cyan"
