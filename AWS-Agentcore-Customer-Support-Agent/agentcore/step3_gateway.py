"""
Step 3: AgentCore Gateway & Identity

Creates an AgentCore Gateway with JWT (Cognito) authorization, registers a Lambda
tool target, then runs the agent using MCP tools served through the gateway.
"""
import os
import uuid

import boto3
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

from agentcore import AWS_REGION as REGION
from agentcore.utils import (
    get_or_create_cognito_pool,
    put_ssm_parameter,
    get_ssm_parameter,
    load_api_spec,
)
from agentcore.step1_agent import (
    SYSTEM_PROMPT, MODEL_ID,
    get_product_info, get_return_policy, get_technical_support,
)
from agentcore.step2_memory import CustomerSupportMemoryHooks, create_or_get_memory_resource, memory_client, ACTOR_ID

GATEWAY_NAME = "customersupport-gw"
API_SPEC_FILE = os.path.join(os.path.dirname(__file__), "..", "prerequisite", "lambda", "api_spec.json")


def create_or_get_gateway(cognito_config: dict) -> dict:
    """Create AgentCore Gateway with JWT authorizer or return existing one from SSM."""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [cognito_config["client_id"]],
            "discoveryUrl": cognito_config["discovery_url"],
        }
    }
    try:
        print(f"  Creating gateway '{GATEWAY_NAME}' in {REGION}...")
        resp = gateway_client.create_gateway(
            name=GATEWAY_NAME,
            roleArn=get_ssm_parameter("/app/customersupport/agentcore/gateway_iam_role"),
            protocolType="MCP",
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration=auth_config,
            description="Customer Support AgentCore Gateway",
        )
        gateway_id = resp["gatewayId"]
        put_ssm_parameter("/app/customersupport/agentcore/gateway_id", gateway_id)
        put_ssm_parameter("/app/customersupport/agentcore/gateway_name", GATEWAY_NAME)
        put_ssm_parameter("/app/customersupport/agentcore/gateway_arn", resp["gatewayArn"])
        put_ssm_parameter("/app/customersupport/agentcore/gateway_url", resp["gatewayUrl"])
        print(f"  Gateway created: {gateway_id}")
        return {"id": gateway_id, "name": GATEWAY_NAME, "gateway_url": resp["gatewayUrl"], "gateway_arn": resp["gatewayArn"]}
    except Exception:
        # Try SSM first; if missing, fall back to listing gateways by name
        try:
            existing_id = get_ssm_parameter("/app/customersupport/agentcore/gateway_id")
        except Exception:
            gateways = gateway_client.list_gateways().get("items", [])
            match = next((g for g in gateways if g["name"] == GATEWAY_NAME), None)
            if not match:
                raise RuntimeError(f"Gateway '{GATEWAY_NAME}' not found and could not be created.")
            existing_id = match["gatewayId"]
            put_ssm_parameter("/app/customersupport/agentcore/gateway_id", existing_id)
        print(f"  Found existing gateway: {existing_id}")
        gw = gateway_client.get_gateway(gatewayIdentifier=existing_id)
        # Update role + authorizer: the stored roleArn may be stale (CF stack replaced the role)
        current_role_arn = get_ssm_parameter("/app/customersupport/agentcore/gateway_iam_role")
        try:
            gateway_client.update_gateway(
                gatewayIdentifier=existing_id,
                name=gw["name"],
                roleArn=current_role_arn,
                protocolType=gw["protocolType"],
                authorizerType="CUSTOM_JWT",
                authorizerConfiguration=auth_config,
            )
            print(f"  Gateway role and authorizer updated.")
        except Exception as ue:
            print(f"  Gateway update skipped: {ue}")
        put_ssm_parameter("/app/customersupport/agentcore/gateway_id", existing_id)
        put_ssm_parameter("/app/customersupport/agentcore/gateway_name", gw["name"])
        put_ssm_parameter("/app/customersupport/agentcore/gateway_arn", gw["gatewayArn"])
        put_ssm_parameter("/app/customersupport/agentcore/gateway_url", gw["gatewayUrl"])
        return {"id": existing_id, "name": gw["name"], "gateway_url": gw["gatewayUrl"], "gateway_arn": gw["gatewayArn"]}


