import os
import sys

# Ensure current directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

# Expose 'app' for Vercel / WSGI servers
app = create_app()

if __name__ == "__main__":
    app.run()
