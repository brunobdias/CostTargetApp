cd C:\Python\CostTargetApp\

# Fetch latest code
git reset --hard
git clean -fd
git pull origin main   # or master, depending on your branch

# Restart the Waitress service
# Restart-Service -Name CostTargetAppService

.\venv\Scripts\activate
python run_app.py