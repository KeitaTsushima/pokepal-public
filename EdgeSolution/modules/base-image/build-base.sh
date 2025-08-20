#!/bin/bash
# PokePal base image build script

echo "🏗️ Building PokePal base image..."
echo "⏱️ This only needs to be run once (takes 10-15 minutes)"

ACR_NAME="YOUR_ACR_NAME"
BASE_IMAGE="${ACR_NAME}.azurecr.io/YOUR_BASE_IMAGE_NAME:latest-arm64v8"

echo "📝 Logging into ACR..."
az acr login --name $ACR_NAME

echo "🔨 Building base image..."
docker buildx build \
    --platform linux/arm64 \
    -t $BASE_IMAGE \
    -f Dockerfile \
    . \
    --push

if [ $? -eq 0 ]; then
    echo "✅ Base image build completed successfully!"
    echo "📦 Image: $BASE_IMAGE"
    echo ""
    echo "Next steps:"
    echo "1. Update each module's Dockerfile to use the base image"
    echo "2. FROM $BASE_IMAGE"
else
    echo "❌ Build failed"
    exit 1
fi