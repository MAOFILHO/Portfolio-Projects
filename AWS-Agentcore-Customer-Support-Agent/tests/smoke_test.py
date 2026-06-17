"""
End-to-end smoke test — system health check for the full AgentCore pipeline.

Covers all 7 layers of the stack:
  1. AWS Infrastructure  (SSM, S3, DynamoDB, Lambda, IAM)
  2. Bedrock Knowledge Base  (KB status, data source, ingestion)
  3. Cognito Auth  (pool, client, bearer token)
  4. AgentCore Gateway  (gateway + Lambda target)
  5. AgentCore Memory  (memory resource)
  6. AgentCore Runtime  (endpoint status + invocations)
  7. End-to-end agent flows  (each tool + multi-turn memory)

Run after completing all steps:
  make smoke
"""
import os
import sys
import uuid

import boto3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REGION = "us-east-1"


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def account_id():
    return boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]


@pytest.fixture(scope="module")
def ssm():
    return boto3.client("ssm", region_name=REGION)


@pytest.fixture(scope="module")
def runtime_and_token():
    """Configure the AgentCore Runtime toolkit and obtain a fresh bearer token."""
    from agentcore.utils import get_or_create_cognito_pool, get_ssm_parameter, create_agentcore_runtime_execution_role
    from agentcore.step4_runtime import configure_runtime

    try:
        get_ssm_parameter("/app/customersupport/agentcore/runtime_arn")
    except Exception:
        pytest.skip("Runtime ARN not in SSM — run Step 4 first.")

    cognito_config = get_or_create_cognito_pool(refresh_token=True)
    execution_role_arn = create_agentcore_runtime_execution_role()
    runtime = configure_runtime(execution_role_arn, cognito_config)
    return runtime, cognito_config["bearer_token"]


# ══════════════════════════════════════════════════════════════════════════════
# 1. AWS INFRASTRUCTURE
# ══════════════════════════════════════════════════════════════════════════════

class TestInfrastructure:
    """Verify all CloudFormation-provisioned resources exist and are reachable."""

    REQUIRED_SSM = [
        "/app/customersupport/agentcore/gateway_iam_role",
        "/app/customersupport/agentcore/runtime_iam_role",
        "/app/customersupport/agentcore/lambda_arn",
        "/app/customersupport/dynamodb/warranty_table_name",
        "/app/customersupport/dynamodb/customer_profile_table_name",
    ]

    def test_ssm_parameters_exist(self, ssm):
        """All CF-provisioned SSM parameters must be present."""
        missing = []
        for name in self.REQUIRED_SSM:
            try:
                ssm.get_parameter(Name=name)
            except ssm.exceptions.ParameterNotFound:
                missing.append(name)
        assert not missing, f"Missing SSM parameters: {missing}"

    def test_kb_ssm_parameters_exist(self, ssm, account_id):
        """Knowledge Base SSM parameters written by the custom resource Lambda."""
        for name in [
            f"/{account_id}-{REGION}/kb/knowledge-base-id",
            f"/{account_id}-{REGION}/kb/data-source-id",
        ]:
            val = ssm.get_parameter(Name=name)["Parameter"]["Value"]
            assert val, f"SSM parameter {name} is empty"

    def test_s3_data_bucket_has_documents(self, account_id):
        """KB data bucket must exist and contain at least 1 document."""
        s3 = boto3.client("s3", region_name=REGION)
        bucket = f"{account_id}-{REGION}-kb-data-bucket"
        resp = s3.list_objects_v2(Bucket=bucket)
        count = resp.get("KeyCount", 0)
        assert count > 0, f"S3 bucket '{bucket}' is empty — no documents uploaded"

    def test_dynamodb_warranty_table(self, ssm):
        """Warranty DynamoDB table must exist and be ACTIVE."""
        table_name = ssm.get_parameter(
            Name="/app/customersupport/dynamodb/warranty_table_name"
        )["Parameter"]["Value"]
        ddb = boto3.client("dynamodb", region_name=REGION)
        resp = ddb.describe_table(TableName=table_name)
        status = resp["Table"]["TableStatus"]
        assert status == "ACTIVE", f"Warranty table status: {status}"

    def test_dynamodb_customer_profile_table(self, ssm):
        """Customer profile DynamoDB table must exist and be ACTIVE."""
        table_name = ssm.get_parameter(
            Name="/app/customersupport/dynamodb/customer_profile_table_name"
        )["Parameter"]["Value"]
        ddb = boto3.client("dynamodb", region_name=REGION)
        resp = ddb.describe_table(TableName=table_name)
        status = resp["Table"]["TableStatus"]
        assert status == "ACTIVE", f"Customer profile table status: {status}"

    def test_lambda_function_active(self, ssm):
        """Customer support Lambda must exist and be Active."""
        lambda_arn = ssm.get_parameter(
            Name="/app/customersupport/agentcore/lambda_arn"
        )["Parameter"]["Value"]
        fn_name = lambda_arn.split(":")[-1]
        lam = boto3.client("lambda", region_name=REGION)
        resp = lam.get_function(FunctionName=fn_name)
        state = resp["Configuration"]["State"]
        assert state == "Active", f"Lambda state: {state}"


