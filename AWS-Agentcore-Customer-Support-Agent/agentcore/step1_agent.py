"""
Step 1: Customer Support Agent Prototype

Creates 4 tools (return policy, product info, web search, technical support),
syncs the Bedrock Knowledge Base, then runs the agent against sample queries.
"""
import time
import boto3
from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException
from strands import Agent
from strands.models import BedrockModel
from strands.tools import tool
from strands_tools import retrieve

from agentcore import AWS_REGION
from agentcore.utils import get_ssm_parameter

MODEL_ID = "us.amazon.nova-pro-v1:0"

SYSTEM_PROMPT = """You are a helpful customer support assistant for an electronics company.

ABSOLUTE RULES — YOU MUST FOLLOW THESE:

1. ONLY talk about the ONE product the customer is asking about RIGHT NOW.
2. NEVER mention other products the customer owns or asked about before.
3. NEVER say "Since you also mentioned..." or "Regarding your other device..." or "You also own..."
4. When the customer says "it", "my device", or "this product", find the LAST product mentioned BY NAME in the conversation. That is what "it" means. Example: if messages mention "Dell XPS", then "Gaming Console Pro", then "it" — "it" = Gaming Console Pro, NOT Dell XPS.
5. Messages may start with [BACKGROUND]. IGNORE that section completely. ONLY answer what comes after [CURRENT QUESTION].
6. Do NOT mix information from [BACKGROUND] into your answer.
7. Keep responses focused and concise.

TOOLS:
- get_return_policy() — warranty and return policy
- get_product_info() — product specifications
- web_search() — current prices, reviews, availability
- get_technical_support() — troubleshooting, setup guides, maintenance

Always use tools for accurate information. Do not guess product specs.

REMEMBER: Only discuss the ONE product the customer is currently asking about. Nothing else."""


@tool
def get_return_policy(product_category: str) -> str:
    """
    Get return policy information for a specific product category.

    Args:
        product_category: Electronics category (e.g., 'smartphones', 'laptops', 'accessories')

    Returns:
        Formatted return policy details including timeframes and conditions
    """
    return_policies = {
        "smartphones": {
            "window": "30 days",
            "condition": "Original packaging, no physical damage, factory reset required",
            "process": "Online RMA portal or technical support",
            "refund_time": "5-7 business days after inspection",
            "shipping": "Free return shipping, prepaid label provided",
            "warranty": "1-year manufacturer warranty included",
        },
        "laptops": {
            "window": "30 days",
            "condition": "Original packaging, all accessories, no software modifications",
            "process": "Technical support verification required before return",
            "refund_time": "7-10 business days after inspection",
            "shipping": "Free return shipping with original packaging",
            "warranty": "1-year manufacturer warranty, extended options available",
        },
        "accessories": {
            "window": "30 days",
            "condition": "Unopened packaging preferred, all components included",
            "process": "Online return portal",
            "refund_time": "3-5 business days after receipt",
            "shipping": "Customer pays return shipping under $50",
            "warranty": "90-day manufacturer warranty",
        },
    }
    default_policy = {
        "window": "30 days",
        "condition": "Original condition with all included components",
        "process": "Contact technical support",
        "refund_time": "5-7 business days after inspection",
        "shipping": "Return shipping policies vary",
        "warranty": "Standard manufacturer warranty applies",
    }
    policy = return_policies.get(product_category.lower(), default_policy)
    return (
        f"Return Policy - {product_category.title()}:\n\n"
        f"• Return window: {policy['window']} from delivery\n"
        f"• Condition: {policy['condition']}\n"
        f"• Process: {policy['process']}\n"
        f"• Refund timeline: {policy['refund_time']}\n"
        f"• Shipping: {policy['shipping']}\n"
        f"• Warranty: {policy['warranty']}"
    )


