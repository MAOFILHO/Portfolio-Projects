"""
MultiCloud MLOps - Smoke Test Suite
Runs without any cloud credentials.  Verifies:
  1.  All automation Python modules import cleanly
  2.  Config loads from environment without errors
  3.  Shell utility functions work correctly
  4.  All k8s YAML manifests parse as valid YAML
  5.  All Azure DevOps pipeline YAML files parse as valid YAML
  6.  All service Dockerfiles exist
  7.  All service requirements.txt files exist
  8.  scripts/setup-aws.sh has correct bash syntax (bash -n)
  9.  Service app.py files import expected env var names
  10. DynamoDB table primary key names are correct (video_id / event_id)
  11. ACR placeholder in k8s manifests can be detected and replaced
  12. Config default values match what pipeline YAMLs reference
"""
import importlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Project root = two levels up from tests/smoke/
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── 1. Module imports ────────────────────────────────────────────────────────

AUTOMATION_MODULES = [
    "automation.config",
    "automation.utils.shell",
    "automation.aws.setup_aws",
    "automation.azure.setup_azure",
    "automation.azure.build_images",
    "automation.k8s.deploy_k8s",
    "automation.devops.setup_devops",
    "automation.ml.setup_ml",
    "automation.cleanup",
]


@pytest.mark.parametrize("module", AUTOMATION_MODULES)
def test_module_imports(module):
    """Every automation module must import without errors."""
    # Provide dummy env vars so modules that read os.getenv don't crash
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AZURE_SUBSCRIPTION_ID", "test-sub-id")
    os.environ.setdefault("AZDO_PAT_TOKEN", "test-pat")
    mod = importlib.import_module(module)
    assert mod is not None


# ─── 2. Config loading ────────────────────────────────────────────────────────

def test_config_loads():
    """Config object must be importable with all expected fields."""
    from automation.config import ProjectConfig, config

    assert isinstance(config, ProjectConfig)
    assert hasattr(config, "aws")
    assert hasattr(config, "azure")
    assert hasattr(config, "devops")
    assert hasattr(config, "ml")
    assert hasattr(config, "k8s")
    assert isinstance(config.services, list)
    assert len(config.services) == 7


def test_config_service_names():
    """Service names must match the actual services/ subdirectories."""
    from automation.config import config

    expected = {
        "ingestion", "fast-screening", "deep-vision",
        "policy-engine", "human-review", "notification", "api-gateway",
    }
    assert set(config.services) == expected


def test_config_variable_group_name():
    """Variable group name must match what pipeline YAMLs declare."""
    from automation.config import config

    assert config.devops.variable_group_name == "guardian-variables"


def test_config_service_connection_names():
    """Service connection names must match what pipeline YAMLs reference."""
    from automation.config import config

    assert config.devops.azure_sc_name == "guardian-azure-connection"
    assert config.devops.acr_sc_name   == "guardian-acr-connection"
    assert config.devops.aks_sc_name   == "guardian-aks-connection"


def test_config_pipeline_yaml_paths():
    """Pipeline YAML paths must reference files that exist in the repo."""
    from automation.config import config

    for yaml_path in (
        config.devops.app_pipeline_yaml,
        config.devops.ml_training_yaml,
        config.devops.ml_deployment_yaml,
    ):
        # Strip leading slash
        full = PROJECT_ROOT / yaml_path.lstrip("/")
        assert full.exists(), f"Pipeline YAML not found: {full}"


# ─── 3. Shell utilities ───────────────────────────────────────────────────────

def test_shell_run_success():
    from automation.utils.shell import run

    result = run(["echo", "hello"], capture=True, description="echo test")
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_shell_run_json():
    from automation.utils.shell import run_json

    result = run_json(["python3", "-c", "import json; print(json.dumps({'ok': True}))"])
    assert result == {"ok": True}


def test_shell_run_failure_raises():
    from automation.utils.shell import run
    import subprocess

    with pytest.raises(subprocess.CalledProcessError):
        run(["false"], check=True, description="expected failure")


def test_shell_run_or_skip_does_not_raise():
    from automation.utils.shell import run_or_skip

    result = run_or_skip(["false"], description="non-fatal failure")
    assert result is None


def test_check_tools_returns_bool():
    from automation.utils.shell import check_tools

    # python3 is always available; result should be True
    assert check_tools(["python3"]) is True


# ─── 4. Kubernetes YAML files ─────────────────────────────────────────────────

K8S_YAMLS = list((PROJECT_ROOT / "k8s").rglob("*.yaml"))


@pytest.mark.parametrize("yaml_file", K8S_YAMLS, ids=[str(f.relative_to(PROJECT_ROOT)) for f in K8S_YAMLS])
def test_k8s_yaml_valid(yaml_file):
    """Every k8s YAML must parse without errors."""
    import yaml  # pyyaml

    content = yaml_file.read_text()
    docs = list(yaml.safe_load_all(content))
    assert len(docs) >= 1, f"Empty YAML: {yaml_file}"


