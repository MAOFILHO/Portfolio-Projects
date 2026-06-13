#!/bin/bash
set -e

echo "Initializing Guardian AI Project Structure..."

mkdir -p services/{ingestion,fast-screening,deep-vision,policy-engine,human-review,notification}
mkdir -p infrastructure/helm
mkdir -p k8s/{cpu-services,gpu-services,overlays/{staging,production}}
mkdir -p mlops/{training,deployment}
mkdir -p tests/{unit,integration,load}
mkdir -p docs

echo "Project structure created successfully!"
