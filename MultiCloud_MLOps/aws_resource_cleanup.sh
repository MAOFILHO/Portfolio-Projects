#!/bin/bash
# Don't exit on error - we handle errors explicitly
set -o pipefail

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

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_section() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

# Function to check if AWS CLI is configured
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS CLI is not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    print_success "AWS CLI is configured"
}

# Function to confirm deletion
confirm_deletion() {
    echo ""
    print_warning "This script will DELETE ALL AWS resources for Guardian AI project:"
    echo "  • S3 bucket (guardian-videos-*)"
    echo "  • SQS queues (guardian-video-processing, guardian-gpu-processing)"
    echo "  • DynamoDB tables (guardian-videos, guardian-events)"
    echo ""
    read -p "Are you sure you want to proceed? (type 'yes' to confirm): " confirmation
    
    if [ "$confirmation" != "yes" ]; then
        print_info "Deletion cancelled."
        exit 0
    fi
}

print_section "Guardian AI - AWS Resource Cleanup"

# Check AWS CLI
print_info "Checking AWS CLI configuration..."
check_aws_cli

# Get AWS account ID and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
# Respect AWS_REGION env var first, then aws configure, no hardcoded fallback
REGION="${AWS_REGION:-$(aws configure get region)}"
if [ -z "$REGION" ]; then
    echo "ERROR: No AWS region configured. Set AWS_REGION or run: aws configure"
    exit 1
fi
BUCKET_SUFFIX=$(echo $ACCOUNT_ID | cut -c1-8)
PRIMARY_BUCKET="guardian-videos-${BUCKET_SUFFIX}"

print_info "AWS Account ID: $ACCOUNT_ID"
print_info "Region: $REGION"
print_info "S3 Bucket: $PRIMARY_BUCKET"

# Confirm deletion
confirm_deletion

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# S3 Bucket Cleanup
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_section "Cleaning up S3 Bucket"