# ══════════════════════════════════════════════════════════════════════════════
# 2. BEDROCK KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeBase:
    """Verify the Bedrock KB is ACTIVE and the data source is healthy."""

    def test_kb_is_active(self, ssm, account_id):
        kb_id = ssm.get_parameter(
            Name=f"/{account_id}-{REGION}/kb/knowledge-base-id"
        )["Parameter"]["Value"]
        bedrock = boto3.client("bedrock-agent", region_name=REGION)
        kb = bedrock.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]
        assert kb["status"] == "ACTIVE", f"KB status: {kb['status']}"

    def test_data_source_exists(self, ssm, account_id):
        kb_id = ssm.get_parameter(
            Name=f"/{account_id}-{REGION}/kb/knowledge-base-id"
        )["Parameter"]["Value"]
        ds_id = ssm.get_parameter(
            Name=f"/{account_id}-{REGION}/kb/data-source-id"
        )["Parameter"]["Value"]
        bedrock = boto3.client("bedrock-agent", region_name=REGION)
        ds = bedrock.get_data_source(knowledgeBaseId=kb_id, dataSourceId=ds_id)["dataSource"]
        assert ds["status"] == "AVAILABLE", f"Data source status: {ds['status']}"

    def test_kb_retrieval_returns_results(self, ssm, account_id):
        """A semantic query against the KB must return at least 1 result."""
        kb_id = ssm.get_parameter(
            Name=f"/{account_id}-{REGION}/kb/knowledge-base-id"
        )["Parameter"]["Value"]
        bedrock_rt = boto3.client("bedrock-agent-runtime", region_name=REGION)
        resp = bedrock_rt.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": "laptop overheating"},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
        )
        results = resp.get("retrievalResults", [])
        assert len(results) > 0, "KB retrieve returned 0 results — sync may be needed"


# ══════════════════════════════════════════════════════════════════════════════
# 3. COGNITO AUTH
# ══════════════════════════════════════════════════════════════════════════════

