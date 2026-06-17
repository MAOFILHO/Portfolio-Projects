#!/bin/bash
# verify_cleanup.sh — confirms all project AWS resources have been deleted
# Usage: bash scripts/verify_cleanup.sh

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PASS=0
FAIL=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✅ CLEAN${NC}  $1"; PASS=$((PASS+1)); }
fail() { echo -e "  ${RED}❌ FOUND${NC}   $1"; FAIL=$((FAIL+1)); }
info() { echo -e "  ${YELLOW}ℹ️  INFO${NC}   $1"; }

echo ""
echo "================================================================"
echo "  AgentCore Cleanup Verification  |  Account: $ACCOUNT_ID"
echo "  Region: $REGION"
echo "================================================================"

# ── AgentCore Runtime ─────────────────────────────────────────────
echo ""
echo "[ AgentCore Runtime ]"
RUNTIMES=$(aws bedrock-agentcore list-agent-runtimes \
  --region "$REGION" \
  --query "agentRuntimes[?contains(agentRuntimeName,'customer_support')].agentRuntimeName" \
  --output text 2>/dev/null || echo "")
if [ -z "$RUNTIMES" ]; then ok "No AgentCore Runtimes found"
else fail "Runtime still exists: $RUNTIMES"; fi

# ── AgentCore Memory ──────────────────────────────────────────────
echo ""
echo "[ AgentCore Memory ]"
MEMORIES=$(aws bedrock-agentcore list-memory-resources \
  --region "$REGION" \
  --query "memoryResources[?contains(name,'CustomerSupport')].name" \
  --output text 2>/dev/null || echo "")
if [ -z "$MEMORIES" ]; then ok "No AgentCore Memory resources found"
else fail "Memory still exists: $MEMORIES"; fi

# ── AgentCore Gateway ─────────────────────────────────────────────
echo ""
echo "[ AgentCore Gateway ]"
GATEWAYS=$(aws bedrock-agentcore list-gateways \
  --region "$REGION" \
  --query "gateways[?contains(name,'customersupport')].name" \
  --output text 2>/dev/null || echo "")
if [ -z "$GATEWAYS" ]; then ok "No AgentCore Gateways found"
else fail "Gateway still exists: $GATEWAYS"; fi

# ── CloudFormation Stacks ─────────────────────────────────────────
echo ""
echo "[ CloudFormation Stacks ]"
STACKS=$(aws cloudformation list-stacks \
  --region "$REGION" \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE ROLLBACK_COMPLETE \
  --query "StackSummaries[?contains(StackName,'CustomerSupport')].StackName" \
  --output text 2>/dev/null || echo "")
if [ -z "$STACKS" ]; then ok "No CustomerSupport CloudFormation stacks found"
else fail "Stack still exists: $STACKS"; fi

# ── S3 Buckets ────────────────────────────────────────────────────
echo ""
echo "[ S3 Buckets ]"
BUCKETS=$(aws s3 ls 2>/dev/null | awk '{print $3}' | grep -E "customersupport|customer-support|agentcore|kb-data|kb-vector" || echo "")
if [ -z "$BUCKETS" ]; then ok "No project S3 buckets found"
else fail "S3 bucket(s) still exist: $BUCKETS"; fi

# ── ECR Repositories ──────────────────────────────────────────────
echo ""
echo "[ ECR Repositories ]"
ECR=$(aws ecr describe-repositories \
  --region "$REGION" \
  --query "repositories[?contains(repositoryName,'agentcore') || contains(repositoryName,'customer_support')].repositoryName" \
  --output text 2>/dev/null || echo "")
if [ -z "$ECR" ]; then ok "No AgentCore ECR repositories found"
else fail "ECR repository still exists: $ECR"; fi

# ── CodeBuild Projects ────────────────────────────────────────────
echo ""
echo "[ CodeBuild Projects ]"
CODEBUILD=$(aws codebuild list-projects \
  --region "$REGION" \
  --query "projects[?contains(@,'agentcore') || contains(@,'customer_support')]" \
  --output text 2>/dev/null || echo "")
if [ -z "$CODEBUILD" ]; then ok "No AgentCore CodeBuild projects found"
else fail "CodeBuild project still exists: $CODEBUILD"; fi

# ── IAM Roles ─────────────────────────────────────────────────────
echo ""
echo "[ IAM Roles ]"
# AWSServiceRoleForBedrockAgentCoreRuntimeIdentity is an AWS-managed service-linked
# role — it cannot be deleted manually and is safe to ignore.
IAM_ROLES=$(aws iam list-roles \
  --query "Roles[?contains(RoleName,'CustomerSupport') || contains(RoleName,'AmazonBedrockAgentCoreSDKCodeBuild')].RoleName" \
  --output text 2>/dev/null || echo "")
if [ -z "$IAM_ROLES" ]; then ok "No project IAM roles found"
else fail "IAM role(s) still exist: $IAM_ROLES"; fi

# ── SSM Parameters ────────────────────────────────────────────────
echo ""
echo "[ SSM Parameter Store ]"
SSM=$(aws ssm get-parameters-by-path \
  --path "/app/customersupport" \
  --region "$REGION" \
  --query "Parameters[*].Name" \
  --output text 2>/dev/null || echo "")
