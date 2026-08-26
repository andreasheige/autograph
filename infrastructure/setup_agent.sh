#!/bin/bash

# Autograph Setup Script
# This script automates the initial configuration of the Autograph Agent.

set -e

echo "🚀 Starting Autograph Setup..."

# 1. Handle .env file
if [ ! -f ".env" ]; then
    echo "📝 .env file not found. Creating from template..."
    cp .env.example .env
    echo "✅ Created .env. Please edit it with your actual paths."
else
    echo "✅ .env file already exists. Skipping."
fi

# 2. Ensure local directories exist
echo "📂 Ensuring local directories exist..."
mkdir -p ~/.autograph/logs
mkdir -p ~/.autograph/vault/daily_notes
mkdir -p ~/.autograph/vault/projects

# 3. Check for dependencies
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed."
    exit 1
fi

echo "✨ Setup Complete! You can now configure your paths in .env and start running the agents."
