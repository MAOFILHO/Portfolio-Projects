"""
Azure ML Job Submission Script
Submits training jobs to Azure ML compute cluster instead of running locally
"""
import os
import sys
import argparse
from azure.ai.ml import MLClient, command
from azure.ai.ml.entities import Environment, CodeConfiguration
from azure.identity import DefaultAzureCredential
from azure.ai.ml.constants import AssetTypes
import time
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def submit_training_job(
    model_type: str,
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    compute_cluster: str,
    training_script: str = None,
    experiment_name: str = None
):
    """
    Submit a training job to Azure ML compute cluster
    
    Args:
        model_type: Type of model to train ('nsfw' or 'violence')
        subscription_id: Azure subscription ID
        resource_group: Azure resource group name
        workspace_name: Azure ML workspace name
        compute_cluster: Name of the compute cluster
        training_script: Path to training script (defaults based on model_type)
        experiment_name: MLflow experiment name (defaults based on model_type)
    """
    
    # Initialize ML Client
    print(f"Initializing ML Client...")
    print(f"Subscription: {subscription_id}")
    print(f"Resource Group: {resource_group}")
    print(f"Workspace: {workspace_name}")
    
    ml_client = MLClient(
        DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name
    )
    
    # Verify compute cluster exists
    print(f"Verifying compute cluster '{compute_cluster}' exists...")
    try:
        cluster = ml_client.compute.get(compute_cluster)
        print(f"Found compute cluster: {cluster.name} (Status: {cluster.provisioning_state})")
        if cluster.provisioning_state != "Succeeded":
            print(f"Warning: Compute cluster is not in 'Succeeded' state. Current state: {cluster.provisioning_state}")
    except Exception as e:
        print(f"Error: Compute cluster '{compute_cluster}' not found or not accessible: {e}")
        raise
    
    # Set defaults based on model type
    if model_type.lower() == "nsfw":
        if not training_script:
            training_script = "train_nsfw_model.py"
        if not experiment_name:
            experiment_name = "nsfw-detection"
        job_name = f"nsfw-training-{int(time.time())}"
    elif model_type.lower() == "violence":
        if not training_script:
            training_script = "train_violence_model.py"
        if not experiment_name:
            experiment_name = "violence-detection"
        job_name = f"violence-training-{int(time.time())}"
    else:
        raise ValueError(f"Invalid model_type: {model_type}. Must be 'nsfw' or 'violence'")
    
    # Get the directory containing the training script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    training_script_path = os.path.join(script_dir, training_script)
    
    if not os.path.exists(training_script_path):
        raise FileNotFoundError(f"Training script not found: {training_script_path}")
    
    print(f"Training script: {training_script_path}")
    print(f"Experiment name: {experiment_name}")
    print(f"Job name: {job_name}")
    
    # Set up environment variables for the job
    env_vars = {
        "AZURE_SUBSCRIPTION_ID": subscription_id,
        "AZURE_RESOURCE_GROUP": resource_group,
        "AZURE_ML_WORKSPACE": workspace_name,
        "AZURE_ML_REGION": os.getenv("AZURE_ML_REGION", "eastus"),
        "MLFLOW_TRACKING_URI": f"azureml://{os.getenv('AZURE_ML_REGION', 'eastus')}.api.azureml.ms/mlflow/v1.0/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}"
    }
    
    # Create a curated environment or use a base one
    # For PyTorch training, we'll use Azure ML's curated PyTorch environment
    print(f"Setting up job environment...")
    
    # Create command job
    # Install all dependencies and run training script
    # Using base Python environment and installing all packages ensures compatibility
    install_cmd = (
        "pip install --upgrade pip && "
        "pip install torch torchvision mlflow azureml-mlflow azure-ai-ml azure-identity "
        "transformers pillow numpy && "
        f"python {training_script}"
    )
    
    # Use Azure ML's base Python 3.9 environment
    # This is more reliable than curated environments which may not exist
    base_env = "AzureML-sklearn-1.0-ubuntu20.04-py38-cpu:1"  # Base Python environment
    
    # Try to use a PyTorch curated environment if available, otherwise fall back to base
    # You can customize this based on your workspace's available environments
    env_object = None
    try:
        # Check if PyTorch environment exists
        pytorch_envs = [env for env in ml_client.environments.list() 
                       if "pytorch" in env.name.lower()]
        if pytorch_envs:
            env_object = pytorch_envs[0]
            base_env = env_object.name
            print(f"Using PyTorch environment: {base_env}")
            # If using PyTorch env, we don't need to install torch/torchvision
            install_cmd = (
                "pip install --upgrade pip && "
                "pip install mlflow azureml-mlflow azure-ai-ml azure-identity "
                "transformers pillow numpy && "
                f"python {training_script}"
            )
        else:
            print(f"No PyTorch curated environment found, using base environment: {base_env}")
            # Try to get the base environment object
            try:
                env_object = ml_client.environments.get(base_env, version="1")
            except:
                pass  # Will use string name if object not found
    except Exception as e:
        print(f"Could not check for PyTorch environments, using base: {e}")
    
    # Use environment object if available, otherwise use string name
    environment_param = env_object if env_object else base_env
    
    # Use command() function from azure.ai.ml (SDK v2 API)
    # Note: command() returns a CommandJob object that can be configured
    command_job = command(
        code=script_dir,  # Upload entire training directory
        command=install_cmd,
        environment=environment_param,  # Use environment object or string name
        compute=compute_cluster,
        environment_variables=env_vars,
    )
    
    # Set additional properties on the command job
    command_job.name = job_name
    command_job.display_name = f"{model_type.capitalize()} Model Training"
    command_job.description = f"Train {model_type} detection model on Azure ML compute cluster"
    command_job.experiment_name = experiment_name
    command_job.tags = {
        "model_type": model_type,
        "training_type": "compute_cluster",
        "framework": "pytorch"
    }
    
    print(f"Submitting job to compute cluster '{compute_cluster}'...")
    print(f"Job name: {job_name}")
    print(f"Command: python {training_script}")
    
    try:
        # Submit the job
        returned_job = ml_client.jobs.create_or_update(command_job)
        print(f"Job submitted successfully!")
        print(f"Job ID: {returned_job.id}")
        print(f"Job Name: {returned_job.name}")
        print(f"Status: {returned_job.status}")
        print(f"Portal URL: {returned_job.studio_url}")
        
        # Wait for job completion
        print(f"\n Waiting for job to complete...")
        print(f"   You can monitor progress at: {returned_job.studio_url}")
        
        # Poll for job status
        max_wait_time = 3600 * 2  # 2 hours max wait
        poll_interval = 30  # Check every 30 seconds
        start_time = time.time()
        
        while True:
            # Get latest job status
            current_job = ml_client.jobs.get(returned_job.name)
            status = current_job.status
            
            elapsed_time = time.time() - start_time
            print(f"   Status: {status} (Elapsed: {int(elapsed_time)}s)")
            
            if status in ["Completed", "Failed", "Canceled"]:
                break
            
            if elapsed_time > max_wait_time:
                print(f" Warning: Maximum wait time ({max_wait_time}s) exceeded. Job may still be running.")
                print(f" Monitor at: {returned_job.studio_url}")
                return returned_job
            
            time.sleep(poll_interval)
        
        # Final status check
        final_job = ml_client.jobs.get(returned_job.name)
        print(f"\n Final Job Status: {final_job.status}")
        
        if final_job.status == "Completed":
            print(f" Job completed successfully!")
            print(f"   Job ID: {final_job.id}")
            print(f"   Portal URL: {final_job.studio_url}")
            return final_job
        elif final_job.status == "Failed":
            print(f" Job failed!")
            print(f"   Error details available at: {final_job.studio_url}")
            # Try to get error details
            if hasattr(final_job, 'error') and final_job.error:
                print(f"   Error: {final_job.error}")
            raise Exception(f"Training job failed. Check details at: {final_job.studio_url}")
        else:
            print(f" Job ended with status: {final_job.status}")
            return final_job
            
    except Exception as e:
        print(f"Error submitting job: {e}")
        raise


