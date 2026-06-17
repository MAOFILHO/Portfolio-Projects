import boto3
from bedrock_agentcore.runtime import (
    BedrockAgentCoreApp,
)  # ### AGENTCORE RUNTIME - LINE 1 ####
from agentcore.step1_agent import (
    MODEL_ID,
    SYSTEM_PROMPT,
    get_product_info,
    get_return_policy,
    get_technical_support,
    web_search,
)
from agentcore.step2_memory import (
    ACTOR_ID,
    SESSION_ID,
    CustomerSupportMemoryHooks,
    memory_client,
)
from agentcore.utils import get_ssm_parameter
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# Initialize boto3 client
sts_client = boto3.client("sts")

# Get AWS account details
REGION = boto3.session.Session().region_name

# Step 1: Create the Bedrock model
model = BedrockModel(model_id=MODEL_ID)

# Load memory ID once at startup
memory_id = get_ssm_parameter("/app/customersupport/agentcore/memory_id")

# Initialize the AgentCore Runtime App
app = BedrockAgentCoreApp()  #### AGENTCORE RUNTIME - LINE 2 ####


@app.entrypoint  #### AGENTCORE RUNTIME - LINE 3 ####
async def invoke(payload, context=None):
    """AgentCore Runtime entrypoint function"""
    user_input = payload.get("prompt", "")
    history = payload.get("history", [])

    # Access request headers - handle None case
    request_headers = context.request_headers or {}

    # Per-request actor_id and session_id — keeps each user's memory isolated
    actor_id = payload.get("actor_id", ACTOR_ID)
    session_id = request_headers.get(
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id", SESSION_ID
    )
    memory_hooks = CustomerSupportMemoryHooks(
        memory_id, memory_client, actor_id, session_id
    )

    # Get Client JWT token
    auth_header = request_headers.get("Authorization", "")

    print(f"Authorization header: {auth_header}")
    # Get Gateway ID
    existing_gateway_id = get_ssm_parameter("/app/customersupport/agentcore/gateway_id")

    # Initialize Bedrock AgentCore Control client
    gateway_client = boto3.client(
        "bedrock-agentcore-control",
        region_name=REGION,
    )
    # Get existing gateway details
    gateway_response = gateway_client.get_gateway(gatewayIdentifier=existing_gateway_id)

    # Get gateway url
    gateway_url = gateway_response["gatewayUrl"]

    # Create MCP client and agent within context manager if JWT token available
    if gateway_url and auth_header:
        try:
            mcp_client = MCPClient(
                lambda: streamablehttp_client(
                    url=gateway_url, headers={"Authorization": auth_header}
                )
            )

            with mcp_client:
                # tools = mcp_client.list_tools_sync()
                tools = [
                    get_product_info,
                    get_return_policy,
                    get_technical_support,
                    web_search,
                ] + mcp_client.list_tools_sync()

                # Create the agent with per-request memory hooks
                agent = Agent(
                    model=model,
                    tools=tools,
                    system_prompt=SYSTEM_PROMPT,
                    hooks=[memory_hooks],
                )
                # Load conversation history so the agent has context from prior turns
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    agent.messages.append({
                        "role": role,
                        "content": [{"text": content}],
                    })
                # Invoke the agent
                response = agent(user_input)
                return response.message["content"][0]["text"]
        except Exception as e:
            print(f"MCP client error: {str(e)}")
            return f"Error: {str(e)}"
    else:
        return "Error: Missing gateway URL or authorization header"


if __name__ == "__main__":
    app.run()  #### AGENTCORE RUNTIME - LINE 4 ####
