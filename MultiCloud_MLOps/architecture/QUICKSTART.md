# Guardian AI - Quick Start Guide

**Get the simplified MLOps system running in 30 minutes!**

---

## 🎯 What You'll Build

A complete video moderation system with:
- 6 microservices (ingestion, screening, analysis, policy, review, notification)
- AWS storage (S3, SQS, DynamoDB)
- Local Docker Compose deployment
- **Cost**: ~$10-25/month

---

## ⚡ Quick Start (30 minutes)

### Step 1: Prerequisites (5 minutes)
```bash
# Check you have these installed:
docker --version          # Need Docker Desktop 24+
python3 --version        # Need Python 3.11+
aws --version            # Need AWS CLI 2.13+

# Install if missing (macOS):
brew install docker python@3.11 awscli
```

### Step 2: Setup AWS (10 minutes)
```bash
# Configure AWS credentials
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter region: ap-south-1
# Enter output format: json

# Verify
aws sts get-caller-identity

# Create AWS resources (1 S3 bucket, 2 SQS queues, 2 DynamoDB tables)
cd ~/Projects/MLOps_Project
bash scripts/setup-aws.sh

# Save the S3 bucket name from the output
export S3_BUCKET_NAME="guardian-videos-xxxxxxxx"
```

### Step 3: Configure Environment (5 minutes)
```bash
# Get SQS queue URLs
export SQS_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-video-processing --query 'QueueUrl' --output text)
export SQS_GPU_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-gpu-processing --query 'QueueUrl' --output text)

# Create .env file
cat > .env <<EOF
AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key)
AWS_REGION=ap-south-1
S3_BUCKET_NAME=$S3_BUCKET_NAME
SQS_QUEUE_URL=$SQS_QUEUE_URL
SQS_GPU_QUEUE_URL=$SQS_GPU_QUEUE_URL
DYNAMODB_VIDEOS_TABLE=guardian-videos
DYNAMODB_EVENTS_TABLE=guardian-events
AZURE_OPENAI_ENABLED=false
EOF

echo "✅ Configuration complete!"
```

### Step 4: Start Services (5 minutes)
```bash
# Build and start all services
docker-compose up --build -d

# Wait for services to start (30 seconds)
sleep 30

# Check all services are healthy
curl http://localhost:8000/health  # Ingestion
curl http://localhost:8001/health  # Fast Screening
curl http://localhost:8003/health  # Policy Engine
curl http://localhost:8004/health  # Human Review
curl http://localhost:8005/health  # Notification

echo "✅ All services running!"
```

### Step 5: Test Upload (5 minutes)
```bash
# Create a test video (or use your own MP4 file)
# For testing, download any small MP4 video

# Upload video
curl -X POST http://localhost:8000/upload \
  -F "file=@test-video.mp4"

# Expected response:
# {"job_id":"<uuid>","status":"queued"}

# Save the job_id
export VIDEO_ID="<uuid-from-response>"

# Check video in DynamoDB
aws dynamodb get-item \
  --table-name guardian-videos \
  --key "{\"video_id\":{\"S\":\"$VIDEO_ID\"}}"

# Check video in S3
aws s3 ls s3://$S3_BUCKET_NAME/videos/

echo "✅ Video uploaded successfully!"
```

---

## 🎉 Success!

You now have a complete MLOps video moderation system running locally!

### What's Running:
- ✅ **Ingestion Service** (port 8000) - Video upload handler
- ✅ **Fast Screening Service** (port 8001) - CPU-based risk screening
- ✅ **Deep Vision Service** (port 8002) - GPU-based deep analysis
- ✅ **Policy Engine Service** (port 8003) - Decision logic
- ✅ **Human Review Service** (port 8004) - Review queue management
- ✅ **Notification Service** (port 8005) - Webhook delivery
- ✅ **Redis** (port 6379) - Caching

### AWS Resources:
- ✅ **S3 Bucket** - Video storage
- ✅ **2 SQS Queues** - Async processing
- ✅ **2 DynamoDB Tables** - Data storage

---

## 📖 Next Steps

