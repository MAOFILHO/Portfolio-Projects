"""Entry point for product-service. Run with: python run.py"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from application import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PRODUCT_SERVICE_PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))
