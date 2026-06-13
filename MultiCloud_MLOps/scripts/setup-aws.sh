#!/bin/bash
set -e

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_skip() {
    echo -e "${YELLOW}⊘ $1${NC}"
}

print_section() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_section "Guardian AI - Simplified AWS Infrastructure Setup"

# Get script and project directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Use AWS_REGION env var if set, else fall back to aws configure
REGION="${AWS_REGION:-$(aws configure get region)}"
if [ -z "$REGION" ]; then
    echo "ERROR: No AWS region found. Set AWS_REGION in .env or run: aws configure"
    exit 1
fi
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_SUFFIX=$(echo $ACCOUNT_ID | cut -c1-8)

print_info "AWS Account ID: $ACCOUNT_ID"
print_info "Region: $REGION"

# Tags for all resources
TAGS="Key=Project,Value=guardian-ai Key=ManagedBy,Value=script Key=Environment,Value=production"

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# S3 Buckets
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_section "Creating S3 Bucket"

# Primary S3 Bucket for Videos
# Allow S3_BUCKET_OVERRIDE env var to use a custom name (avoids AWS deletion lock-out)
PRIMARY_BUCKET="${S3_BUCKET_OVERRIDE:-guardian-videos-${BUCKET_SUFFIX}}"
print_info "Checking primary S3 bucket: $PRIMARY_BUCKET"

if aws s3api head-bucket --bucket "$PRIMARY_BUCKET" 2>/dev/null; then
    print_skip "Bucket already exists: $PRIMARY_BUCKET"
else
    # us-east-1 does NOT accept LocationConstraint — it's the S3 default region
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$PRIMARY_BUCKET" \
            --region "$REGION"
    else
        aws s3api create-bucket \
            --bucket "$PRIMARY_BUCKET" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION"
    fi
    
    # Add tags to bucket
    aws s3api put-bucket-tagging \
        --bucket "$PRIMARY_BUCKET" \
        --tagging "TagSet=[{Key=Project,Value=guardian-ai},{Key=Purpose,Value=video-storage},{Key=Environment,Value=production}]"
    
    print_success "Created primary bucket: $PRIMARY_BUCKET"
fi

# Enable versioning
print_info "Enabling versioning on $PRIMARY_BUCKET"
aws s3api put-bucket-versioning \
    --bucket $PRIMARY_BUCKET \
    --versioning-configuration Status=Enabled
print_success "Versioning enabled"

# S3 Lifecycle for Glacier (OPTIONAL - Commented out by default)
# Uncomment to enable automatic archiving to Glacier after 90 days
# print_info "Configuring lifecycle policy for $PRIMARY_BUCKET"
# cat > /tmp/lifecycle.json <<EOF
# {
#   "Rules": [
#     {
#       "ID": "ArchiveOldVideos",
#       "Status": "Enabled",
#       "Filter": {
#         "Prefix": ""
#       },
#       "Transitions": [
#         {
#           "Days": 90,
#           "StorageClass": "GLACIER"
#         }
#       ]
#     }
#   ]
# }
# EOF
# 
# aws s3api put-bucket-lifecycle-configuration \
#     --bucket $PRIMARY_BUCKET \
#     --lifecycle-configuration file:///tmp/lifecycle.json
# print_success "Lifecycle policy configured (archive to Glacier after 90 days)"

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SQS Queues (SIMPLIFIED: 2 queues instead of 4)
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_section "Creating SQS Queues (Simplified: 2 queues)"

# Helper function to create SQS queue
create_sqs_queue() {
    local queue_name=$1
    local retention=$2
    local visibility=$3
    
    print_info "Checking SQS queue: $queue_name"
    
    # Check if queue exists
    if aws sqs get-queue-url --queue-name "$queue_name" --region "$REGION" &>/dev/null; then
        print_skip "Queue already exists: $queue_name"
    else
        aws sqs create-queue \
            --queue-name "$queue_name" \
            --region "$REGION" \
            --attributes MessageRetentionPeriod=$retention,VisibilityTimeout=$visibility \
            --tags Project=guardian-ai,ManagedBy=script,Environment=production
        print_success "Created queue: $queue_name"
    fi
}

