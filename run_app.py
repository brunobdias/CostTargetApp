# run_app.py
"""
Production entry point for running Flask behind IIS + ARR.
Use WAITRESS for stability on Windows.
"""

from waitress import serve
from app import app    # Import your existing Flask "app" object

if __name__ == "__main__":
    print("Starting Waitress server on http://localhost:5001 ...")
    serve(
        app,
        host="127.0.0.1",
        port=5001,
        threads=8
    )
