#!/usr/bin/env bash
# T064: Enable required Google Cloud APIs before deployment
#
# Usage: ./scripts/enable_gcloud_apis.sh [PROJECT_ID]

set -euo pipefail

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: No project ID provided and none configured in gcloud."
    echo "Usage: $0 <project-id>"
    exit 1
fi

echo "Enabling required APIs for project: $PROJECT_ID"

APIS=(
    "run.googleapis.com"
    "logging.googleapis.com"
    "secretmanager.googleapis.com"
    "cloudbuild.googleapis.com"
    "containerregistry.googleapis.com"
)

for api in "${APIS[@]}"; do
    echo "  Enabling $api..."
    gcloud services enable "$api" --project="$PROJECT_ID"
done

echo "All required APIs enabled."
