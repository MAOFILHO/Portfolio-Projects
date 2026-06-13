# Azure OpenAI Integration Summary

## Overview

This document summarizes the integration of Azure OpenAI (GPT-4o) into the Guardian AI MLOps platform. The integration follows the principle: **LLMs are adjacent, not foundational** - they assist but never make final moderation decisions.

## Key Principles

### ✅ Where Azure OpenAI IS Used

1. **Human Review Copilot** (Primary Use Case)
   - Summarizes why content was flagged
   - Highlights key frames and timestamps
   - Suggests actions (reviewer makes final decision)
   - Multilingual explanation generation

2. **Policy Interpretation** (Enterprise Use Case)
   - Converts natural language policies → executable rules
   - Assists compliance teams (non-technical users)

3. **Moderation Explanation** (Optional Enhancement)
   - Generates human-readable explanations asynchronously
   - Off critical path (fire-and-forget)

### ❌ Where Azure OpenAI is NOT Used

- ❌ Primary moderation (Fast Screening, Deep Vision core inference)
- ❌ Real-time decision making (Policy Engine decisions)
- ❌ Critical path operations

## Changes Made

### 1. Fast Screening Service (`services/fast-screening/`)

**Changes**:
- ✅ Removed Azure OpenAI client (was imported but not used)
- ✅ Removed `openai` and `azure-identity` from requirements.txt
- ✅ Updated comments to clarify: "classical ML features (no LLM on critical path)"
- ✅ Changed `screening_type` from "cpu_ai" to "cpu"

**Rationale**: Fast screening uses deterministic classical ML features. LLMs should not be on the critical path for primary moderation.

### 2. Deep Vision Service (`services/deep-vision/`)

**Changes**:
- ✅ Made Azure OpenAI optional via `AZURE_OPENAI_ENABLED` environment variable
- ✅ Moved explanation generation to async, fire-and-forget pattern
- ✅ Explanation generation no longer blocks ML inference response
- ✅ Added `/explain` endpoint (optional, can be disabled)
- ✅ Default: `AZURE_OPENAI_ENABLED=false` (optional feature)

**Rationale**: Explanation generation is a nice-to-have enhancement. It should not impact the critical ML inference pipeline.

**Key Code Pattern**:
```python
# ML inference completes first (critical path)
nsfw_avg = calculate_scores(frames_data)

# Save to DB immediately
save_decision(video_id, nsfw_avg, violence_avg)

# Generate explanation asynchronously (off critical path)
if AZURE_OPENAI_ENABLED:
    asyncio.create_task(generate_explanation_async(...))
```

### 3. Human Review Service (`services/human-review/`)

**Changes**:
- ✅ Added Azure OpenAI client (optional, enabled by default)
- ✅ Added `openai==1.12.0` to requirements.txt
- ✅ Added three new endpoints:
  - `GET /review/{video_id}/summary` - AI summary for reviewer
  - `POST /review/{video_id}/suggest` - AI suggestion (non-binding)
  - `GET /review/{video_id}/explain` - Multilingual explanation for creators
- ✅ Enhanced `/queue` endpoint to include AI summaries if available
- ✅ Default: `AZURE_OPENAI_ENABLED=true` (enabled by default)

**Rationale**: This is the primary use case for LLMs - assisting human reviewers without making decisions.

**New Endpoints**:

1. **`GET /review/{video_id}/summary`**
   - Generates concise summary for reviewer
   - Highlights key timestamps/frames
   - Caches results
   - Supports multilingual output

2. **`POST /review/{video_id}/suggest`**
   - Provides AI suggestion (clearly marked as non-binding)
   - Includes disclaimer that reviewer makes final decision
   - Helps reviewers focus on important factors

3. **`GET /review/{video_id}/explain`**
   - Generates explanation for content creators
   - Multilingual support (via `language` parameter)
   - Professional, clear explanations
   - Caches per language