@tool
def get_product_info(product_type: str) -> str:
    """
    Get detailed technical specifications and information for electronics products.

    Args:
        product_type: Electronics product type (e.g., 'laptops', 'smartphones', 'headphones', 'monitors', 'gaming consoles', 'tablets', 'smart tvs', 'speakers', 'smartwatches')
    Returns:
        Formatted product information including warranty, features, and policies
    """
    products = {
        "laptops": {
            "warranty": "1-year manufacturer warranty + optional extended coverage",
            "specs": "Intel/AMD processors, 8-32GB RAM, SSD storage, various display sizes",
            "features": "Backlit keyboards, USB-C/Thunderbolt, Wi-Fi 6, Bluetooth 5.0",
            "compatibility": "Windows 11, macOS, Linux support varies by model",
            "support": "Technical support and driver updates included",
        },
        "smartphones": {
            "warranty": "1-year manufacturer warranty",
            "specs": "5G/4G connectivity, 128GB-1TB storage, multiple camera systems",
            "features": "Wireless charging, water resistance, biometric security",
            "compatibility": "iOS/Android, carrier unlocked options available",
            "support": "Software updates and technical support included",
        },
        "headphones": {
            "warranty": "1-year manufacturer warranty",
            "specs": "Wired/wireless options, noise cancellation, 20Hz-20kHz frequency",
            "features": "Active noise cancellation, touch controls, voice assistant",
            "compatibility": "Bluetooth 5.0+, 3.5mm jack, USB-C charging",
            "support": "Firmware updates via companion app",
        },
        "monitors": {
            "warranty": "3-year manufacturer warranty",
            "specs": "4K/1440p/1080p resolutions, IPS/OLED panels, various sizes",
            "features": "HDR support, high refresh rates, adjustable stands",
            "compatibility": "HDMI, DisplayPort, USB-C inputs",
            "support": "Color calibration and technical support",
        },
        "gaming consoles": {
            "warranty": "1-year manufacturer warranty + optional gaming warranty",
            "specs": "Next-gen octa-core processor, 16GB GDDR6 RAM, 1TB SSD, ray tracing GPU",
            "features": "4K gaming at 120fps, backward compatibility, haptic feedback controllers",
            "compatibility": "HDMI 2.1, Wi-Fi 6, Bluetooth 5.2, USB-C, expandable storage",
            "support": "Online multiplayer support, firmware updates, dedicated gaming support line",
        },
        "tablets": {
            "warranty": "1-year manufacturer warranty",
            "specs": "10-13 inch displays, 64GB-1TB storage, Apple M-series/Snapdragon processors",
            "features": "Stylus support, split-screen multitasking, cellular options",
            "compatibility": "iPadOS/Android, keyboard and stylus accessories",
            "support": "Software updates and technical support included",
        },
        "smart tvs": {
            "warranty": "2-year manufacturer warranty + optional extended coverage",
            "specs": "43-85 inch OLED/QLED panels, 4K/8K resolution, 120Hz refresh rate",
            "features": "Built-in streaming apps, voice control, screen mirroring, Dolby Atmos",
            "compatibility": "HDMI 2.1, Wi-Fi 6, Bluetooth 5.0, USB, Ethernet",
            "support": "Firmware updates, smart home integration support",
        },
        "speakers": {
            "warranty": "1-year manufacturer warranty + optional audio warranty",
            "specs": "Bluetooth 5.2, 20W-100W output, waterproof ratings up to IPX7",
            "features": "360-degree sound, multi-room pairing, voice assistant built-in",
            "compatibility": "Bluetooth, Wi-Fi, AUX 3.5mm, USB-C charging",
            "support": "Firmware updates via companion app, dedicated audio support",
        },
        "smartwatches": {
            "warranty": "1-year manufacturer warranty",
            "specs": "AMOLED displays, heart rate/SpO2 sensors, GPS, 5ATM water resistance",
            "features": "Fitness tracking, sleep monitoring, contactless payments, app ecosystem",
            "compatibility": "iOS/Android companion apps, Bluetooth 5.0, Wi-Fi",
            "support": "Software updates and health feature support included",
        },
    }
    product = products.get(product_type.lower())
    if not product:
        return f"Technical specifications for {product_type} not available. Please contact our technical support team for detailed product information and compatibility requirements."
    return (
        f"Technical Information - {product_type.title()}:\n\n"
        f"• Warranty: {product['warranty']}\n"
        f"• Specifications: {product['specs']}\n"
        f"• Key Features: {product['features']}\n"
        f"• Compatibility: {product['compatibility']}\n"
        f"• Support: {product['support']}"
    )


@tool
def web_search(keywords: str, region: str = "us-en", max_results: int = 3) -> str:
    """Search the web for current prices, reviews, availability, or recent information.

    Args:
        keywords (str): The search query keywords.
        region (str): The search region: wt-wt, us-en, uk-en, ru-ru, etc..
        max_results (int | None): The maximum number of results to return.
    Returns:
        List of dictionaries with search results.
    """
    try:
        results = DDGS().text(keywords, region=region, max_results=max_results)
        if not results:
            return "No results found."
        return "\n\n".join(
            f"{r.get('title', '')}\n{r.get('href', '')}\n{r.get('body', '')[:300]}"
            for r in results
        )
    except RatelimitException:
        return "Rate limit reached. Please try again later."
    except DDGSException as e:
        return f"Search error: {e}"
    except Exception as e:
        return f"Search error: {str(e)}"


