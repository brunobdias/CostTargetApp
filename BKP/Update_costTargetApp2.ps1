Write-Host "=== CostTarget App Update ==="

cd C:\Python\CostTargetApp\

Write-Host "Stopping old CostTargetApp instance..."

Get-WmiObject Win32_Process `
| Where-Object {
    $_.Name -eq "python.exe" -and
    $_.CommandLine -like "*CostTargetApp*"
} `
| ForEach-Object {
    Write-Host "Killing PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force
}

Write-Host "Cleaning Git repo..."
git reset --hard
git clean -fd
git pull origin main   # or master

Write-Host "Activating virtual environment..."
.\venv\Scripts\activate

Write-Host "Installing dependencies..."
pip install -r requirements.txt

Write-Host "Cleaning Python cache..."
Get-ChildItem -Recurse -Include *.pyc | Remove-Item -Force -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue

Write-Host "Starting application..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Python\CostTargetApp; .\venv\Scripts\activate; python run_app.py"

Write-Host "=== Update Complete ==="