### 4. Policy Engine Service (`services/policy-engine/`)

**Changes**:
- ✅ Added Azure OpenAI client (optional, enabled by default)
- ✅ Added `openai==1.12.0` to requirements.txt
- ✅ Added new endpoints:
  - `POST /policy/interpret` - Convert natural language to structured rules
  - `POST /policy/validate` - Validate policy rules
- ✅ Added `PolicyRule` and `NaturalLanguagePolicy` models
- ✅ Default: `AZURE_OPENAI_ENABLED=true` (enabled by default)

**Rationale**: Enables compliance teams to author policies in natural language, which are then converted to executable rules.

**New Endpoints**:

1. **`POST /policy/interpret`**
   - Input: Natural language policy text
   - Output: Structured JSON rules
   - Example:
     ```json
     {
       "policy_text": "Apply stricter thresholds for minors in EU regions",
       "region": "EU"
     }
     ```
   - Returns executable rules with conditions, actions, and thresholds

2. **`POST /policy/validate`**
   - Validates policy rules for correctness
   - Checks action types, threshold ranges, age groups
   - Returns validation errors if any

### 5. Architecture Documentation (`ARCHITECTURE.md`)

**Changes**:
- ✅ Added "LLM Assist Layer" subgraph to architecture diagram
- ✅ Added section "5. Azure OpenAI Integration (Optional LLM Layer)"
- ✅ Added detailed "Azure OpenAI Integration Details" section
- ✅ Updated version to 1.1
- ✅ Documented configuration, cost management, and failure handling

## Configuration

### Environment Variables

```bash
# Enable/disable LLM features (service-specific defaults)
AZURE_OPENAI_ENABLED=true  # true for human-review/policy-engine, false for deep-vision

# Azure OpenAI credentials
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

### Service-Specific Defaults

| Service | Default | Rationale |
|---------|---------|-----------|
| Human Review | `true` | Primary use case - reviewer productivity |
| Policy Engine | `true` | Enterprise feature - policy authoring |
| Deep Vision | `false` | Optional enhancement - off critical path |

## Cost Impact

### Usage Patterns

- **Human Review**: ~1-2 API calls per review (cached after first call)
- **Policy Engine**: ~1 API call per new policy (infrequent)
- **Deep Vision**: ~1 API call per high-risk video (optional, async)

### Estimated Costs (GPT-4o)

- Human Review: ~$0.01-0.02 per review
- Policy Interpretation: ~$0.01 per policy
- Explanation Generation: ~$0.01 per video (optional)

**Total Impact**: < 5% of total moderation cost

## Failure Handling

### Graceful Degradation

- All LLM features are optional
- Services continue to function if Azure OpenAI is unavailable
- Human reviewers can work without AI assistance
- Policy rules can be manually configured

### Error Handling

- LLM failures are logged but do not block operations
- Explanations default to "AI explanation unavailable"
- Suggestions are marked as unavailable if service is down
- All endpoints return appropriate HTTP status codes

## Testing

### Manual Testing

1. **Test Human Review Copilot**:
   ```bash
   # Get AI summary
   curl http://localhost:8004/review/{video_id}/summary
   
   # Get AI suggestion
   curl -X POST http://localhost:8004/review/{video_id}/suggest
   
   # Get multilingual explanation
   curl http://localhost:8004/review/{video_id}/explain?language=es
   ```

2. **Test Policy Interpretation**:
   ```bash
   curl -X POST http://localhost:8003/policy/interpret \
     -H "Content-Type: application/json" \
     -d '{
       "policy_text": "Apply stricter thresholds for minors in EU regions",
       "region": "EU"
     }'
   ```

3. **Test Deep Vision Explanation** (if enabled):
   ```bash
   curl -X POST http://localhost:8002/explain \
     -H "Content-Type: application/json" \
     -d '{"video_id": "test-video-id"}'
   ```

## Architecture Pattern

```
[ ML Inference Pipeline ]  →  [ Policy Engine ]
                                    ↓
                          [ LLM Assist Layer ] (Optional, Off-Critical-Path)
                                    ↓
                        [ Human Review + Audit ]
