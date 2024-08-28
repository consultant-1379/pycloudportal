#!/bin/bash

# Activate the virtual environment if applicable
source /opt/venvpycloud/bin/activate

# Install pylint if not already installed
pip install pylint

# DEV Setting: Change this to your working DIRECTORY
# Set the base directory of your Django project
BASE_DIR="/opt/pycloudportal"

# Run pylint to check for syntax errors and enforce coding standards
pylint --disable=R0903,E1101,C0115 pyvcloud_project --ignore=migrations