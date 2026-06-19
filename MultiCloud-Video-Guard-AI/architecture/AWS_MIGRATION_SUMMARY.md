# AWS Migration Summary - Hybrid Architecture

## Overview

This project has been migrated to a **Balanced Hybrid Architecture**:
- **AWS**: Primary storage, queues, and database (S3, SQS, DynamoDB)
- **Azure**: Compute, ML, and LLM services (AKS, Azure ML, Azure OpenAI)

## Changes Made

### 1. Service Code Updates

All services have been updated to use AWS SDK (boto3) instead of Azure SDKs:

#### Updated Services:
- ✅ `services/ingestion/` - Uses S3, SQS, DynamoDB
- ✅ `services/fast-screening/` - Uses DynamoDB, SQS
- ✅ `services/deep-vision/` - Uses S3, DynamoDB
- ✅ `services/policy-engine/` - Uses DynamoDB, SQS
- ✅ `services/human-review/` - Uses DynamoDB
- ✅ `services/notification/` - Uses DynamoDB

#### Requirements Updated:
- Removed: `azure-cosmos`, `azure-storage-blob`, `azure-servicebus`
- Added: `boto3==1.34.0`, `botocore==1.34.0`

### 2. Infrastructure Updates

#### Infrastructure:
- ✅ Added AWS S3 bucket for primary video storage
- ✅ Added AWS SQS queues (video-processing, gpu-processing, human-review, notification)
- ✅ Added AWS DynamoDB tables (videos, decisions, reviews, notifications)
- ✅ Kept Azure resources (AKS, ACR for compute/container registry)

#### Setup Scripts:
- ✅ Updated `scripts/setup-aws.sh` - Creates all primary AWS resources
- ✅ Script now creates: S3, SQS, DynamoDB

### 3. Configuration Updates

#### Docker Compose (`docker-compose.yml`):
- ✅ Updated all services with AWS environment variables
- ✅ Removed Azure-specific environment variables
- ✅ Added AWS credentials, S3 bucket, SQS URLs, DynamoDB table names

#### Environment Variables:
Create a `.env` file with:
```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=ap-south-1
S3_BUCKET_NAME=guardian-videos-xxxxxxxx
SQS_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/ACCOUNT_ID/guardian-video-processing
SQS_GPU_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/ACCOUNT_ID/guardian-gpu-processing
SQS_REVIEW_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/ACCOUNT_ID/guardian-human-review
SQS_NOTIFICATION_QUEUE_URL=https://sqs.ap-south-1.amazonaws.com/ACCOUNT_ID/guardian-notification

# DynamoDB Tables
DYNAMODB_VIDEOS_TABLE=guardian-videos
DYNAMODB_DECISIONS_TABLE=guardian-decisions
DYNAMODB_REVIEWS_TABLE=guardian-reviews
DYNAMODB_NOTIFICATIONS_TABLE=guardian-notifications

# Azure OpenAI (Optional - Keep on Azure)
AZURE_OPENAI_ENABLED=true
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

## AWS Services Used

### Primary Services (Replaced Azure):
1. **S3** - Video storage (replaces Azure Blob Storage)
2. **SQS** - Message queues (replaces Azure Service Bus)
3. **DynamoDB** - Database (replaces Azure Cosmos DB)
4. **CloudWatch** - Monitoring (optional, later)

### DR Services:
- Not required for the learning-focused setup

## Azure Services Kept

### Compute & ML (Still on Azure):
1. **AKS** - Kubernetes cluster
2. **Azure ML Workspace** - MLOps platform
3. **Azure OpenAI** - LLM service (GPT-4o)

## Migration Steps

### 1. Setup AWS Resources
```bash
# Configure AWS CLI
aws configure

# Create all AWS resources
bash scripts/setup-aws.sh

# Get queue URLs
export SQS_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-video-processing --query 'QueueUrl' --output text)
export SQS_GPU_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-gpu-processing --query 'QueueUrl' --output text)
export SQS_REVIEW_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-human-review --query 'QueueUrl' --output text)
export SQS_NOTIFICATION_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-notification --query 'QueueUrl' --output text)
```

### 2. Update Environment Variables
Create `.env` file with AWS credentials and resource names.

### 3. Rebuild Services
```bash
# Rebuild Docker images
docker-compose build

# Start services
docker-compose up -d
```

### 4. Test Services
```bash
# Test ingestion
curl -X POST http://localhost:8000/upload -F "file=@test-video.mp4"

# Check DynamoDB
aws dynamodb scan --table-name guardian-videos

# Check SQS
aws sqs get-queue-attributes --queue-url $SQS_QUEUE_URL --attribute-names All
```

## Benefits of Hybrid Architecture

1. **Cost Optimization**: AWS S3, SQS, DynamoDB are more cost-effective for storage/queue/DB
2. **Best of Both Clouds**: Use Azure for ML/LLM, AWS for storage/queues
3. **Learning-Friendly Setup**: Minimal, cost-aware hybrid architecture
4. **Service Integration**: Better AWS service integration for storage/queue patterns

## Next Steps

1. ✅ All code updated to use AWS SDK
2. ✅ Infrastructure scripts updated
3. ✅ Docker compose updated
4. ⏳ Update Kubernetes manifests (if deploying to AKS)
5. ⏳ Update CI/CD pipelines
6. ⏳ Test end-to-end workflow

## Notes

- Azure Cosmos DB, Blob Storage, and Service Bus are **no longer used** in the codebase
- All services now use AWS SDK (boto3) for storage, queues, and database
- Azure is still used for: AKS (compute), Azure ML (MLOps), Azure OpenAI (LLM)
- This is a **hybrid architecture** - not a full migration to AWS

---

**Status**: ✅ Migration Complete
**Architecture**: Balanced Hybrid (AWS Storage/Queue/DB + Azure Compute/ML/LLM)
