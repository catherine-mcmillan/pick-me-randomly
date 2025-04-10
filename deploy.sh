#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define variables
APP_NAME="pick-me-randomly"  # Replace with your Fly.io app name
IMAGE_NAME="pick-me-randomly"  # Replace with your Docker image name

# Build the Docker image
echo "Building Docker image..."
docker build -t $IMAGE_NAME .

# Tag the image for Fly.io
echo "Tagging image for Fly.io..."
docker tag $IMAGE_NAME registry.fly.io/$APP_NAME:latest

# Push the image to Fly.io
echo "Pushing image to Fly.io..."
docker push registry.fly.io/$APP_NAME:latest

# Deploy the app on Fly.io
echo "Deploying app on Fly.io..."
fly deploy --image registry.fly.io/$APP_NAME:latest

echo "Deployment complete!"
