"""
Secure Event Management System - Application Entrypoint
Run locally with:
    python run.py
"""
import os
import sys
from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    print("=" * 70)
    print(" Secure Event Management System (EventSecure)")
    print("=" * 70)
    print(f" * Database Type:    {Config.DB_TYPE.upper()}")
    print(f" * Database URI:     {Config.SQLALCHEMY_DATABASE_URI}")
    print(f" * Running on:       http://{Config.HOST}:{Config.PORT}")
    print(f" * Default Admin:    admin@example.com  (Password: Admin@12345)")
    print(f" * Default User:     user@example.com   (Password: User@12345)")
    print("=" * 70)

    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
