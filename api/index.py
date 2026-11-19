import os
import sys

# Ensure project root is in Python module search path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app

# Vercel serverless entrypoint: exposes the Flask application instance 'app'
app = create_app()

if __name__ == "__main__":
    app.run()
