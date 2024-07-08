#!/bin/bash

# Ensuring script is run as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

# Update system
echo "Updating system packages..."
apt-get update

# Install necessary tools
echo "Installing necessary tools..."
apt-get install -y apt-transport-https ca-certificates curl software-properties-common

# Check for Python 3.11 and install if missing
if ! command -v python3.11 &> /dev/null
then
    echo "Python 3.11 not found, adding repository and installing Python 3.11..."
    add-apt-repository ppa:deadsnakes/ppa -y
    apt-get update
    apt-get install -y python3.11 python3.11-venv python3.11-dev
else
    echo "Python 3.11 is already installed."
fi

# Check for pip and install if missing
if ! command -v pip &> /dev/null
then
    echo "pip not found, installing..."
    apt-get install -y python3-pip
else
    echo "pip is already installed."
fi

# Install Pipenv using pip
echo "Installing/updating Pipenv..."
pip install --upgrade pipenv

# Check for Docker and install if missing
if ! command -v docker &> /dev/null
then
    echo "Docker not found, installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
else
    echo "Docker is already installed."
fi

# Add current user to the docker group to run docker as non-root
usermod -aG docker $USER

# Check for Docker Compose and install if missing
if ! command -v docker-compose &> /dev/null
then
    echo "Docker Compose not found, installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo "Docker Compose is already installed."
fi

echo "Installation and verification complete. Please log out and back in for group changes to take effect, if Docker was installed."