class TestCognitoAuth:
    """Verify the Cognito user pool, test user, and token issuance."""

    def test_cognito_pool_exists(self):
        from agentcore.utils import get_customer_support_secret
        import json
        secret = json.loads(get_customer_support_secret())
        pool_id = secret.get("pool_id", "")
        assert pool_id.startswith("us-east-1_"), f"Unexpected pool_id: {pool_id}"
        cognito = boto3.client("cognito-idp", region_name=REGION)
        resp = cognito.describe_user_pool(UserPoolId=pool_id)
        assert resp["UserPool"]["Id"] == pool_id

    def test_testuser_exists_and_confirmed(self):
        from agentcore.utils import get_customer_support_secret
        import json
        secret = json.loads(get_customer_support_secret())
        pool_id = secret["pool_id"]
        cognito = boto3.client("cognito-idp", region_name=REGION)
        user = cognito.admin_get_user(UserPoolId=pool_id, Username="testuser")
        assert user["UserStatus"] == "CONFIRMED", f"testuser status: {user['UserStatus']}"

    def test_bearer_token_obtained(self):
        from agentcore.utils import get_or_create_cognito_pool
        config = get_or_create_cognito_pool(refresh_token=True)
        token = config.get("bearer_token", "")
        assert len(token) > 100, "Bearer token too short or missing"


# ══════════════════════════════════════════════════════════════════════════════
# 4. AGENTCORE GATEWAY
# ══════════════════════════════════════════════════════════════════════════════

class TestGateway:
    """Verify the AgentCore Gateway and its Lambda target are READY."""

    def test_gateway_is_ready(self, ssm):
        try:
            gateway_id = ssm.get_parameter(
                Name="/app/customersupport/agentcore/gateway_id"
            )["Parameter"]["Value"]
        except Exception:
            pytest.skip("Gateway ID not in SSM — run Step 3 first.")
        gw = boto3.client("bedrock-agentcore-control", region_name=REGION)
        resp = gw.get_gateway(gatewayIdentifier=gateway_id)
        assert resp["status"] == "READY", f"Gateway status: {resp['status']}"

    def test_gateway_has_target(self, ssm):
        try:
            gateway_id = ssm.get_parameter(
                Name="/app/customersupport/agentcore/gateway_id"
            )["Parameter"]["Value"]
        except Exception:
            pytest.skip("Gateway ID not in SSM — run Step 3 first.")
        gw = boto3.client("bedrock-agentcore-control", region_name=REGION)
        targets = gw.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
        ready = [t for t in targets if t.get("status") == "READY"]
        assert len(ready) > 0, f"No READY targets on gateway. Targets: {targets}"


# ══════════════════════════════════════════════════════════════════════════════
# 5. AGENTCORE MEMORY
# ══════════════════════════════════════════════════════════════════════════════

class TestMemory:
    """Verify the AgentCore Memory resource is available."""

    def test_memory_resource_exists(self, ssm):
        try:
            memory_id = ssm.get_parameter(
                Name="/app/customersupport/agentcore/memory_id"
            )["Parameter"]["Value"]
        except Exception:
            pytest.skip("Memory ID not in SSM — run Step 2 first.")
        from bedrock_agentcore.memory import MemoryClient
        client = MemoryClient(region_name=REGION)
        resp = client.gmcp_client.get_memory(memoryId=memory_id)
        # Response shape: {'memory': {'id': ..., 'name': ..., ...}, 'ResponseMetadata': ...}
        memory_obj = resp.get("memory", resp)
        assert memory_obj.get("id") == memory_id, \
            f"Memory id mismatch or not found. Response keys: {list(resp.keys())}"


# ══════════════════════════════════════════════════════════════════════════════
# 6. AGENTCORE RUNTIME
# ══════════════════════════════════════════════════════════════════════════════

class TestRuntime:
    """Verify the Runtime endpoint is READY and responds to invocations."""

    def test_runtime_is_ready(self, runtime_and_token):
        runtime, _ = runtime_and_token
        status = runtime.status()
        assert status.endpoint is not None, "Runtime endpoint is None"
        assert status.endpoint.get("status") == "READY", \
            f"Runtime status: {status.endpoint.get('status')}"

    def test_runtime_arn_in_ssm(self, ssm):
        arn = ssm.get_parameter(
            Name="/app/customersupport/agentcore/runtime_arn"
        )["Parameter"]["Value"]
        assert "bedrock-agentcore" in arn and "runtime" in arn, \
            f"Unexpected runtime ARN format: {arn}"

    def test_basic_invocation(self, runtime_and_token):
        runtime, token = runtime_and_token
        response = runtime.invoke(
            {"prompt": "List all of your tools"},
            bearer_token=token,
            session_id=str(uuid.uuid4()),
        )
        assert len(response.get("response", "")) > 0, "Empty response from runtime"


