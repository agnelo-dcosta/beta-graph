#!/bin/bash

# GCP Setup Script - Personal Account
# Run this to configure gcloud CLI for your personal GCP account

set -e

echo "=== GCP Setup for Personal Account ==="

# 1. Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "gcloud CLI not found. Install with: brew install --cask google-cloud-sdk"
    exit 1
fi

# 2. Initialize gcloud (opens browser for sign-in)
echo ""
echo "Step 1: Sign in to your personal Google account..."
gcloud init

# 3. Set up Application Default Credentials (for local SDK/tools)
echo ""
echo "Step 2: Set up Application Default Credentials..."
gcloud auth application-default login

# 4. Verify configuration
echo ""
echo "Step 3: Verifying configuration..."
echo "--- Active account ---"
gcloud auth list
echo ""
echo "--- Current config ---"
gcloud config list

echo ""
echo "=== Setup complete ==="
echo "Optional: Create a project-specific config with:"
echo "  gcloud config configurations create beta-graph-personal"
echo "  gcloud config set account YOUR_EMAIL@gmail.com"
echo "  gcloud config set project YOUR_GCP_PROJECT_ID"
echo "  gcloud config configurations activate beta-graph-personal"
