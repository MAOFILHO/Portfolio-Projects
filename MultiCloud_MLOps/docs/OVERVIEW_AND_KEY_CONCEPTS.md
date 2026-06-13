# Guardian AI – Multi-Cloud MLOps: Overview and Key Concepts

This project helps you build a production-ready, multi-cloud MLOps pipeline that trains content-moderation models on Azure ML, deploys them to managed endpoints, and integrates them with an application layer that uses AWS for storage and messaging. Ideal for ML engineers, MLOps practitioners, and platform engineers, it demonstrates how to orchestrate Azure Machine Learning (compute clusters, model registry, online endpoints), Azure DevOps (CI/CD), and AWS (S3, SQS, DynamoDB) to automate the full ML lifecycle—from code commit and cluster-based training to model registration and online deployment—with optional integration into a video moderation application.

---

## Scenario

You are working with a content moderation team that must review large volumes of video uploads for policy compliance. Manually reviewing every video is slow and inconsistent. To scale and standardize decisions, you need to automate model training and deployment: train NSFW and violence-detection models on scalable compute, register and version them, deploy to managed inference endpoints, and have application services (which store videos and metadata on AWS) call those endpoints for real-time scoring. You will use Azure for the ML platform and AWS for data and messaging, with Azure DevOps pipelines orchestrating training and deployment so that new model versions flow from code commit to production endpoints without manual steps.

---

## Description

In this lab, you will learn how to orchestrate a multi-cloud MLOps workflow. Azure Machine Learning provides the workspace, compute clusters for training, a model registry for versioning, and managed online endpoints for inference. Azure DevOps runs CI/CD pipelines that submit training jobs to the cluster (instead of the pipeline agent), register trained models automatically, and deploy them to online endpoints. MLflow tracks experiments and metrics with an Azure ML backend. Optionally, application microservices (e.g., Deep-Vision) run on Azure Kubernetes Service (AKS), read video references from AWS S3 and metadata from DynamoDB, process messages from SQS, and call Azure ML endpoints for model scoring. You will push code to the repository, run the training pipeline to train on the compute cluster, see models appear in the registry, run the deployment pipeline to create or update endpoints, and optionally update Kubernetes ConfigMaps so application pods use the new scoring URIs. This end-to-end flow demonstrates automated, reproducible model training and deployment across AWS (data/messaging) and Azure (ML platform and CI/CD).

---

## Overview And Key Concepts

In this section, we cover the main concepts used in this guide and what the lab focuses on.

This lab gives you hands-on experience building a multi-cloud MLOps system that automates training, registration, and deployment of content-moderation models, and optionally connects them to an application that uses AWS for storage and queues and Azure for ML and orchestration.

The lab focuses on a serverless-style ML workflow: training runs on Azure ML compute clusters (not on the pipeline agent), models are registered automatically in the Azure ML Model Registry, and deployment is driven by Azure DevOps pipelines that deploy to Azure ML online endpoints. The application layer can stay on AWS for data and use Azure only for inference, giving you a clear separation between data (AWS) and ML platform (Azure).

---

### Azure Machine Learning – Workspace, Compute Clusters, and Model Registry

Azure Machine Learning provides a centralized workspace for managing ML assets: compute targets (e.g., CPU clusters), experiments, model registry, and deployments. Compute clusters scale up and down based on job submission, so training runs on dedicated VMs instead of on the CI/CD agent. The Model Registry stores trained models (e.g., `nsfw-detector`, `violence-detector`) with versioning and metadata, forming the single source of truth for deployment.

**Definition:** Managed ML platform that provides workspaces, scalable compute clusters for training jobs, a model registry for versioning, and integration with MLflow for experiment tracking.

**Use Case:** Run training jobs on a `cpu-training-cluster`, track runs with MLflow, and automatically register model artifacts in the registry after successful training so deployment pipelines can deploy a specific version to online endpoints.

**Example:** The training pipeline submits a job with `submit_training_job.py`; the job runs `train_nsfw_model.py` on the cluster, logs metrics via MLflow, and registers the model as `nsfw-detector:3` in the registry; the deployment pipeline then deploys `nsfw-detector:3` to `nsfw-detector-endpoint`.

---

### Azure Machine Learning – Online Endpoints