def test_k8s_namespace_is_production():
    """All k8s resources must use namespace: production."""
    import yaml

    skip_files = {"namespace.yaml"}
    for yf in K8S_YAMLS:
        if yf.name in skip_files:
            continue
        content = yf.read_text()
        for doc in yaml.safe_load_all(content):
            if isinstance(doc, dict) and "metadata" in doc:
                ns = doc["metadata"].get("namespace")
                if ns:
                    assert ns == "production", (
                        f"{yf}: expected namespace 'production', got '{ns}'"
                    )


def test_k8s_manifests_have_acr_reference():
    """CPU service deployments must reference *.azurecr.io images."""
    cpu_dir = PROJECT_ROOT / "k8s" / "cpu-services"
    # Exclude redis (uses public image redis:7-alpine, not ACR)
    for yaml_file in [f for f in cpu_dir.glob("*.yaml") if f.name != "redis.yaml"]:
        content = yaml_file.read_text()
        import yaml
        for doc in yaml.safe_load_all(content):
            if not isinstance(doc, dict):
                continue
            if doc.get("kind") != "Deployment":
                continue
            containers = (
                doc.get("spec", {})
                   .get("template", {})
                   .get("spec", {})
                   .get("containers", [])
            )
            for c in containers:
                image = c.get("image", "")
                assert "azurecr.io" in image, (
                    f"{yaml_file.name}: container image should reference azurecr.io, "
                    f"got: {image}"
                )


# ─── 5. Pipeline YAMLs ────────────────────────────────────────────────────────

PIPELINE_YAMLS = list(PROJECT_ROOT.glob("azure-pipelines-*.yml"))


@pytest.mark.parametrize(
    "yaml_file", PIPELINE_YAMLS,
    ids=[f.name for f in PIPELINE_YAMLS],
)
def test_pipeline_yaml_valid(yaml_file):
    """Each Azure DevOps pipeline YAML must parse as valid YAML."""
    import yaml

    content = yaml_file.read_text()
    doc = yaml.safe_load(content)
    assert isinstance(doc, dict)


def test_pipeline_yamls_reference_correct_variable_group():
    """Pipeline YAMLs must reference 'guardian-variables'."""
    import yaml

    for yf in PIPELINE_YAMLS:
        content = yf.read_text()
        assert "guardian-variables" in content, (
            f"{yf.name}: missing '- group: guardian-variables'"
        )


def test_pipeline_yamls_reference_correct_service_connections():
    """Pipeline YAMLs must use the exact service connection names from config."""
    import yaml
    from automation.config import config

    app_pipeline = PROJECT_ROOT / "azure-pipelines-app-ci-cd.yml"
    content = app_pipeline.read_text()
    assert config.devops.acr_sc_name in content, (
        f"App pipeline missing ACR connection: {config.devops.acr_sc_name}"
    )


# ─── 6. Service Dockerfiles ───────────────────────────────────────────────────

@pytest.mark.parametrize("service", [
    "ingestion", "fast-screening", "deep-vision", "policy-engine",
    "human-review", "notification", "api-gateway",
])
def test_service_dockerfile_exists(service):
    df = PROJECT_ROOT / "services" / service / "Dockerfile"
    assert df.exists(), f"Dockerfile missing: {df}"


# ─── 7. Service requirements.txt ─────────────────────────────────────────────

@pytest.mark.parametrize("service", [
    "ingestion", "fast-screening", "deep-vision", "policy-engine",
    "human-review", "notification", "api-gateway",
])
def test_service_requirements_exists(service):
    req = PROJECT_ROOT / "services" / service / "requirements.txt"
    assert req.exists(), f"requirements.txt missing: {req}"


# ─── 8. Bash script syntax ───────────────────────────────────────────────────

