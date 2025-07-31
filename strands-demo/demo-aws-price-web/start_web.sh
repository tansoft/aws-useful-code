#!/bin/bash

# Make sure we're in the correct directory
cd "$(dirname "$0")"

# Check if Python is installed
if ! command -v python3 &> /dev/null
then
    echo "Python 3 is required but not installed. Please install Python 3 to continue."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null
then
    echo "pip3 is required but not installed. Please install pip3 to continue."
    exit 1
fi

# Check if virtual environment exists, if not create one
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install or upgrade dependencies
echo "Installing/upgrading dependencies..."
pip install --upgrade -r requirements.txt

# Run the application
echo "Starting AWS Price Web Assistant..."
echo "Access the application at http://localhost:8000"
python demo_aws_price_web.py

# Deactivate virtual environment when done
deactivate