Azure ML Online Endpoints are managed, HTTP-accessible endpoints that serve model inference. They handle scaling, health probes, and authentication (e.g., key-based), so application code only needs to call a scoring URI with the right payload and key.

**Definition:** Managed real-time inference endpoints that host a registered model version, expose a scoring URI, and support health checks and traffic splitting (e.g., champion/challenger).

**Use Case:** Serve NSFW and violence-detection models to application services (e.g., Deep-Vision) so they can send input to the endpoint and receive risk scores without managing servers or containers.

**Example:** After deployment, `nsfw-detector-endpoint` exposes a scoring URI; the Deep-Vision service sends a POST request with the payload and `MODEL_ENDPOINT_KEY`; the endpoint returns a score used to update DynamoDB and drive policy decisions.

---

### MLflow – Experiment Tracking and Azure ML Backend

MLflow is an open-source platform for tracking experiments, logging parameters and metrics, and managing model artifacts. When used with Azure ML, the tracking URI points to the Azure ML workspace, so runs and registered models appear in Azure ML Studio and the Model Registry.

**Definition:** Experiment-tracking and model-lifecycle tool that logs parameters, metrics, and artifacts; with Azure ML backend, runs and model registration are stored in the Azure ML workspace.

**Use Case:** During training on the compute cluster, log hyperparameters, metrics (e.g., accuracy, loss), and save the model artifact; after the run, the training script registers the model in the Azure ML Model Registry so it can be deployed by the deployment pipeline.

**Example:** `train_nsfw_model.py` sets `mlflow.set_tracking_uri(azureml_uri)`, creates an MLflow run, logs `learning_rate` and `epochs`, logs `val_accuracy`, and calls `mlflow.register_model()` so the model appears under the workspace’s Model Registry with a new version.

---

### Azure DevOps – CI/CD Pipelines for Training and Deployment

Azure DevOps provides source control, variable groups, service connections, and pipelines. Pipelines can run on Microsoft-hosted or self-hosted agents and execute steps (e.g., Azure CLI, Python scripts) to submit jobs to Azure ML and deploy models, without running the actual training on the agent.

**Definition:** CI/CD service that hosts repositories, variable groups, and pipelines; used here to trigger training job submission to Azure ML compute and to run deployment steps that deploy registered models to online endpoints.

**Use Case:** On code push or manual run, the training pipeline installs dependencies and calls `submit_training_job.py` for each model type; after jobs complete and models are registered, the deployment pipeline runs `deploy_model.py` (or equivalent) to create/update endpoints and optionally update Kubernetes ConfigMaps.

**Example:** Running `azure-pipelines-ml-training.yml` submits NSFW and violence training jobs to `cpu-training-cluster`; when both complete, running `azure-pipelines-ml-deployment.yml` deploys the latest `nsfw-detector` and `violence-detector` versions to their endpoints and updates the ConfigMap with the new scoring URIs.

---

### AWS S3 – Object Storage for Application Data

Amazon S3 is object storage for unstructured data such as video files. The application layer (e.g., Ingestion service) uploads videos to an S3 bucket; downstream services (e.g., Deep-Vision) download them for processing and inference.

**Definition:** Cloud object storage for storing and retrieving large binary objects (e.g., video files) with high durability and scalability.

**Use Case:** Store uploaded videos in a dedicated bucket (e.g., `guardian-videos-<account-id>`); application services read from S3 when they need to run inference or process content.

**Scalability:** Videos are stored in a single bucket (or prefix) per environment; Azure ML does not read from S3—application services bridge S3 and Azure ML by sending extracted or referenced content to the endpoints.

---

### AWS SQS – Message Queues for Asynchronous Processing

Amazon SQS provides managed message queues for decoupling producers and consumers. The project uses queues such as `video-processing` and `gpu-processing` to drive which videos are processed and when high-risk items are sent for deeper model inference.

**Definition:** Managed message queue service that enables asynchronous, decoupled processing between services with at-least-once delivery.

**Use Case:** Ingestion pushes message references to SQS; Fast-Screening and Deep-Vision services poll (or are triggered by) queues, process items, and call Azure ML endpoints for scoring; results are written back to DynamoDB.

