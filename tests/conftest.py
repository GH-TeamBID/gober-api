"""
Pytest configuration file for all tests.
This file is automatically loaded by pytest.
"""

import os
import sys
import pytest
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Load test environment variables
def load_test_env():
    """Load environment variables from .env.test file"""
    # Get the project root directory
    root_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    # Path to .env.test file
    env_test_path = os.path.join(root_dir, '.env.test')
    
    # Load environment variables from .env.test
    if os.path.exists(env_test_path):
        print(f"Loading test environment from: {env_test_path}")
        load_dotenv(env_test_path, override=True)
        return True
    else:
        print(f"Warning: Test environment file not found: {env_test_path}")
        return False

# Load test environment variables
load_test_env()

def pytest_addoption(parser):
    """Add custom command-line options to pytest"""
    parser.addoption(
        "--run-real-db", 
        action="store_true", 
        default=False, 
        help="Run tests that connect to the real database"
    )

@pytest.fixture(scope="session")
def run_real_db(request):
    """Fixture to check if real DB tests should run"""
    return request.config.getoption("--run-real-db") 