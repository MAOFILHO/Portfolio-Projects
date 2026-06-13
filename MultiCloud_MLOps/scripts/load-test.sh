#!/bin/bash
set -e

echo "Running Load Tests..."

if ! command -v k6 &> /dev/null; then
    echo "Installing k6..."
    brew install k6
fi

k6 run --vus 100 --duration 30s tests/load/load-test.js

echo "Load test complete!"
