#!/usr/bin/env python3
"""
Convenience script to run the Flask web application
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.web.app import app
from src.web.models import Base, engine

if __name__ == '__main__':
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5001)