```

**Key Points**:
- LLM layer is downstream from ML inference
- LLM layer is off the critical path
- Failure does not block moderation
- Cost is bounded

## Migration Guide

### For Existing Deployments

1. **Update Environment Variables**:
   ```bash
   # Add to your deployment configs
   AZURE_OPENAI_ENABLED=true
   AZURE_OPENAI_API_KEY=<your-key>
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   AZURE_OPENAI_ENDPOINT=<your-endpoint>
   AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
   ```

2. **Update Requirements**:
   - Human Review: Already includes `openai==1.12.0`
   - Policy Engine: Already includes `openai==1.12.0`
   - Deep Vision: Already includes `openai==1.12.0` (optional)

3. **Deploy Updated Services**:
   ```bash
   # Rebuild and deploy
   bash scripts/build-services.sh
   kubectl apply -f k8s/cpu-services/
   kubectl apply -f k8s/gpu-services/
   ```

4. **Verify Integration**:
   - Check service health endpoints
   - Test new endpoints
   - Verify graceful degradation if Azure OpenAI is disabled

## CI/CD Setup for Azure OpenAI Integration

This section covers setting up Azure DevOps self-hosted agents for CI/CD pipelines that build and deploy services with Azure OpenAI integration.

### Phase: Setup Self-Hosted Agent (macOS/Linux)

#### Step 1: Verify/Create Default Agent Pool

1. Go to **Azure DevOps** → Your project (`guardian-ai-mlops`)
2. Click **Project Settings** (gear icon, bottom left)
3. Under **Pipelines**, click **"Agent pools"**
4. Verify **"Default"** pool exists (it should exist by default)
5. If it doesn't exist:
   - Click **"+ Add pool"**
   - Select **"Self-hosted"**
   - Name: `Default`
   - Click **"Create"**

**Note**: The pipeline YAML uses `pool: name: 'Default'`, so ensure this pool exists.

#### Step 2: Create Personal Access Token (PAT)

1. In Azure DevOps, click your profile (top right) → **"Personal access tokens"**
2. Click **"+ New Token"**
3. Fill in:
   - **Name**: `Self-hosted Agent Token` (or any descriptive name)
   - **Organization**: Select your organization
   - **Expiration**: Choose expiration (90 days recommended for learning)
   - **Scopes**: Select **"Full access"** (for learning) or **"Agent Pools (Read & manage)"** (more secure)
4. Click **"Create"**
5. **Important**: Copy the token immediately (you won't see it again)
   - Format: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Save it securely (you'll need it in Step 4)

#### Step 3: Download Agent Software

1. In Azure DevOps, go to **Project Settings** → **Agent pools**
2. Click on **"Default"** pool
3. Click **"New agent"**
4. Select your OS:
   - **macOS**: Download `vsts-agent-osx-x64-*.tar.gz` (or `vsts-agent-osx-arm64-*.tar.gz` for Apple Silicon)
   - **Linux**: Download `vsts-agent-linux-x64-*.tar.gz`
5. Extract the archive:
   ```bash
   # macOS
   cd ~/Downloads
   tar -xzf vsts-agent-osx-x64-*.tar.gz
   cd vsts-agent-osx-x64-*
   
   # Linux
   cd ~/Downloads
   tar -xzf vsts-agent-linux-x64-*.tar.gz
   cd vsts-agent-linux-x64-*
   ```

#### Step 4: Configure Agent (macOS - Gatekeeper Fix)

**Important for macOS**: macOS Gatekeeper may block the agent scripts. Fix this first:

```bash
# Navigate to agent directory
cd ~/Downloads/vsts-agent-osx-x64-*  # or vsts-agent-osx-arm64-* for Apple Silicon