**Example:** A message in `guardian-gpu-processing` triggers the Deep-Vision service to pull the video from S3, call `nsfw-detector-endpoint` and `violence-detector-endpoint`, and update the corresponding DynamoDB record with risk scores.

---

### AWS DynamoDB – Metadata and Application State

DynamoDB is a managed NoSQL database used for metadata and event records. Tables such as `guardian-videos` store video metadata, status, and risk scores; `guardian-events` can store audit events with TTL.

**Definition:** Managed NoSQL database for low-latency read/write of structured metadata and application state, with optional TTL for event/audit data.

**Use Case:** Single source of truth for video metadata, processing status, and model outputs; Policy Engine and Human-Review services read and write decisions and review state.

**Example:** After Deep-Vision calls Azure ML endpoints, it updates the `guardian-videos` item with `risk_score`, `nsfw_score`, and `violence_score`; the Policy Engine reads these fields to decide allow/block/review and writes the decision back to DynamoDB.

---

### Azure Kubernetes Service (AKS) and ConfigMaps – Runtime Integration

AKS hosts the application microservices (Ingestion, Fast-Screening, Deep-Vision, Policy Engine, etc.) in containers. ConfigMaps store non-secret configuration such as Azure ML endpoint URLs; the deployment pipeline can update the ConfigMap after a new deployment so pods use the latest scoring URIs.

**Definition:** Managed Kubernetes service for running containerized application services; ConfigMaps hold endpoint URLs and other configuration that deployment pipelines update when new model versions are deployed.

**Use Case:** Run Deep-Vision and other services that need to call Azure ML; after the deployment pipeline deploys a new model version, it updates the ConfigMap and restarts the relevant deployments so they use the new endpoints without rebuilding images.

**Example:** ConfigMap `guardian-config` contains `NSFW_MODEL_ENDPOINT` and `VIOLENCE_MODEL_ENDPOINT`; after `azure-pipelines-ml-deployment.yml` runs, a script updates these values and restarts the Deep-Vision deployment so it immediately uses the new scoring URIs.

---

### Cross-Cloud Integration – Data on AWS, ML on Azure

The architecture keeps data and messaging on AWS and ML training, registry, and inference on Azure. Application services (on AKS or elsewhere) use AWS for S3, SQS, and DynamoDB, and use Azure only for calling the ML endpoints and for CI/CD (Azure DevOps and Azure ML).

**Definition:** Separation of responsibilities: AWS for storage, queues, and application metadata; Azure for ML workspace, compute, registry, endpoints, and pipeline orchestration; application code connects both via configuration (endpoint URLs, keys, and AWS credentials).

**Use Case:** Optimize cost and capability—use AWS for high-scale object storage and queues, and Azure for a full-featured ML platform and managed endpoints; keep a single application codebase that talks to both clouds via environment variables and SDKs.

**Example:** Video upload → S3 + DynamoDB (AWS); processing triggered by SQS (AWS); Deep-Vision runs on AKS, reads from S3/DynamoDB, calls Azure ML endpoints for scores, writes results back to DynamoDB; training and deployment are fully on Azure via Azure DevOps and Azure ML.

---

## Key Benefits

- **Automation:** Code commit triggers or manually run pipelines that train on the cluster, register models, and deploy to endpoints—no manual promotion or server management.
- **Consistency:** Every deployment uses the same pipeline and the same registry versions; rollbacks can target a previous model version.
- **Explainability and traceability:** MLflow and Azure ML Studio provide run history, metrics, and model lineage; registry versions tie deployments to specific training runs.
- **Scalability:** Training scales on Azure ML compute clusters; inference scales via managed endpoints; application layer scales independently on AWS and AKS.
- **Speed:** New model versions move from code to production in one pipeline run; application pods pick up new endpoints via ConfigMap updates and restarts.
- **Multi-cloud flexibility:** Use AWS for data and messaging and Azure for ML and CI/CD, with clear boundaries and minimal coupling.

---

**Next steps:** See [README.md](../README.md) for setup, [COMPUTE_CLUSTER_WORKFLOW.md](./COMPUTE_CLUSTER_WORKFLOW.md) for the Git-to-training flow, and [AZURE_DEVOPS_ML_INTEGRATION_GUIDE.md](./AZURE_DEVOPS_ML_INTEGRATION_GUIDE.md) for pipeline and variable configuration.