# Create simplified queues
print_info "Creating main processing queue (ingestion → fast-screening)"
create_sqs_queue "guardian-video-processing" "1209600" "300"

print_info "Creating GPU processing queue (fast-screening → deep-vision, KEDA autoscaling)"
create_sqs_queue "guardian-gpu-processing" "1209600" "600"

print_success "SQS queues created (2/2)"
echo ""
print_info "Note: Human review and notifications now use direct HTTP calls (simpler, no queues needed)"

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DynamoDB Tables (SIMPLIFIED: 2 tables instead of 4)
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_section "Creating DynamoDB Tables (Simplified: 2 tables)"

# Helper function to create DynamoDB table
create_dynamodb_table() {
    local table_name=$1
    local key_name=$2
    
    print_info "Checking DynamoDB table: $table_name"
    
    # Check if table exists
    if aws dynamodb describe-table --table-name "$table_name" --region "$REGION" &>/dev/null; then
        print_skip "Table already exists: $table_name"
    else
        aws dynamodb create-table \
            --table-name "$table_name" \
            --attribute-definitions AttributeName=$key_name,AttributeType=S \
            --key-schema AttributeName=$key_name,KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --tags Key=Project,Value=guardian-ai Key=ManagedBy,Value=script Key=Environment,Value=production \
            --region "$REGION" > /dev/null
        
        print_success "Created table: $table_name"
        
        # Wait for table to be active
        print_info "Waiting for $table_name to be active..."
        aws dynamodb wait table-exists --table-name "$table_name" --region "$REGION"
        print_success "Table $table_name is now active"
    fi
}

# Create simplified tables
print_info "Creating videos table (single source of truth for all video data)"
create_dynamodb_table "guardian-videos" "video_id"

print_info "Creating events table (audit log for all events with TTL)"
create_dynamodb_table "guardian-events" "event_id"

# Enable TTL on events table (auto-cleanup after 90 days)
print_info "Enabling TTL on events table (auto-cleanup after 90 days)"
aws dynamodb update-time-to-live \
    --table-name guardian-events \
    --time-to-live-specification "Enabled=true, AttributeName=ttl" \
    --region "$REGION" > /dev/null 2>&1 || print_skip "TTL already enabled or not supported"

print_success "DynamoDB tables created (2/2)"
echo ""
print_info "Note: Consolidated from 4 tables to 2 tables for simplicity"
print_info "  - videos: Stores all video metadata, scores, decisions, and review status"
print_info "  - events: Audit log for all events (uploads, screens, decisions, notifications)"

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Summary
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_section "Setup Complete! 🎉"

echo -e "${GREEN}AWS Resources Summary (Simplified):${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Primary S3 Bucket:   ${GREEN}$PRIMARY_BUCKET${NC}"
echo -e "Region:              ${GREEN}$REGION${NC}"
echo -e "Account ID:          ${GREEN}$ACCOUNT_ID${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}SQS Queues Created (2):${NC}"
echo "  • guardian-video-processing (main processing)"
echo "  • guardian-gpu-processing (GPU autoscaling)"
echo ""
echo -e "${YELLOW}DynamoDB Tables Created (2):${NC}"
echo "  • guardian-videos (primary data)"
echo "  • guardian-events (audit log with TTL)"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Cost Savings:${NC}"
echo "  • 50% reduction in SQS costs (2 queues vs 4)"
echo "  • 50% reduction in DynamoDB costs (2 tables vs 4)"
echo "  • Estimated monthly cost: ~$25-40 (down from $50-100)"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Next Steps:${NC}"
echo "1. Update k8s/configmap.yaml with AWS values:"
echo -e "   ${YELLOW}./scripts/update-k8s-config.sh${NC}"
echo "2. Configure Kubernetes secrets with AWS credentials"
echo "3. Update .env file with queue URLs and table names"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
