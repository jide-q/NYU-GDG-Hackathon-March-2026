#!/bin/bash
# deploy.sh — One-command deployment to Google Cloud Run
# Usage: ./deploy.sh YOUR_PROJECT_ID YOUR_API_KEY

set -e

PROJECT_ID=${1:?"Usage: ./deploy.sh PROJECT_ID API_KEY"}
API_KEY=${2:?"Usage: ./deploy.sh PROJECT_ID API_KEY"}
REGION="us-central1"
SERVICE="deliver-assist"

echo "🚀 Deploying DeliverAssist to Cloud Run..."
echo "   Project: $PROJECT_ID"
echo "   Region:  $REGION"
echo "   Service: $SERVICE"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "📡 Enabling APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    aiplatform.googleapis.com \
    --quiet

# Deploy from source (Cloud Build handles Docker)
echo "🏗️  Building and deploying..."
gcloud run deploy $SERVICE \
    --source . \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_API_KEY=$API_KEY" \
    --memory=512Mi \
    --timeout=300 \
    --session-affinity \
    --min-instances=0 \
    --max-instances=3

# Get the URL
URL=$(gcloud run services describe $SERVICE --region $REGION --format 'value(status.url)')

echo ""
echo "✅ Deployed successfully!"
echo "🌐 URL: $URL"
echo ""
echo "📹 Take a screenshot of this terminal output as proof of GCP deployment."
