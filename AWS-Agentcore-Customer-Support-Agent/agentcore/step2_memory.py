"""
Step 2: AgentCore Memory

Creates a managed memory resource with USER_PREFERENCE and SEMANTIC strategies,
seeds historical customer interactions, and attaches memory hooks to the agent.
"""
import logging
import time
import uuid

import boto3
from boto3.session import Session
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType
from strands import Agent
from strands.hooks import AfterInvocationEvent, HookProvider, HookRegistry, MessageAddedEvent
from strands.models import BedrockModel

from agentcore import AWS_REGION as REGION
from agentcore.utils import get_ssm_parameter, put_ssm_parameter
from agentcore.step1_agent import (
    SYSTEM_PROMPT, MODEL_ID,
    get_product_info, get_return_policy, web_search, get_technical_support,
)

logger = logging.getLogger(__name__)
ACTOR_ID = "customer_001"
SESSION_ID = str(uuid.uuid4())

memory_client = MemoryClient(region_name=REGION)


def create_or_get_memory_resource() -> str | None:
    """Create AgentCore Memory resource or return existing memory ID from SSM."""
    try:
        memory_id = get_ssm_parameter("/app/customersupport/agentcore/memory_id")
        memory_client.gmcp_client.get_memory(memoryId=memory_id)
        print("  Found existing memory resource.")
        return memory_id
    except Exception:
        pass

    try:
        strategies = [
            {
                StrategyType.USER_PREFERENCE.value: {
                    "name": "CustomerPreferences",
                    "description": "Captures customer preferences and behavior",
                    "namespaces": ["support/customer/{actorId}/preferences"],
                }
            },
            {
                StrategyType.SEMANTIC.value: {
                    "name": "CustomerSupportSemantic",
                    "description": "Stores facts from conversations",
                    "namespaces": ["support/customer/{actorId}/semantic"],
                }
            },
        ]
        print("  Creating AgentCore Memory resource (takes 2-3 minutes)...")
        response = memory_client.create_memory_and_wait(
            name="CustomerSupportMemory",
            description="Customer support agent memory",
            strategies=strategies,
            event_expiry_days=90,
        )
        memory_id = response["id"]
        put_ssm_parameter("/app/customersupport/agentcore/memory_id", memory_id)
        print(f"  Memory resource created: {memory_id}")
        return memory_id
    except Exception as e:
        print(f"  ERROR: Failed to create memory resource: {e}")
        return None


def seed_customer_history(memory_id: str, customer_id: str) -> None:
    """Seed the memory with historical customer interactions."""
    previous_interactions = [
        ("I'm having issues with my MacBook Pro overheating during video editing.", "USER"),
        ("I can help with that thermal issue. For video editing workloads, let's check your Activity Monitor and adjust performance settings. Your MacBook Pro order #MB-78432 is still under warranty.", "ASSISTANT"),
        ("What's the return policy on gaming headphones? I need low latency for competitive FPS games", "USER"),
        ("For gaming headphones, you have 30 days to return. Since you're into competitive FPS, I'd recommend checking the audio latency specs - most gaming models have <40ms latency.", "ASSISTANT"),
        ("I need a laptop under $1200 for programming. Prefer 16GB RAM minimum and good Linux compatibility. I like ThinkPad models.", "USER"),
        ("Perfect! For development work, I'd suggest looking at our ThinkPad E series or Dell XPS models. Both have excellent Linux support and 16GB RAM options within your budget.", "ASSISTANT"),
    ]
    memory_client.create_event(
        memory_id=memory_id,
        actor_id=customer_id,
        session_id="previous_session",
        messages=previous_interactions,
    )
    print("  Seeded 3 historical customer interactions.")


def wait_for_memory_processing(memory_id: str, customer_id: str, max_retries: int = 12) -> list:
    """Poll until LTM memories are processed (up to max_retries * 10 seconds)."""
    print("  Waiting for Long-Term Memory processing...")
    for attempt in range(1, max_retries + 1):
        memories = memory_client.retrieve_memories(
            memory_id=memory_id,
            namespace=f"support/customer/{customer_id}/preferences",
            query="customer support summary",
        )
        if memories:
            print(f"  LTM processing complete after ~{attempt * 10}s. Found {len(memories)} preference memories.")
            return memories
        print(f"  Still processing... (attempt {attempt}/{max_retries})")
        time.sleep(10)
    print("  WARNING: Memory processing taking longer than expected. Continuing anyway.")
    return []