@tool
def get_technical_support(issue_description: str) -> str:
    """
    Get technical support information from the knowledge base.

    Args:
        issue_description: Description of the technical issue or question.
    Returns:
        Technical support guidance from the knowledge base.
    """
    try:
        from agentcore import AWS_REGION as region
        ssm = boto3.client("ssm", region_name=region)
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        kb_id = ssm.get_parameter(Name=f"/{account_id}-{region}/kb/knowledge-base-id")["Parameter"]["Value"]
        tool_use = {
            "toolUseId": "tech_support_query",
            "input": {
                "text": issue_description,
                "knowledgeBaseId": kb_id,
                "region": region,
                "numberOfResults": 3,
                "score": 0.4,
            },
        }
        result = retrieve.retrieve(tool_use)
        if result["status"] == "success":
            return result["content"][0]["text"]
        return f"Unable to access technical support documentation. Error: {result['content'][0]['text']}"
    except Exception as e:
        return f"Unable to access technical support documentation. Error: {str(e)}"


def _ensure_knowledge_base(account_id: str, region: str) -> tuple[str, str]:
    """Create the KB and data source if they don't exist; return (kb_id, ds_id)."""
    ssm = boto3.client("ssm", region_name=region)
    bedrock = boto3.client("bedrock-agent", region_name=region)

    kb_param = f"/{account_id}-{region}/kb/knowledge-base-id"
    ds_param = f"/{account_id}-{region}/kb/data-source-id"

    # Try to reuse existing KB from SSM — only if it is in a usable state
    _unusable = {"DELETE_UNSUCCESSFUL", "DELETING", "FAILED"}
    try:
        kb_id = ssm.get_parameter(Name=kb_param)["Parameter"]["Value"]
        ds_id = ssm.get_parameter(Name=ds_param)["Parameter"]["Value"]
        kb_info = bedrock.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]
        status = kb_info.get("status", "")
        if status in _unusable:
            print(f"  KB {kb_id} is in unusable state ({status}) — creating a new versioned KB.")
        else:
            print(f"  Found existing Knowledge Base: {kb_id} (status: {status})")
            return kb_id, ds_id
    except Exception:
        pass

    # KB is missing — create it using resources from the CF stack.
    # Auto-version: if base name is stuck (DELETE_UNSUCCESSFUL/DELETING), use _v2, _v3, …
    base_name = f"{account_id}-{region}-kb"
    blocked_statuses = {"DELETE_UNSUCCESSFUL", "DELETING"}
    existing_kbs = bedrock.list_knowledge_bases().get("knowledgeBaseSummaries", [])
    blocked_names = {kb["name"] for kb in existing_kbs if kb.get("status") in blocked_statuses}

    version = 1
    kb_name = base_name
    while kb_name in blocked_names:
        version += 1
        kb_name = f"{base_name}-v{version}"
    if version > 1:
        print(f"  Base KB name blocked — using versioned name: {kb_name}")

    suffix = "" if version == 1 else f"-v{version}"
    ds_name = f"{account_id}-{region}-kb-datasource{suffix}"
    vector_bucket = f"{account_id}-{region}-kb-vector-bucket{suffix}"
    data_bucket = f"{account_id}-{region}-kb-data-bucket"
    bedrock_role_arn = f"arn:aws:iam::{account_id}:role/{account_id}-{region}-kb-bedrock-service-role"
    embed_model_arn = f"arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"

    index_name = f"{account_id}-{region}-kb-vector-index{suffix}"
    index_arn = f"arn:aws:s3vectors:{region}:{account_id}:bucket/{vector_bucket}/index/{index_name}"

    # Ensure the S3 Vectors bucket and index exist
    s3vectors = boto3.client("s3vectors", region_name=region)
    try:
        s3vectors.create_vector_bucket(vectorBucketName=vector_bucket)
        print(f"  Created S3 Vectors bucket '{vector_bucket}'.")
    except s3vectors.exceptions.ConflictException:
        print(f"  S3 Vectors bucket '{vector_bucket}' already exists.")

    existing = s3vectors.list_indexes(vectorBucketName=vector_bucket).get("indexes", [])
    if not any(i["indexName"] == index_name for i in existing):
        print(f"  Creating S3 Vectors index '{index_name}'...")
        s3vectors.create_index(
            vectorBucketName=vector_bucket,
            indexName=index_name,
            dimension=1024,
            distanceMetric="cosine",
            dataType="float32",
        )
        print(f"  Index created.")

    print(f"  Creating Knowledge Base '{kb_name}'...")
    kb_resp = bedrock.create_knowledge_base(
        name=kb_name,
        roleArn=bedrock_role_arn,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": embed_model_arn,
                "embeddingModelConfiguration": {
                    "bedrockEmbeddingModelConfiguration": {
                        "dimensions": 1024,
                        "embeddingDataType": "FLOAT32",
                    }
                },
            },
        },
        storageConfiguration={
            "type": "S3_VECTORS",
            "s3VectorsConfiguration": {"indexArn": index_arn},
        },
    )
    kb_id = kb_resp["knowledgeBase"]["knowledgeBaseId"]

    print(f"  Waiting for KB {kb_id} to become ACTIVE...")
    while True:
        status = bedrock.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]["status"]
        if status == "ACTIVE":
            break
        print(f"    Status: {status}")
        time.sleep(5)

    print(f"  Creating Data Source '{ds_name}'...")
    ds_resp = bedrock.create_data_source(
        knowledgeBaseId=kb_id,
        name=ds_name,
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {"bucketArn": f"arn:aws:s3:::{data_bucket}"},
        },
    )
    ds_id = ds_resp["dataSource"]["dataSourceId"]

    ssm.put_parameter(Name=kb_param, Value=kb_id, Type="String", Overwrite=True)
    ssm.put_parameter(Name=ds_param, Value=ds_id, Type="String", Overwrite=True)
    print(f"  SSM updated — KB: {kb_id}, DS: {ds_id}")
    return kb_id, ds_id


