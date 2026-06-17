import os

# Project-wide AWS region. Defaults to us-east-1; override with AWS_DEFAULT_REGION env var.
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
