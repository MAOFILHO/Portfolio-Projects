from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential
import os

def rollback_model(model_name="nsfw-detector"):
    """Rollback model to previous version"""
    ml_client = MLClient(
        DefaultAzureCredential(),
        subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
        resource_group_name=os.getenv("AZURE_RESOURCE_GROUP", "guardian-ai-prod"),
        workspace_name=os.getenv("AZURE_ML_WORKSPACE", "guardian-ml-workspace-prod")
    )
    
    endpoint_name = f"{model_name}-endpoint"
    
    try:
        endpoint = ml_client.online_endpoints.get(endpoint_name)
        
        # Rollback traffic to previous deployment
        endpoint.traffic = {"champion": 0, "previous-champion": 100}
        ml_client.online_endpoints.begin_create_or_update(endpoint).result()
        
        print(f"✅ Model {model_name} rolled back to previous version!")
    except Exception as e:
        print(f"❌ Failed to rollback {model_name}: {e}")

if __name__ == "__main__":
    import sys
    model_name = sys.argv[1] if len(sys.argv) > 1 else "nsfw-detector"
    rollback_model(model_name)