def sync_knowledge_base() -> None:
    """Ensure KB exists, then start and poll an ingestion job until completion."""
    region = AWS_REGION
    account_id = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
    bedrock = boto3.client("bedrock-agent", region_name=region)
    s3 = boto3.client("s3", region_name=region)

    kb_id, ds_id = _ensure_knowledge_base(account_id, region)

    bucket_name = f"{account_id}-{region}-kb-data-bucket"
    s3_objects = s3.list_objects_v2(Bucket=bucket_name)
    file_names = [obj["Key"] for obj in s3_objects.get("Contents", [])]

    response = bedrock.start_ingestion_job(
        knowledgeBaseId=kb_id, dataSourceId=ds_id, description="Automated sync"
    )
    job_id = response["ingestionJob"]["ingestionJobId"]
    print(f"  Ingestion job started: {job_id}")

    while True:
        job = bedrock.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )["ingestionJob"]
        status = job["status"]
        if status in ["COMPLETE", "FAILED"]:
            break
        print(f"  Status: {status} — waiting 10s...")
        time.sleep(10)

    if status == "COMPLETE":
        file_count = job.get("statistics", {}).get("numberOfDocumentsScanned", 0)
        print(f"Knowledge base sync complete. Ingested {file_count} files: {', '.join(file_names)}")
    else:
        raise RuntimeError(f"Knowledge base sync failed with status: {status}")


def build_agent() -> Agent:
    """Build and return the customer support agent."""
    model = BedrockModel(model_id=MODEL_ID, temperature=0.3, region_name=AWS_REGION)
    return Agent(
        model=model,
        tools=[get_product_info, get_return_policy, web_search, get_technical_support],
        system_prompt=SYSTEM_PROMPT,
    )


def run() -> None:
    """Run Step 1: sync knowledge base and test the prototype agent."""
    print("\n=== Step 1: Customer Support Agent Prototype ===")
    print("Syncing knowledge base...")
    sync_knowledge_base()

    agent = build_agent()
    print("\nAgent ready. Running sample queries...\n")

    queries = [
        "What's the return policy for my ThinkPad X1 Carbon?",
        "My laptop won't turn on, what should I check?",
        "I bought an iPhone 14 last month. It heats up. How do I fix it?",
    ]
    for q in queries:
        print(f"\n> {q}")
        print("-" * 60)
        agent(q)

    print("\n=== Step 1 complete ===\n")
