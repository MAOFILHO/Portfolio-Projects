from azure.ai.ml import MLClient
from azure.ai.ml.entities import (
    ManagedOnlineEndpoint,
    ManagedOnlineDeployment,
    Environment,
    CodeConfiguration,
    ProbeSettings,
)
from azure.identity import DefaultAzureCredential
import os

# Environment name for MLflow inference with azureml-ai-monitoring (fixes Collector import)
INFERENCE_ENV_NAME = "guardian-mlflow-inference"
# Azure ML inference base image (Ubuntu 22.04); required so Environment build accepts conda_file
INFERENCE_BASE_IMAGE = "mcr.microsoft.com/azureml/inference-base-2204:20260218.v1"
INFERENCE_BASE_IMAGE_FALLBACK = "mcr.microsoft.com/azureml/inference-base-2204:latest"


def _get_or_create_inference_environment(ml_client):
    """Create or get environment that includes azureml-ai-monitoring for MLflow score scripts.
    Uses base image + conda_file because Azure ML requires image or Dockerfile."""
    deploy_dir = os.path.dirname(os.path.abspath(__file__))
    conda_path = os.path.join(deploy_dir, "conda-inference.yaml")
    if not os.path.isfile(conda_path):
        return None
    last_error = None
    for image in (INFERENCE_BASE_IMAGE, INFERENCE_BASE_IMAGE_FALLBACK):
        try:
            env = Environment(
                name=INFERENCE_ENV_NAME,
                image=image,
                conda_file=conda_path,
            )
            env = ml_client.environments.create_or_update(env)
            return f"{INFERENCE_ENV_NAME}:{env.version}"
        except Exception as e:
            last_error = e
            continue
    print(f"Could not create inference environment: {last_error}. Using model environment.")
    return None

def _get_code_configuration():
    """Return explicit scoring configuration so Azure ML packages the entry script."""
    deploy_dir = os.path.dirname(os.path.abspath(__file__))
    scoring_script = "main.py"
    scoring_script_path = os.path.join(deploy_dir, scoring_script)
    if not os.path.isfile(scoring_script_path):
        raise FileNotFoundError(
            f"Required scoring script not found: {scoring_script_path}. "
            "Deployment expects mlops/deployment/main.py."
        )
    return CodeConfiguration(
        code=deploy_dir,
        scoring_script=scoring_script,
    )


def deploy_model(model_name="nsfw-detector", version="latest"):
    """Deploy model to Azure ML with A/B testing support"""
    
    ml_client = MLClient(
        DefaultAzureCredential(),
        subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
        resource_group_name=os.getenv("AZURE_RESOURCE_GROUP"),
        workspace_name=os.getenv("AZURE_ML_WORKSPACE")
    )
    
    endpoint_name = f"{model_name}-endpoint"
    
    print(f"Deploying {model_name} to Azure ML...")
    
    # Create or update endpoint
    endpoint = ManagedOnlineEndpoint(
        name=endpoint_name,
        description=f"{model_name} inference endpoint",
        auth_mode="key",
        tags={"model": model_name, "environment": "production"}
    )
    
    print(f"Creating endpoint: {endpoint_name}")
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()
    
    # Get latest model version
    if version == "latest":
        model_versions = ml_client.models.list(name=model_name)
        latest_version = max([int(m.version) for m in model_versions])
        version = str(latest_version)
    
    print(f"Using model version: {version}")
    
    # Optional: use custom env with azureml-ai-monitoring so existing MLflow score scripts work
    env_id = _get_or_create_inference_environment(ml_client)
    deployment_kw = {}
    if env_id:
        deployment_kw["environment"] = env_id
        print(f"Using inference environment: {env_id}")
    deployment_kw["code_configuration"] = _get_code_configuration()
    print("Using scoring script: mlops/deployment/main.py")
    
    # Deploy champion model (production). instance_count=1 to stay within DS3_v2 quota (20 vCPUs) for both models.
    champion_deployment = ManagedOnlineDeployment(
        name="champion",
        endpoint_name=endpoint_name,
        model=f"{model_name}:{version}",
        instance_type="Standard_DS1_v2",
        instance_count=1,
        **deployment_kw,
        environment_variables={
            "MODEL_VERSION": version
        },
        liveness_probe=ProbeSettings(
            failure_threshold=3,
            success_threshold=1,
            timeout=10,
            period=10,
            initial_delay=30
        ),
        readiness_probe=ProbeSettings(
            failure_threshold=3,
            success_threshold=1,
            timeout=10,
            period=10,
            initial_delay=30
        )
    )
    
    print("Deploying champion model...")
    ml_client.online_deployments.begin_create_or_update(champion_deployment).result()
    
    # Route all traffic to champion unless A/B testing is enabled.
    endpoint.traffic = {"champion": 100}
    
    # Deploy challenger model for A/B testing (if enabled)
    if os.getenv("ENABLE_AB_TESTING", "false").lower() == "true":
        print("Deploying challenger model for A/B testing...")
        
        challenger_deployment = ManagedOnlineDeployment(
            name="challenger",
            endpoint_name=endpoint_name,
            model=f"{model_name}:{version}",
            instance_type="Standard_DS1_v2",
            instance_count=1,
            **deployment_kw,
            environment_variables={
                "MODEL_VERSION": version,
                "DEPLOYMENT_TYPE": "challenger"
            }
        )
        
        ml_client.online_deployments.begin_create_or_update(challenger_deployment).result()
        
        # Split traffic for A/B testing
        traffic_percent = int(os.getenv("CHALLENGER_TRAFFIC_PERCENT", "10"))
        endpoint.traffic = {
            "champion": 100 - traffic_percent,
            "challenger": traffic_percent
        }
    
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()
    
    # Get endpoint details
    endpoint_details = ml_client.online_endpoints.get(endpoint_name)
    scoring_uri = endpoint_details.scoring_uri
    
    print(f"\nDeployment successful!")
    print(f"Scoring URI: {scoring_uri}")
    print(f"Traffic split: {endpoint.traffic}")
    
    return scoring_uri

def deploy_all_models():
    """Deploy all trained models"""
    models = ["nsfw-detector", "violence-detector"]
    
    endpoints = {}
    for model_name in models:
        try:
            uri = deploy_model(model_name)
            endpoints[model_name] = uri
        except Exception as e:
            print(f"Failed to deploy {model_name}: {e}")
    
    return endpoints

if __name__ == "__main__":
    print("Guardian AI - Model Deployment Pipeline")
    print("="*50)
    
    endpoints = deploy_all_models()
    
    print("\nDeployment Summary:")
    for model, uri in endpoints.items():
        print(f"  {model}: {uri}")
    
    print("\nUpdate your .env file with these endpoints!")
