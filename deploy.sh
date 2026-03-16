#!/usr/bin/env bash
# Willow — Google Cloud Run deployment script
# Usage: ./deploy.sh [PROJECT_ID]
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - GEMINI_API_KEY set in environment or .env file
#
# This script enables required GCP services and deploys Willow to Cloud Run.

set -euo pipefail

PROJECT_ID="${1:-willow-agent}"
REGION="us-central1"
SERVICE_NAME="willow"

# Load GEMINI_API_KEY from .env if not already set
if [ -z "${GEMINI_API_KEY:-}" ] && [ -f .env ]; then
  GEMINI_API_KEY=$(grep -E '^GEMINI_API_KEY=' .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
fi

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "Error: GEMINI_API_KEY not set. Export it or add it to .env"
  exit 1
fi

echo "Deploying Willow to Cloud Run..."
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo "  Service:  $SERVICE_NAME"
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# Enable required services
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

# Deploy
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --timeout 3600 \
  --set-env-vars "GEMINI_API_KEY=$GEMINI_API_KEY" \
  --set-env-vars "GEMINI_MODEL_ID=gemini-2.5-flash-native-audio-preview-12-2025" \
  --set-env-vars "SKIP_HASH_VALIDATION=true" \
  --set-env-vars "LOG_LEVEL=INFO"

# Print live URL
echo ""
echo "Deployed! Live URL:"
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)"