# Remove quarantine attributes (allows scripts to run)
xattr -cr .
```

**Why this is needed**: macOS Gatekeeper blocks unsigned executables. This command removes the quarantine attribute so `./config.sh` and `./run.sh` can execute.

#### Step 5: Configure Agent

1. Run the configuration script:
   ```bash
   ./config.sh
   ```

2. When prompted, enter:
   - **Server URL**: `https://dev.azure.com/<your-org-name>`
     - Example: `https://dev.azure.com/surbhi0510`
     - **Important**: Use only the organization URL, NOT the project URL
   - **Authentication type**: `PAT` (Personal Access Token)
   - **Personal Access Token**: Paste the token from Step 2
   - **Agent pool**: `Default` (or press Enter for default)
   - **Agent name**: Your machine name (e.g., `Heeyaichens-Mac-mini`) or press Enter for auto-generated name
   - **Work folder**: Press Enter for default (`_work`)

3. Configuration completes successfully when you see:
   ```
   ✓ Successfully added the agent
   ```

#### Step 6: Run Agent

1. Start the agent:
   ```bash
   ./run.sh
   ```

2. You should see:
   ```
   Scanning for tool capabilities.
   Connecting to the server.
   Listening for Jobs
   ```

3. **Keep this terminal open** - the agent must stay running to pick up pipeline jobs.

4. **For other terminal tasks**: Open a new terminal window/tab (don't close the agent terminal).

#### Step 7: Verify Agent is Online

1. In Azure DevOps, go to **Project Settings** → **Agent pools** → **Default**
2. You should see your agent listed with status **"Online"** (green dot)
3. If it shows **"Offline"**:
   - Check the terminal where `./run.sh` is running for errors
   - Verify PAT token hasn't expired
   - Verify server URL is correct (organization only, no project path)

### Troubleshooting Agent Setup

#### Issue: "No agent found" when running pipeline
**Solution**:
- Verify agent pool name matches pipeline YAML (`Default`)
- Check agent is online in Azure DevOps
- Ensure `./run.sh` is running in a terminal

#### Issue: "xattr: command not found" (Linux)
**Solution**: The `xattr -cr .` command is macOS-specific. On Linux, skip Step 4.

#### Issue: Agent shows "Offline" but `./run.sh` is running
**Solution**:
- Check server URL is correct (organization only: `https://dev.azure.com/<org>`, not `https://dev.azure.com/<org>/<project>`)
- Verify PAT token is valid and has correct permissions
- Check network connectivity

#### Issue: Gatekeeper blocks scripts on macOS
**Solution**: Run `xattr -cr .` in the agent directory before `./config.sh`

### Next Steps

Once the agent is online:
1. Your pipelines will use this agent instead of Microsoft-hosted agents
2. The agent will run on your machine (Mac/Linux)
3. Ensure Docker is installed and accessible (for building images)
4. Ensure `docker buildx` is available (for multi-platform builds)

**Note**: For Apple Silicon Macs, consider using the ARM64 agent (`vsts-agent-osx-arm64-*.tar.gz`) to avoid X64 emulation warnings and improve performance.

## Best Practices

1. **Always mark AI suggestions as non-binding**
2. **Cache LLM responses to reduce costs**
3. **Use async patterns for non-critical features**
4. **Monitor LLM API usage and costs**
5. **Test graceful degradation scenarios**
6. **Document which features require LLM**

## Summary

✅ **Removed** Azure OpenAI from fast-screening (should not be on critical path)
✅ **Made optional** in deep-vision (off critical path, async)
✅ **Added** to human-review (primary use case - reviewer copilot)
✅ **Added** to policy-engine (enterprise feature - policy interpretation)
✅ **Updated** architecture documentation

**Result**: Clean, defensible architecture where LLMs assist but never decide.

---

**Last Updated**: 2024
**Status**: Production Ready
**LLM Integration**: Optional, Off-Critical-Path