def create_gateway_target(gateway_id: str) -> None:
    """Register the Lambda tool target on the gateway, updating it if it already exists."""
    gateway_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    api_spec = load_api_spec(API_SPEC_FILE)
    lambda_arn = get_ssm_parameter("/app/customersupport/agentcore/lambda_arn")
    lambda_target_config = {
        "mcp": {
            "lambda": {
                "lambdaArn": lambda_arn,
                "toolSchema": {"inlinePayload": api_spec},
            }
        }
    }
    try:
        resp = gateway_client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name="LambdaUsingSDK",
            description="Lambda Target using SDK",
            targetConfiguration=lambda_target_config,
            credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
        )
        print(f"  Gateway target created: {resp['targetId']}")
    except gateway_client.exceptions.ConflictException:
        targets = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
        existing = next((t for t in targets if t["name"] == "LambdaUsingSDK"), None)
        if existing:
            gateway_client.update_gateway_target(
                gatewayIdentifier=gateway_id,
                targetId=existing["targetId"],
                name="LambdaUsingSDK",
                description="Lambda Target using SDK",
                targetConfiguration=lambda_target_config,
                credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
            )
            print(f"  Gateway target updated: {existing['targetId']} → Lambda ARN refreshed")
        else:
            print(f"  Gateway target conflict but could not find existing target to update")
    except Exception as e:
        print(f"  Gateway target error: {e}")


def build_gateway_agent(gateway_url: str, bearer_token: str, memory_id: str) -> Agent:
    mcp_client = MCPClient(
        lambda: streamablehttp_client(gateway_url, headers={"Authorization": f"Bearer {bearer_token}"})
    )
    session_id = str(uuid.uuid4())
    hooks = CustomerSupportMemoryHooks(memory_id, memory_client, ACTOR_ID, session_id)
    model = BedrockModel(model_id=MODEL_ID, temperature=0.3, region_name=REGION)

    with mcp_client:
        tools = [get_product_info, get_return_policy, get_technical_support] + mcp_client.list_tools_sync()
        return Agent(model=model, tools=tools, hooks=[hooks], system_prompt=SYSTEM_PROMPT)


def run() -> None:
    """Run Step 3: create gateway, register Lambda target, test agent via MCP."""
    print("\n=== Step 3: AgentCore Gateway & Identity ===")

    print("\n[Step 1/4] Setting up Cognito OAuth pool and obtaining bearer token...")
    cognito_config = get_or_create_cognito_pool(refresh_token=True)
    print(f"  Cognito client ID: {cognito_config['client_id']}")
    print(f"  Discovery URL: {cognito_config['discovery_url']}")

    print("\n[Step 2/4] Creating or retrieving AgentCore Gateway with JWT authorizer...")
    gateway = create_or_get_gateway(cognito_config)
    print(f"  Gateway URL: {gateway['gateway_url']}")

    print("\n[Step 3/4] Registering Lambda tool target on the gateway...")
    create_gateway_target(gateway["id"])

    print("\n[Step 4/4] Running agent via MCP gateway with sample queries...")
    memory_id = create_or_get_memory_resource()

    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            gateway["gateway_url"],
            headers={"Authorization": f"Bearer {cognito_config['bearer_token']}"},
        )
    )
    session_id = str(uuid.uuid4())
    hooks = CustomerSupportMemoryHooks(memory_id, memory_client, ACTOR_ID, session_id)
    model = BedrockModel(model_id=MODEL_ID, temperature=0.3, region_name=REGION)

    test_prompts = [
        "I have a Gaming Console Pro device, I want to check my warranty status. Serial number: MNO33333333.",
        "How can I fix a Lenovo ThinkPad with a blue screen?",
    ]

    with mcp_client:
        tools = [get_product_info, get_return_policy, get_technical_support] + mcp_client.list_tools_sync()
        agent = Agent(model=model, tools=tools, hooks=[hooks], system_prompt=SYSTEM_PROMPT)
        for i, prompt in enumerate(test_prompts, 1):
            print(f"\n  [Query {i}/{len(test_prompts)}] {prompt}")
            print("  " + "-" * 58)
            agent(prompt)

    print("\n=== Step 3 complete ===\n")