if aws s3api head-bucket --bucket "$PRIMARY_BUCKET" --region "$REGION" 2>/dev/null; then
    print_info "Found S3 bucket: $PRIMARY_BUCKET"
    
    # Check if bucket has objects (including versions)
    print_info "Checking bucket contents..."
    
    # Quick check for objects
    OBJECT_CHECK=$(aws s3api list-objects-v2 --bucket "$PRIMARY_BUCKET" --region "$REGION" --max-items 1 --query 'Contents | length(@)' --output text 2>/dev/null || echo "0")
    VERSION_CHECK=$(aws s3api list-object-versions --bucket "$PRIMARY_BUCKET" --region "$REGION" --max-items 1 --query 'Versions | length(@)' --output text 2>/dev/null || echo "0")
    
    if [ "$OBJECT_CHECK" != "0" ] || [ "$VERSION_CHECK" != "0" ]; then
        print_warning "Bucket contains objects or versions"
        print_info "Deleting all contents (this may take a while for large buckets)..."
        
        # Use aws s3 rm --recursive to delete all objects
        # This handles regular objects and most versioned objects
        print_info "Removing all objects recursively..."
        aws s3 rm "s3://${PRIMARY_BUCKET}" --recursive --region "$REGION" 2>&1 | grep -v "^$" || true
        
        # For versioned buckets, we need to handle versions separately
        # Check if versioning is enabled
        VERSIONING_STATUS=$(aws s3api get-bucket-versioning --bucket "$PRIMARY_BUCKET" --region "$REGION" --query 'Status' --output text 2>/dev/null || echo "None")
        
        if [ "$VERSIONING_STATUS" = "Enabled" ] || [ "$VERSIONING_STATUS" = "Suspended" ]; then
            print_info "Bucket has versioning enabled. Removing all versions and delete markers..."
            print_info "This may take a while for buckets with many versions..."
            
            # Use a more reliable method: delete versions using aws s3api delete-objects
            # Process in batches until no more versions exist
            MAX_ATTEMPTS=50
            ATTEMPT=0
            
            while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
                ATTEMPT=$((ATTEMPT + 1))
                
                # Get versions and delete markers
                VERSIONS_OUTPUT=$(aws s3api list-object-versions \
                    --bucket "$PRIMARY_BUCKET" \
                    --region "$REGION" \
                    --max-items 1000 \
                    --output json 2>/dev/null || echo '{"Versions":[],"DeleteMarkers":[]}')
                
                # Count versions and delete markers - use a more reliable method
                VERSIONS_COUNT=$(echo "$VERSIONS_OUTPUT" | grep -o '"VersionId"' | wc -l 2>/dev/null | awk '{print $1}' || echo "0")
                DELETE_MARKERS_COUNT=$(echo "$VERSIONS_OUTPUT" | grep -o '"DeleteMarker": true' | wc -l 2>/dev/null | awk '{print $1}' || echo "0")
                
                # Ensure clean integers
                VERSIONS_COUNT=$((VERSIONS_COUNT + 0))
                DELETE_MARKERS_COUNT=$((DELETE_MARKERS_COUNT + 0))
                
                if [ "$VERSIONS_COUNT" -eq 0 ] && [ "$DELETE_MARKERS_COUNT" -eq 0 ]; then
                    break
                fi
                
                if [ $((ATTEMPT % 5)) -eq 0 ]; then
                    print_info "  Processing... ($VERSIONS_COUNT versions, $DELETE_MARKERS_COUNT delete markers, attempt $ATTEMPT/$MAX_ATTEMPTS)"
                fi
                
                # Delete versions and delete markers separately (more reliable)
                TEMP_DELETE_FILE="/tmp/s3-delete-${PRIMARY_BUCKET}-$$-${ATTEMPT}.json"
                
                # Build delete request - handle versions and delete markers separately
                # First, delete versions
                if [ "$VERSIONS_COUNT" -gt 0 ]; then
                    VERSIONS_DELETE=$(aws s3api list-object-versions \
                        --bucket "$PRIMARY_BUCKET" \
                        --region "$REGION" \
                        --max-items 1000 \
                        --output json \
                        --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}, Quiet: true}' 2>/dev/null || echo '{"Objects":[],"Quiet":true}')
                    
                    echo "$VERSIONS_DELETE" > "$TEMP_DELETE_FILE"
                    aws s3api delete-objects \
                        --bucket "$PRIMARY_BUCKET" \
                        --region "$REGION" \
                        --delete "file://$TEMP_DELETE_FILE" \
                        > /dev/null 2>&1 || true
                fi
                
                # Then, delete delete markers
                if [ "$DELETE_MARKERS_COUNT" -gt 0 ]; then
                    DELETE_MARKERS_DELETE=$(aws s3api list-object-versions \
                        --bucket "$PRIMARY_BUCKET" \
                        --region "$REGION" \
                        --max-items 1000 \
                        --output json \
                        --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}, Quiet: true}' 2>/dev/null || echo '{"Objects":[],"Quiet":true}')
                    
                    echo "$DELETE_MARKERS_DELETE" > "$TEMP_DELETE_FILE"
                    aws s3api delete-objects \
                        --bucket "$PRIMARY_BUCKET" \
                        --region "$REGION" \
                        --delete "file://$TEMP_DELETE_FILE" \
                        > /dev/null 2>&1 || true
                fi
                
                rm -f "$TEMP_DELETE_FILE"
                
                # Small delay to avoid rate limiting
                sleep 0.5
            done
            
            if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
                print_warning "Reached maximum attempts. Trying final cleanup..."
                # Final attempt with aws s3 rm
                aws s3 rm "s3://${PRIMARY_BUCKET}" --recursive --region "$REGION" > /dev/null 2>&1 || true
            else
                print_success "All versions and delete markers removed"
            fi
        fi
        
        print_success "All bucket contents deleted"
    else
        print_info "Bucket is empty"
    fi
    
    # Delete the bucket using aws s3 rb --force
    # This command handles empty buckets, versioned buckets, and non-empty buckets
    print_info "Deleting S3 bucket: $PRIMARY_BUCKET"
    
    # First, verify bucket is actually empty
    print_info "Verifying bucket is empty..."
    REMAINING_OBJECTS=$(aws s3api list-objects-v2 --bucket "$PRIMARY_BUCKET" --region "$REGION" --max-items 1 --query 'Contents | length(@)' --output text 2>/dev/null || echo "0")
    REMAINING_VERSIONS=$(aws s3api list-object-versions --bucket "$PRIMARY_BUCKET" --region "$REGION" --max-items 1 --query 'Versions | length(@)' --output text 2>/dev/null || echo "0")
    REMAINING_DELETE_MARKERS=$(aws s3api list-object-versions --bucket "$PRIMARY_BUCKET" --region "$REGION" --max-items 1 --query 'DeleteMarkers | length(@)' --output text 2>/dev/null || echo "0")
    
    if [ "$REMAINING_OBJECTS" != "0" ] || [ "$REMAINING_VERSIONS" != "0" ] || [ "$REMAINING_DELETE_MARKERS" != "0" ]; then
        print_warning "Bucket still contains items. Attempting final cleanup..."
        aws s3 rm "s3://${PRIMARY_BUCKET}" --recursive --region "$REGION" 2>&1 | head -20 || true
        sleep 2
    fi
    
    # Try to delete the bucket (show errors this time)
    print_info "Attempting bucket deletion..."
    DELETE_OUTPUT=$(aws s3 rb "s3://${PRIMARY_BUCKET}" --force --region "$REGION" 2>&1)
    DELETE_EXIT_CODE=$?
    
    if [ $DELETE_EXIT_CODE -eq 0 ]; then
        print_success "S3 bucket deleted: $PRIMARY_BUCKET"
    else
        print_error "Could not delete bucket: $PRIMARY_BUCKET"
        echo "Error output: $DELETE_OUTPUT"
        echo ""
        print_warning "Manual deletion required. Run these commands:"
        echo ""
        echo "  # Check what's still in the bucket:"
        echo "  aws s3api list-object-versions --bucket $PRIMARY_BUCKET --region $REGION"
        echo ""
        echo "  # Delete all remaining objects/versions:"
        echo "  aws s3 rm s3://$PRIMARY_BUCKET --recursive --region $REGION"
        echo ""
        echo "  # Then delete the bucket:"
        echo "  aws s3 rb s3://$PRIMARY_BUCKET --force --region $REGION"
        echo ""
        print_info "Or delete the bucket manually in AWS Console."
    fi