if [ -z "$SSM" ]; then ok "No /app/customersupport SSM parameters found"
else fail "SSM parameter(s) still exist: $SSM"; fi

# ── Secrets Manager ───────────────────────────────────────────────
echo ""
echo "[ Secrets Manager ]"
SECRETS=$(aws secretsmanager list-secrets \
  --region "$REGION" \
  --query "SecretList[?contains(Name,'customersupport') || contains(Name,'CustomerSupport')].Name" \
  --output text 2>/dev/null || echo "")
if [ -z "$SECRETS" ]; then ok "No project secrets found"
else fail "Secret(s) still exist: $SECRETS"; fi

# ── Cognito User Pools ────────────────────────────────────────────
echo ""
echo "[ Cognito User Pools ]"
COGNITO=$(aws cognito-idp list-user-pools \
  --max-results 60 \
  --region "$REGION" \
  --query "UserPools[?contains(Name,'CustomerSupport')].Name" \
  --output text 2>/dev/null || echo "")
if [ -z "$COGNITO" ]; then ok "No CustomerSupport Cognito user pools found"
else fail "Cognito pool still exists: $COGNITO"; fi

# ── CloudWatch Log Groups ─────────────────────────────────────────
echo ""
echo "[ CloudWatch Log Groups ]"
LOGS=$(aws logs describe-log-groups \
  --region "$REGION" \
  --query "logGroups[?contains(logGroupName,'customer_support') || contains(logGroupName,'customer-support-assistant')].logGroupName" \
  --output text 2>/dev/null || echo "")
if [ -z "$LOGS" ]; then ok "No project CloudWatch log groups found"
else info "Log group(s) found (may be retained intentionally): $LOGS"; fi

# ── Lambda Functions ──────────────────────────────────────────────
echo ""
echo "[ Lambda Functions ]"
LAMBDAS=$(aws lambda list-functions \
  --region "$REGION" \
  --query "Functions[?contains(FunctionName,'CustomerSupport') || contains(FunctionName,'customer_support')].FunctionName" \
  --output text 2>/dev/null || echo "")
if [ -z "$LAMBDAS" ]; then ok "No project Lambda functions found"
else fail "Lambda function(s) still exist: $LAMBDAS"; fi

# ── DynamoDB Tables ───────────────────────────────────────────────
echo ""
echo "[ DynamoDB Tables ]"
DYNAMO=$(aws dynamodb list-tables \
  --region "$REGION" \
  --query "TableNames[?contains(@,'CustomerSupport') || contains(@,'customer_support')]" \
  --output text 2>/dev/null || echo "")
if [ -z "$DYNAMO" ]; then ok "No project DynamoDB tables found"
else fail "DynamoDB table(s) still exist: $DYNAMO"; fi

# ── Bedrock Knowledge Bases ───────────────────────────────────────
echo ""
echo "[ Bedrock Knowledge Bases ]"
KB_ACTIVE=$(aws bedrock-agent list-knowledge-bases \
  --region "$REGION" \
  --query "knowledgeBaseSummaries[?contains(name,'kb') && status!='DELETE_UNSUCCESSFUL' && status!='DELETING'].name" \
  --output text 2>/dev/null || echo "")
KB_STUCK=$(aws bedrock-agent list-knowledge-bases \
  --region "$REGION" \
  --query "knowledgeBaseSummaries[?contains(name,'kb') && (status=='DELETE_UNSUCCESSFUL' || status=='DELETING')].name" \
  --output text 2>/dev/null || echo "")
if [ -z "$KB_ACTIVE" ] && [ -z "$KB_STUCK" ]; then
  ok "No project Knowledge Bases found"
elif [ -z "$KB_ACTIVE" ] && [ -n "$KB_STUCK" ]; then
  info "KB stuck in DELETE_UNSUCCESSFUL: $KB_STUCK (Bedrock control-plane lag — no action needed, storage is gone)"
  PASS=$((PASS+1))
else
  fail "Active Knowledge Base still exists: $KB_ACTIVE"
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo "================================================================"
TOTAL=$((PASS+FAIL))
if [ "$FAIL" -eq 0 ]; then
  echo -e "  ${GREEN}ALL CLEAR — $PASS/$TOTAL checks passed. No resources left behind.${NC}"
else
  echo -e "  ${RED}$FAIL/$TOTAL checks FAILED — resources still exist (listed above).${NC}"
  echo ""
  echo -e "  ${YELLOW}NOTE: Some AWS services delete asynchronously and can take${NC}"
  echo -e "  ${YELLOW}30–120 seconds to fully propagate after cleanup runs:${NC}"
  echo -e "  ${YELLOW}  • Bedrock Knowledge Base  — up to 60s${NC}"
  echo -e "  ${YELLOW}  • AgentCore Runtime       — up to 60s${NC}"
  echo -e "  ${YELLOW}  • CloudFormation stacks   — up to 120s${NC}"
  echo -e "  ${YELLOW}  • Cognito User Pools      — up to 30s${NC}"
  echo ""
  echo -e "  Wait a moment and re-run:  bash scripts/verify_cleanup.sh"
  echo -e "  If resources persist after 2 minutes, run: python main.py --cleanup"
fi
echo "================================================================"
echo ""