# ══════════════════════════════════════════════════════════════════════════════
# 7. END-TO-END AGENT FLOWS
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentFlows:
    """Verify each tool and memory work correctly through the live runtime."""

    def test_return_policy_tool(self, runtime_and_token):
        """Agent should use get_return_policy and mention the return window."""
        runtime, token = runtime_and_token
        resp = runtime.invoke(
            {"prompt": "What is the return policy for laptops?"},
            bearer_token=token,
            session_id=str(uuid.uuid4()),
        )
        text = resp.get("response", "").lower()
        assert any(kw in text for kw in ["30 day", "return", "policy"]), \
            f"Return policy not in response: {text[:200]}"

    def test_product_info_tool(self, runtime_and_token):
        """Agent should use get_product_info and return specs."""
        runtime, token = runtime_and_token
        resp = runtime.invoke(
            {"prompt": "What are the specs and warranty for headphones?"},
            bearer_token=token,
            session_id=str(uuid.uuid4()),
        )
        text = resp.get("response", "").lower()
        assert any(kw in text for kw in ["headphone", "warranty", "bluetooth", "noise"]), \
            f"Product info not in response: {text[:200]}"

    def test_knowledge_base_tool(self, runtime_and_token):
        """Agent should retrieve from the KB for technical support questions."""
        runtime, token = runtime_and_token
        resp = runtime.invoke(
            {"prompt": "My laptop won't turn on. What should I check first?"},
            bearer_token=token,
            session_id=str(uuid.uuid4()),
        )
        text = resp.get("response", "")
        assert len(text) > 50, f"KB tool response too short: {text}"

    def test_web_search_tool(self, runtime_and_token):
        """Agent should call web_search for current pricing questions."""
        runtime, token = runtime_and_token
        resp = runtime.invoke(
            {"prompt": "What is the current price of Samsung OLED monitors?"},
            bearer_token=token,
            session_id=str(uuid.uuid4()),
        )
        text = resp.get("response", "")
        assert len(text) > 50, f"Web search response too short: {text}"

    def test_warranty_check(self, runtime_and_token):
        """Agent should handle a warranty status check."""
        runtime, token = runtime_and_token
        resp = runtime.invoke(
            {"prompt": "Check warranty status for serial number MNO33333333"},
            bearer_token=token,
            session_id=str(uuid.uuid4()),
        )
        text = resp.get("response", "")
        assert len(text) > 10, f"Warranty check response too short: {text}"

    def test_multi_turn_session_memory(self, runtime_and_token):
        """Two back-to-back invocations with the same session_id and actor_id.

        The first turn seeds context about a ThinkPad; the second turn asks about
        it. The AgentCore Memory hooks retrieve prior context via the actor_id
        namespace, so the second response must reference the laptop brand.
        """
        runtime, token = runtime_and_token
        # Use customer_001 — seeded with ThinkPad history in Step 2
        actor_id = "customer_001"
        session_id = str(uuid.uuid4())

        runtime.invoke(
            {"prompt": "My name is Alex and I have a ThinkPad X1 Carbon.", "actor_id": actor_id},
            bearer_token=token,
            session_id=session_id,
        )
        resp = runtime.invoke(
            {"prompt": "What laptop brand did I just mention?", "actor_id": actor_id},
            bearer_token=token,
            session_id=session_id,
        )
        text = resp.get("response", "").lower()
        # Accept ThinkPad, Lenovo, or X1 Carbon as valid context recall signals
        assert any(kw in text for kw in ["thinkpad", "lenovo", "x1 carbon"]), \
            f"Session context not maintained. Response: {text[:300]}"