else
    print_info "S3 bucket not found: $PRIMARY_BUCKET (skipping)"
fi

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SQS Queues Cleanup
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_section "Cleaning up SQS Queues"

SQS_QUEUES=("guardian-video-processing" "guardian-gpu-processing")

for QUEUE_NAME in "${SQS_QUEUES[@]}"; do
    print_info "Checking SQS queue: $QUEUE_NAME"
    
    QUEUE_URL=$(aws sqs get-queue-url --queue-name "$QUEUE_NAME" --region "$REGION" --query 'QueueUrl' --output text 2>/dev/null || echo "")
    
    if [ -n "$QUEUE_URL" ]; then
        print_info "Found queue: $QUEUE_NAME"
        
        # Purge queue before deletion (optional but good practice)
        print_info "Purging queue messages..."
        aws sqs purge-queue --queue-url "$QUEUE_URL" --region "$REGION" 2>/dev/null || print_warning "Could not purge queue (may be empty or already purged)"
        
        # Delete the queue
        print_info "Deleting queue: $QUEUE_NAME"
        aws sqs delete-queue --queue-url "$QUEUE_URL" --region "$REGION" || {
            print_error "Failed to delete queue: $QUEUE_NAME"
            exit 1
        }
        
        print_success "SQS queue deleted: $QUEUE_NAME"
    else
        print_info "SQS queue not found: $QUEUE_NAME (skipping)"
    fi
done

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DynamoDB Tables Cleanup
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_section "Cleaning up DynamoDB Tables"

DYNAMODB_TABLES=("guardian-videos" "guardian-events")

for TABLE_NAME in "${DYNAMODB_TABLES[@]}"; do
    print_info "Checking DynamoDB table: $TABLE_NAME"
    
    if aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" &>/dev/null; then
        print_info "Found table: $TABLE_NAME"
        
        # Check if table has items (optional - just for info)
        ITEM_COUNT=$(aws dynamodb scan --table-name "$TABLE_NAME" --region "$REGION" --select COUNT --query 'Count' --output text 2>/dev/null || echo "0")
        
        if [ "$ITEM_COUNT" -gt 0 ]; then
            print_warning "Table contains $ITEM_COUNT items (will be deleted with table)"
        fi
        
        # Delete the table
        print_info "Deleting table: $TABLE_NAME"
        aws dynamodb delete-table --table-name "$TABLE_NAME" --region "$REGION" || {
            print_error "Failed to delete table: $TABLE_NAME"
            exit 1
        }
        
        # Wait for table to be deleted
        print_info "Waiting for table deletion to complete..."
        aws dynamodb wait table-not-exists --table-name "$TABLE_NAME" --region "$REGION" || {
            print_warning "Table deletion may still be in progress"
        }
        
        print_success "DynamoDB table deleted: $TABLE_NAME"
    else
        print_info "DynamoDB table not found: $TABLE_NAME (skipping)"
    fi
done

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Summary
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_section "Cleanup Complete! 🎉"

echo -e "${GREEN}AWS Resources Deleted:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "S3 Bucket:            ${GREEN}$PRIMARY_BUCKET${NC}"
echo -e "SQS Queues:           ${GREEN}2 queues${NC}"
echo -e "DynamoDB Tables:      ${GREEN}2 tables${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
print_success "All AWS resources have been deleted successfully!"
echo ""
print_info "Note: If any resources still exist, they may be in use or have dependencies."
print_info "Check AWS Console to verify all resources are deleted."
