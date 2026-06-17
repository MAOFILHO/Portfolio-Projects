"""
Step 5: AgentCore Observability (OpenTelemetry)

Sets up CloudWatch log groups/streams and writes an .env file with OTEL config,
then runs the agent under opentelemetry-instrument for automatic tracing to
CloudWatch GenAI Observability dashboard.
"""
import os
import subprocess
import sys

import boto3
from botocore.exceptions import ClientError

LOG_GROUP_NAME = "agents/customer-support-assistant-logs"
LOG_STREAM_NAME = "default"
SERVICE_NAME = "customer-support-assistant-strands"
AGENT_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "runtime", "observability_agent.py")


def setup_cloudwatch_logs(region: str, log_group: str, log_stream: str) -> None:
    """Create CloudWatch log group and stream if they don't exist."""
    logs = boto3.client("logs", region_name=region)
    try:
        logs.create_log_group(logGroupName=log_group)
        print(f"  Created log group: {log_group}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceAlreadyExistsException":
            print(f"  Log group already exists: {log_group}")
        else:
            raise
    try:
        logs.create_log_stream(logGroupName=log_group, logStreamName=log_stream)
        print(f"  Created log stream: {log_stream}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceAlreadyExistsException":
            print(f"  Log stream already exists: {log_stream}")
        else:
            raise


def write_otel_env(region: str, account_id: str, log_group: str, log_stream: str) -> str:
    """Write .env file with OTEL configuration. Returns path to the file."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(env_path, "w") as f:
        f.write(f"AWS_REGION={region}\n")
        f.write(f"AWS_DEFAULT_REGION={region}\n")
        f.write(f"AWS_ACCOUNT_ID={account_id}\n")
        f.write("OTEL_PYTHON_DISTRO=aws_distro\n")
        f.write("OTEL_PYTHON_CONFIGURATOR=aws_configurator\n")
        f.write("OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf\n")
        f.write("OTEL_TRACES_EXPORTER=otlp\n")
        f.write(
            f"OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group={log_group},"
            f"x-aws-log-stream={log_stream},x-aws-metric-namespace=agents\n"
        )
        f.write(f"OTEL_RESOURCE_ATTRIBUTES=service.name={SERVICE_NAME}\n")
        f.write("AGENT_OBSERVABILITY_ENABLED=true\n")
    return env_path


def _console_urls(region: str) -> dict:
    """Return direct CloudWatch console URLs for observability dashboards."""
    base = f"https://{region}.console.aws.amazon.com"
    log_group_encoded = LOG_GROUP_NAME.replace("/", "$252F")
    return {
        "GenAI Observability — sessions + token usage + LLM latency": (
            f"{base}/cloudwatch/home?region={region}#gen-ai-observability/agent-core"
        ),
        "Application Signals — services instrumented by ADOT": (
            f"{base}/cloudwatch/home?region={region}#application-signals:services"
        ),
        "Application Map — topology of agent → Bedrock → tools": (
            f"{base}/cloudwatch/home?region={region}#application-signals:application-map"
        ),
        "CloudWatch Log Group — raw OTEL log lines": (
            f"{base}/cloudwatch/home?region={region}#logsV2:log-groups/log-group/{log_group_encoded}"
        ),
    }


def run() -> None:
    """Run Step 5: configure OTEL and run the agent under opentelemetry-instrument."""
    print("\n=== Step 5: AgentCore Observability (OpenTelemetry + CloudWatch) ===")

    session = boto3.Session()
    region = session.region_name or "us-east-1"
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    print("\n[Step 1/3] Creating CloudWatch log group and stream for OTEL traces...")
    setup_cloudwatch_logs(region, LOG_GROUP_NAME, LOG_STREAM_NAME)

    print("\n[Step 2/3] Writing OTEL environment configuration to .env file...")
    env_path = write_otel_env(region, account_id, LOG_GROUP_NAME, LOG_STREAM_NAME)
    print(f"  Written to: {env_path}")
    print("  Key OTEL variables:")
    print(f"    OTEL_PYTHON_DISTRO=aws_distro")
    print(f"    OTEL_TRACES_EXPORTER=otlp")
    print(f"    OTEL_RESOURCE_ATTRIBUTES=service.name={SERVICE_NAME}")
    print(f"    AGENT_OBSERVABILITY_ENABLED=true")

    print("\n[Step 3/3] Running agent under opentelemetry-instrument for auto-instrumentation...")
    print("  Traces will appear in CloudWatch GenAI Observability dashboard.")
    print(f"  Log group: {LOG_GROUP_NAME}")
    print()

    session_id = "observability-demo-session"
    cmd = [
        "opentelemetry-instrument",
        sys.executable, AGENT_SCRIPT,
        "--session-id", session_id,
    ]
    env = os.environ.copy()
    env.update({
        "AWS_REGION": region,
        "AWS_DEFAULT_REGION": region,
        "AWS_ACCOUNT_ID": account_id,
        "OTEL_PYTHON_DISTRO": "aws_distro",
        "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_TRACES_EXPORTER": "otlp",
        "OTEL_EXPORTER_OTLP_LOGS_HEADERS": f"x-aws-log-group={LOG_GROUP_NAME},x-aws-log-stream={LOG_STREAM_NAME},x-aws-metric-namespace=agents",
        "OTEL_RESOURCE_ATTRIBUTES": f"service.name={SERVICE_NAME}",
        "AGENT_OBSERVABILITY_ENABLED": "true",
    })
    try:
        subprocess.run(cmd, check=True, env=env)
    except FileNotFoundError:
        print("  'opentelemetry-instrument' not found. Install with:")
        print("  pip install aws-opentelemetry-distro")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Instrumented agent run failed: {e}") from e

    urls = _console_urls(region)
    print("\n=== Step 5 complete — View your telemetry ===\n")
    print("  Open these URLs in your browser:\n")
    for label, url in urls.items():
        print(f"  [{label}]")
        print(f"  {url}\n")