def main():
    """Main entry point for command-line usage"""
    parser = argparse.ArgumentParser(description="Submit training job to Azure ML compute cluster")
    parser.add_argument(
        "--model-type",
        type=str,
        required=True,
        choices=["nsfw", "violence"],
        help="Type of model to train"
    )
    parser.add_argument(
        "--subscription-id",
        type=str,
        default=os.getenv("AZURE_SUBSCRIPTION_ID"),
        help="Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var)"
    )
    parser.add_argument(
        "--resource-group",
        type=str,
        default=os.getenv("AZURE_RESOURCE_GROUP"),
        help="Azure resource group name (defaults to AZURE_RESOURCE_GROUP env var)"
    )
    parser.add_argument(
        "--workspace-name",
        type=str,
        default=os.getenv("AZURE_ML_WORKSPACE"),
        help="Azure ML workspace name (defaults to AZURE_ML_WORKSPACE env var)"
    )
    parser.add_argument(
        "--compute-cluster",
        type=str,
        default=os.getenv("COMPUTE_CLUSTER", "cpu-training-cluster"),
        help="Compute cluster name (defaults to COMPUTE_CLUSTER env var or 'cpu-training-cluster')"
    )
    parser.add_argument(
        "--training-script",
        type=str,
        default=None,
        help="Path to training script (defaults based on model-type)"
    )
    parser.add_argument(
        "--experiment-name",
        type=str,
        default=None,
        help="MLflow experiment name (defaults based on model-type)"
    )
    
    args = parser.parse_args()
    
    # Validate required environment variables if not provided as args
    if not args.subscription_id:
        raise ValueError("AZURE_SUBSCRIPTION_ID must be set as environment variable or --subscription-id argument")
    if not args.resource_group:
        raise ValueError("AZURE_RESOURCE_GROUP must be set as environment variable or --resource-group argument")
    if not args.workspace_name:
        raise ValueError("AZURE_ML_WORKSPACE must be set as environment variable or --workspace-name argument")
    
    try:
        job = submit_training_job(
            model_type=args.model_type,
            subscription_id=args.subscription_id,
            resource_group=args.resource_group,
            workspace_name=args.workspace_name,
            compute_cluster=args.compute_cluster,
            training_script=args.training_script,
            experiment_name=args.experiment_name
        )
        print(f"\n Training job completed successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"\n Failed to submit or complete training job: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