class CustomerSupportMemoryHooks(HookProvider):
    """Memory hooks that inject customer context before queries and save interactions after."""

    def __init__(self, memory_id: str, client: MemoryClient, actor_id: str, session_id: str):
        self.memory_id = memory_id
        self.client = client
        self.actor_id = actor_id
        self.session_id = session_id
        self.namespaces = {
            i["type"]: i["namespaces"][0]
            for i in self.client.get_memory_strategies(self.memory_id)
        }

    @staticmethod
    def _resolve_pronouns(messages: list, user_query: str) -> str:
        """If the user message uses pronouns without naming a product, prepend the last named product."""
        import re
        pronouns = re.compile(r'\b(it|its|the device|my device|this product|this device)\b', re.IGNORECASE)
        product_pattern = re.compile(
            r'(Gaming Console Pro|Dell XPS\s*\d*|MacBook Pro|ThinkPad\w*|iPhone\s*\d*|'
            r'Samsung Galaxy\s*\w*|Smart TV\w*|Smartwatch\w*|Speaker\w*|Tablet\w*|'
            r'Headphones?\w*|Monitor\w*)',
            re.IGNORECASE,
        )
        if not pronouns.search(user_query):
            return user_query
        if product_pattern.search(user_query):
            return user_query
        last_product = None
        for msg in reversed(messages[:-1]):
            text = ""
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict) and "text" in block:
                        text += block["text"] + " "
            match = product_pattern.search(text)
            if match:
                last_product = match.group(0)
                break
        if last_product:
            return f"Regarding the {last_product}: {user_query}"
        return user_query

    def retrieve_customer_context(self, event: MessageAddedEvent) -> None:
        messages = event.agent.messages
        if messages[-1]["role"] == "user" and "toolResult" not in messages[-1]["content"][0]:
            user_query = messages[-1]["content"][0]["text"]
            user_query = self._resolve_pronouns(messages, user_query)
            messages[-1]["content"][0]["text"] = user_query
            try:
                all_context = []
                for context_type, namespace in self.namespaces.items():
                    memories = self.client.retrieve_memories(
                        memory_id=self.memory_id,
                        namespace=namespace.format(actorId=self.actor_id),
                        query=user_query,
                        top_k=1,
                    )
                    for memory in memories:
                        if isinstance(memory, dict):
                            text = memory.get("content", {}).get("text", "").strip()
                            if text:
                                all_context.append(f"[{context_type.upper()}] {text}")
                if all_context:
                    context_text = "\n".join(all_context)
                    messages[-1]["content"][0]["text"] = (
                        f"[BACKGROUND — IGNORE THIS SECTION, do not mention any product or device listed here]\n"
                        f"{context_text}\n"
                        f"[END BACKGROUND — IGNORE EVERYTHING ABOVE]\n\n"
                        f"[CURRENT QUESTION — answer ONLY this question about ONLY the product mentioned here]\n"
                        f"{user_query}"
                    )
            except Exception as e:
                logger.error(f"Failed to retrieve customer context: {e}")

    def save_support_interaction(self, event: AfterInvocationEvent) -> None:
        try:
            messages = event.agent.messages
            if len(messages) >= 2 and messages[-1]["role"] == "assistant":
                customer_query = None
                agent_response = None
                for msg in reversed(messages):
                    if msg["role"] == "assistant" and not agent_response:
                        agent_response = msg["content"][0]["text"]
                    elif msg["role"] == "user" and not customer_query and "toolResult" not in msg["content"][0]:
                        customer_query = msg["content"][0]["text"]
                        break
                if customer_query and agent_response:
                    self.client.create_event(
                        memory_id=self.memory_id,
                        actor_id=self.actor_id,
                        session_id=self.session_id,
                        messages=[(customer_query, "USER"), (agent_response, "ASSISTANT")],
                    )
        except Exception as e:
            logger.error(f"Failed to save support interaction: {e}")

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(MessageAddedEvent, self.retrieve_customer_context)
        registry.add_callback(AfterInvocationEvent, self.save_support_interaction)


def build_memory_agent(memory_id: str, customer_id: str, session_id: str) -> Agent:
    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
    hooks = CustomerSupportMemoryHooks(memory_id, memory_client, customer_id, session_id)
    return Agent(
        model=model,
        hooks=[hooks],
        tools=[get_product_info, get_return_policy, web_search, get_technical_support],
        system_prompt=SYSTEM_PROMPT,
    )


def run() -> None:
    """Run Step 2: create memory, seed history, and demonstrate personalized recall."""
    print("\n=== Step 2: AgentCore Memory ===")

    print("\n[Step 1/4] Creating or retrieving AgentCore Memory resource...")
    memory_id = create_or_get_memory_resource()
    if not memory_id:
        raise RuntimeError("Memory resource could not be created.")
    print(f"  Memory ID: {memory_id}")

    print("\n[Step 2/4] Seeding customer interaction history...")
    seed_customer_history(memory_id, ACTOR_ID)

    print("\n[Step 3/4] Waiting for Long-Term Memory (LTM) extraction to complete...")
    wait_for_memory_processing(memory_id, ACTOR_ID)

    print("\n[Step 4/4] Running agent with memory hooks to demonstrate personalized recall...")
    session_id = str(uuid.uuid4())
    agent = build_memory_agent(memory_id, ACTOR_ID, session_id)

    print("\n> Which headphones would you recommend?")
    print("-" * 60)
    agent("Which headphones would you recommend?")

    print("\n> What is my preferred laptop brand and requirements?")
    print("-" * 60)
    agent("What is my preferred laptop brand and requirements?")

    print("\n=== Step 2 complete ===\n")
