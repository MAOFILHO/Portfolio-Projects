#!/bin/bash
set -e

echo "🔄 Updating Kubernetes ConfigMap with AWS values..."

# Get AWS Account ID and Region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)

if [ -z "$AWS_ACCOUNT_ID" ] || [ -z "$AWS_REGION" ]; then
    echo "❌ Error: Could not retrieve AWS account information"
    echo "Please run 'aws configure' first"
    exit 1
fi

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"

# Define resource names (should match setup-aws.sh)
S3_BUCKET="guardian-videos"
DYNAMODB_VIDEOS_TABLE="guardian-videos"
DYNAMODB_DECISIONS_TABLE="guardian-decisions"
DYNAMODB_REVIEWS_TABLE="guardian-reviews"
DYNAMODB_NOTIFICATIONS_TABLE="guardian-notifications"

# Construct SQS URLs
SQS_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/guardian-video-processing"
SQS_GPU_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/guardian-gpu-processing"
SQS_REVIEW_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/guardian-human-review"
SQS_NOTIFICATION_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/guardian-notification"

# Update ConfigMap
cat > k8s/configmap.yaml << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: guardian-config
  namespace: production
data:
  AWS_REGION: "${AWS_REGION}"
  S3_BUCKET_NAME: "${S3_BUCKET}"
  DYNAMODB_VIDEOS_TABLE: "${DYNAMODB_VIDEOS_TABLE}"
  DYNAMODB_DECISIONS_TABLE: "${DYNAMODB_DECISIONS_TABLE}"
  DYNAMODB_REVIEWS_TABLE: "${DYNAMODB_REVIEWS_TABLE}"
  DYNAMODB_NOTIFICATIONS_TABLE: "${DYNAMODB_NOTIFICATIONS_TABLE}"
  SQS_QUEUE_URL: "${SQS_QUEUE_URL}"
  SQS_GPU_QUEUE_URL: "${SQS_GPU_QUEUE_URL}"
  SQS_REVIEW_QUEUE_URL: "${SQS_REVIEW_QUEUE_URL}"
  SQS_NOTIFICATION_QUEUE_URL: "${SQS_NOTIFICATION_QUEUE_URL}"
  LOG_LEVEL: "INFO"
EOF

echo "✅ ConfigMap updated at k8s/configmap.yaml"
echo ""
echo "📋 Values set:"
echo "   Region: $AWS_REGION"
echo "   Account ID: $AWS_ACCOUNT_ID"
echo "   S3 Bucket: $S3_BUCKET"
echo "   DynamoDB Tables: 4 tables configured"
echo "   SQS Queues: 4 queues configured"
echo ""
echo "Next steps:"
echo "1. Review k8s/configmap.yaml"
echo "2. Apply with: kubectl apply -f k8s/configmap.yaml"