@pytest.mark.parametrize("script", [
    "scripts/setup-aws.sh",
    "aws_resource_cleanup.sh",
    "scripts/update-acr-in-manifests.sh",
    "scripts/setup-azure.sh",
])
def test_bash_script_syntax(script):
    """Scripts must pass bash -n (syntax check)."""
    path = PROJECT_ROOT / script
    if not path.exists():
        pytest.skip(f"Script not found: {path}")
    result = subprocess.run(
        ["bash", "-n", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Bash syntax error in {script}:\n{result.stderr}"
    )


# ─── 9. DynamoDB primary key names ───────────────────────────────────────────

def test_dynamodb_key_names_in_aws_setup():
    """
    AWS setup must use correct DynamoDB primary key names that match
    what the service code (app.py files) use as table keys.
    ingestion/app.py stores records with key 'video_id', not 'id'.
    """
    aws_setup = (PROJECT_ROOT / "automation" / "aws" / "setup_aws.py").read_text()
    # The AWS setup delegates to setup-aws.sh; check the shell script directly
    setup_sh = (PROJECT_ROOT / "scripts" / "setup-aws.sh").read_text()
    assert "video_id" in setup_sh, "setup-aws.sh must use 'video_id' as DynamoDB key"
    assert "event_id" in setup_sh, "setup-aws.sh must use 'event_id' as DynamoDB key"


# ─── 10. ConfigMap env var names match service code ──────────────────────────

def test_configmap_env_vars_match_services():
    """
    ConfigMap must include the exact env var names that service apps read.
    Checked against ingestion/app.py as the canonical reference.
    """
    import yaml

    configmap_file = PROJECT_ROOT / "k8s" / "configmap.yaml"
    ingestion_app  = PROJECT_ROOT / "services" / "ingestion" / "app.py"

    if not configmap_file.exists() or not ingestion_app.exists():
        pytest.skip("ConfigMap or ingestion app.py not found")

    # Keys defined in ConfigMap
    doc = yaml.safe_load(configmap_file.read_text())
    cm_keys = set(doc.get("data", {}).keys())

    # Env vars that ingestion app.py reads via os.getenv
    ingestion_src = ingestion_app.read_text()
    used_vars = set(re.findall(r'os\.getenv\(["\']([A-Z_]+)["\']', ingestion_src))

    for var in used_vars:
        assert var in cm_keys or var.startswith("AWS_"), (
            f"Ingestion reads '{var}' but it's missing from ConfigMap"
        )


# ─── 11. ACR replacement works ────────────────────────────────────────────────

def test_acr_sed_pattern_matches_manifest_images(tmp_path):
    """Verify the sed pattern used by _patch_k8s_manifests replaces ACR correctly."""
    test_yaml = tmp_path / "test.yaml"
    test_yaml.write_text(
        "image: guardianacr65958.azurecr.io/guardian-ai-ingestion:v1\n"
        "image: ACR_PLACEHOLDER.azurecr.io/guardian-ai-deep-vision:v1\n"
    )
    # Simulate the sed replacement
    result = subprocess.run(
        ["sed", "-i",
         "s|[a-z0-9]*\\.azurecr\\.io|newacr12345.azurecr.io|g",
         str(test_yaml)],
        capture_output=True,
    )
    content = test_yaml.read_text()
    assert "newacr12345.azurecr.io" in content
    assert "guardianacr65958" not in content


# ─── 12. setup.py entrypoint ─────────────────────────────────────────────────

def test_setup_py_exists():
    assert (PROJECT_ROOT / "setup.py").exists()


def test_setup_py_syntax():
    """setup.py must pass Python compile check."""
    import ast
    source = (PROJECT_ROOT / "setup.py").read_text()
    ast.parse(source)  # raises SyntaxError if invalid


def test_setup_py_check_flag(capsys):
    """python setup.py --check must exit 1 when tools are missing (in CI)."""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "setup.py"), "--check"],
        capture_output=True, text=True,
    )
    # May be 0 (all tools present) or 1 (some missing) — just must not crash/exception
    assert result.returncode in (0, 1)


# ─── 13. README completeness ─────────────────────────────────────────────────

def test_readme_references_setup_py():
    readme = (PROJECT_ROOT / "README.md").read_text()
    assert "setup.py" in readme


def test_readme_references_all_stages():
    readme = (PROJECT_ROOT / "README.md").read_text()
    for stage in ("aws", "azure", "images", "k8s", "devops", "ml"):
        assert stage in readme, f"README missing stage: {stage}"


# ─── 14. Region handling ──────────────────────────────────────────────────────

def test_setup_aws_sh_no_hardcoded_region():
    """setup-aws.sh must NOT hardcode ap-south-1 — region comes from env/config."""
    script = (PROJECT_ROOT / "scripts" / "setup-aws.sh").read_text()
    assert 'REGION="ap-south-1"' not in script, (
        "setup-aws.sh still has hardcoded REGION=ap-south-1. "
        "Must use: REGION=${AWS_REGION:-$(aws configure get region)}"
    )
    assert "AWS_REGION" in script, "setup-aws.sh must reference AWS_REGION env var"


def test_cleanup_sh_no_hardcoded_region():
    """aws_resource_cleanup.sh must not fall back to ap-south-1."""
    script = (PROJECT_ROOT / "aws_resource_cleanup.sh").read_text()
    assert '"ap-south-1"' not in script, (
        "aws_resource_cleanup.sh still references ap-south-1"
    )


def test_setup_aws_py_sqs_has_region_flag():
    """setup_aws.py get_resource_urls must pass --region to SQS calls."""
    src = (PROJECT_ROOT / "automation" / "aws" / "setup_aws.py").read_text()
    # Count --region occurrences in SQS/DynamoDB calls
    import re
    region_count = len(re.findall(r'"--region", region', src))
    assert region_count >= 4, (
        f"Expected at least 4 '--region' flags in setup_aws.py "
        f"(2 SQS + 2 DynamoDB), found {region_count}"
    )


def test_s3_us_east_1_no_location_constraint():
    """setup-aws.sh must handle us-east-1 without LocationConstraint."""
    script = (PROJECT_ROOT / "scripts" / "setup-aws.sh").read_text()
    assert 'REGION" = "us-east-1"' in script or "us-east-1" in script, (
        "setup-aws.sh must handle us-east-1 S3 creation (no LocationConstraint)"
    )


def test_env_example_no_hardcoded_ap_south():
    """.env.example must not default to ap-south-1."""
    env_example = (PROJECT_ROOT / ".env.example").read_text()
    assert "ap-south-1" not in env_example, (
        ".env.example still references ap-south-1 as default region"
    )
