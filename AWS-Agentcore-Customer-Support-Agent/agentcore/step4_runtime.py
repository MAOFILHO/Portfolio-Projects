"""
Step 4: AgentCore Runtime Deployment

Configures and launches the agent to AgentCore Runtime using the starter toolkit,
polls until the endpoint is READY, then runs test invocations.
"""
import os
import time
import uuid

import boto3
from bedrock_agentcore_starter_toolkit import Runtime

from agentcore import AWS_REGION as REGION
from agentcore.utils import (
    get_or_create_cognito_pool,
    create_agentcore_runtime_execution_role,
    get_ssm_parameter,
    put_ssm_parameter,
)

ENTRYPOINT = os.path.join(os.path.dirname(__file__), "..", "runtime", "agent_entrypoint.py")
REQUIREMENTS_FILE = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")


def configure_runtime(execution_role_arn: str, cognito_config: dict) -> Runtime:
    """Configure the AgentCore Runtime with container build settings."""
    runtime = Runtime()
    runtime.configure(
        entrypoint=ENTRYPOINT,
        execution_role=execution_role_arn,
        auto_create_ecr=True,
        requirements_file=REQUIREMENTS_FILE,
        region=REGION,
        agent_name="customer_support_agent",
        authorizer_configuration={
            "customJWTAuthorizer": {
                "allowedClients": [cognito_config["client_id"]],
                "discoveryUrl": cognito_config["discovery_url"],
            }
        },
        request_header_configuration={
            "requestHeaderAllowlist": [
                "Authorization",
                "X-Amzn-Bedrock-AgentCore-Runtime-Custom-H1",
            ]
        },
    )
    return runtime


def launch_and_wait(runtime: Runtime, force_rebuild: bool = False) -> str:
    """Launch the runtime container (triggers CodeBuild + ECR + deployment) and wait until READY."""
    status_resp = runtime.status()
    should_launch = force_rebuild or status_resp.endpoint is None
    if should_launch:
        print("  Launching agent runtime (CodeBuild ARM64 build → ECR push → deployment)...")
        launch_result = runtime.launch()
        agent_arn = launch_result.agent_arn
        put_ssm_parameter("/app/customersupport/agentcore/runtime_arn", agent_arn)
        print(f"  Launch initiated. Agent ARN: {agent_arn}")
    else:
        agent_arn = status_resp.endpoint.get("agentRuntimeArn", "")
        print(f"  Runtime already deployed. ARN: {agent_arn}")

    end_statuses = {"READY", "CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"}
    print("  Polling deployment status...")
    while True:
        status_resp = runtime.status()
        status = status_resp.endpoint["status"] if status_resp.endpoint else "UNKNOWN"
        if status in end_statuses:
            break
        print(f"    Current status: {status} — waiting 15s...")
        time.sleep(15)

    if status != "READY":
        raise RuntimeError(f"Runtime deployment failed with status: {status}")
    print(f"  Deployment READY.")
    return agent_arn


def run_test_invocations(runtime: Runtime, bearer_token: str) -> None:
    """Run several test queries against the live runtime endpoint."""
    session1 = str(uuid.uuid4())
    session2 = str(uuid.uuid4())

    queries = [
        ("List all of your tools", session1),
        ("Tell me detailed information about the technical documentation on installing a new CPU", session1),
        ("I have a Gaming Console Pro device, I want to check my warranty status. Serial number: MNO33333333.", session2),
    ]

    for i, (query, session_id) in enumerate(queries, 1):
        print(f"\n  [Invocation {i}/{len(queries)}] Session: {session_id[:8]}...")
        print(f"  Query: {query}")
        print("  " + "-" * 58)
        response = runtime.invoke(
            {"prompt": query},
            bearer_token=bearer_token,
            session_id=session_id,
        )
        print(response.get("response", ""))


def run() -> None:
    """Run Step 4: deploy agent to AgentCore Runtime and invoke it."""
    print("\n=== Step 4: AgentCore Runtime Deployment ===")

    print("\n[Step 1/5] Ensuring memory resource exists (required by runtime entrypoint)...")
    from agentcore.step2_memory import create_or_get_memory_resource
    memory_id = create_or_get_memory_resource()
    print(f"  Memory ID: {memory_id}")

    print("\n[Step 2/5] Creating AgentCore Runtime IAM execution role...")
    execution_role_arn = create_agentcore_runtime_execution_role()
    print(f"  Execution role ARN: {execution_role_arn}")

    print("\n[Step 3/5] Obtaining Cognito OAuth token for authorizer configuration...")
    cognito_config = get_or_create_cognito_pool(refresh_token=True)
    print(f"  Bearer token obtained (expires in ~3600s).")

    print("\n[Step 4/5] Configuring and launching AgentCore Runtime...")
    print("  This triggers: Dockerfile generation → CodeBuild ARM64 build → ECR push → Runtime deployment")
    runtime = configure_runtime(execution_role_arn, cognito_config)
    agent_arn = launch_and_wait(runtime, force_rebuild=True)

    print("\n[Step 5/5] Running test invocations against the live endpoint...")
    run_test_invocations(runtime, cognito_config["bearer_token"])

    print("\n=== Step 4 complete ===\n")
    print(f"  Agent ARN saved to SSM: /app/customersupport/agentcore/runtime_arn")
    print(f"  Agent ARN: {agent_arn}")