### Learn More
1. **[LOCAL_DEVELOPMENT_GUIDE.md](./LOCAL_DEVELOPMENT_GUIDE.md)** - Complete development guide
2. **[ARCHITECTURE_CORRECTED.md](./ARCHITECTURE_CORRECTED.md)** - System architecture
3. **[DEPLOYMENT_OPTIONS.md](./DEPLOYMENT_OPTIONS.md)** - Deployment comparison

### Test the System
```bash
# View service logs
docker-compose logs -f

# View specific service
docker-compose logs -f ingestion

# Check queue depth
aws sqs get-queue-attributes \
  --queue-url $SQS_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages

# Query all videos
aws dynamodb scan --table-name guardian-videos --limit 10

# Query events
aws dynamodb scan --table-name guardian-events --limit 10
```

### Optional: Enable Azure OpenAI
```bash
# Edit .env file
vim .env

# Change:
AZURE_OPENAI_ENABLED=true
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

# Restart services
docker-compose restart
```

### Deploy to Cloud (Optional)
```bash
# Setup Azure AKS
bash scripts/setup-aks.sh

# Build and push images
bash scripts/build-services.sh

# Deploy to Kubernetes
kubectl apply -f k8s/
```

---

## 🔧 Common Commands

### Service Management
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart specific service
docker-compose restart ingestion

# View logs
docker-compose logs -f

# Rebuild after code changes
docker-compose build ingestion
docker-compose up -d ingestion
```

### AWS Management
```bash
# List S3 videos
aws s3 ls s3://$S3_BUCKET_NAME/videos/

# Check SQS queue
aws sqs get-queue-attributes --queue-url $SQS_QUEUE_URL

# Query DynamoDB
aws dynamodb scan --table-name guardian-videos --limit 10

# Delete old videos
aws s3 rm s3://$S3_BUCKET_NAME/videos/ --recursive
```

---

## 🆘 Troubleshooting

### Services won't start
```bash
# Check Docker is running
docker info

# View error logs
docker-compose logs

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

### Can't connect to AWS
```bash
# Verify credentials
aws sts get-caller-identity

# Check .env file
cat .env | grep AWS

# Test S3 access
aws s3 ls s3://$S3_BUCKET_NAME
```

### DynamoDB table not found
```bash
# List tables
aws dynamodb list-tables

# Recreate if missing
bash scripts/setup-aws.sh
```

---

## 💰 Cost Management

### Current Costs (Monthly)
- **AWS S3**: $3-5
- **AWS SQS**: $0.50-1
- **AWS DynamoDB**: $5-10
- **Docker Desktop**: Free
- **Total**: ~$10-25/month

### Stop Services When Not in Use
```bash
# Stop all services
docker-compose down

# Purge SQS queues
aws sqs purge-queue --queue-url $SQS_QUEUE_URL
aws sqs purge-queue --queue-url $SQS_GPU_QUEUE_URL

# Delete old S3 videos
aws s3 rm s3://$S3_BUCKET_NAME/videos/ --recursive
```

---

## 🧹 Cleanup (When Done)

### Delete Everything
```bash
# Stop services
docker-compose down -v

# Delete AWS resources
aws s3 rb s3://$S3_BUCKET_NAME --force
aws sqs delete-queue --queue-url $SQS_QUEUE_URL
aws sqs delete-queue --queue-url $SQS_GPU_QUEUE_URL
aws dynamodb delete-table --table-name guardian-videos
aws dynamodb delete-table --table-name guardian-events

echo "✅ All resources deleted"
```

---

## 📚 Documentation

- **[README.md](./README.md)** - Project overview
- **[LOCAL_DEVELOPMENT_GUIDE.md](./LOCAL_DEVELOPMENT_GUIDE.md)** - Complete guide
- **[ARCHITECTURE_CORRECTED.md](./ARCHITECTURE_CORRECTED.md)** - Architecture details
- **[DEPLOYMENT_OPTIONS.md](./DEPLOYMENT_OPTIONS.md)** - Deployment comparison
- **[SIMPLIFICATION_SUMMARY.md](./SIMPLIFICATION_SUMMARY.md)** - What changed

---

**Time**: 30 minutes
**Cost**: ~$10-25/month
**Status**: ✅ Ready to learn MLOps!

🚀 **Happy coding!**
