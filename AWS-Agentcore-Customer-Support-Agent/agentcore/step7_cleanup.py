"""
Step 7: Complete Resource Cleanup

Deletes all AWS resources created across Steps 1-6 to avoid ongoing charges.
Runs non-interactively (no manual confirmation prompts).
"""
import boto3
from botocore.exceptions import ClientError

from agentcore import AWS_REGION as REGION
from agentcore.utils import (
    delete_agentcore_runtime_execution_role,
    delete_ssm_parameter,
    cleanup_cognito_resources,
    get_customer_support_secret,
    delete_customer_support_secret,
    agentcore_memory_cleanup,
    gateway_target_cleanup,
    runtime_resource_cleanup,
    delete_observability_resources,
    local_file_cleanup,
    get_ssm_parameter,
)

def empty_s3_buckets() -> list[str]:
    """Find and empty all project-related S3 buckets (without deleting them).

    Buckets are only emptied so CloudFormation can delete them during stack teardown.
    Deleting buckets here would break the CF Lambda delete handler that needs them
    for KB cleanup.
    """
    s3 = boto3.client("s3", region_name=REGION)
    cfn = boto3.client("cloudformation", region_name=REGION)
    buckets_to_clean: list[str] = []

    # Find buckets via CloudFormation
    try:
        resp = cfn.list_stacks(
            StackStatusFilter=[
                "CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE",
                "ROLLBACK_COMPLETE", "DELETE_FAILED",
            ]
        )
        for stack in resp.get("StackSummaries", []):
            name = stack["StackName"]
            if "CustomerSupportStack" in name or "customer-support" in name.lower() or "customersupport" in name.lower():
                try:
                    resources = cfn.list_stack_resources(StackName=name)
                    for r in resources.get("StackResourceSummaries", []):
                        if r["ResourceType"] == "AWS::S3::Bucket":
                            buckets_to_clean.append(r["PhysicalResourceId"])
                except Exception:
                    pass
    except Exception as e:
        print(f"  WARNING: Could not list CloudFormation stacks: {e}")

    # Also find by naming pattern
    try:
        for b in s3.list_buckets().get("Buckets", []):
            bn = b["Name"]
            if any(p in bn.lower() for p in ["agentcore", "customer-support", "customersupport", "bedrock-kb", "knowledgebase"]):
                if bn not in buckets_to_clean:
                    buckets_to_clean.append(bn)
    except Exception as e:
        print(f"  WARNING: Could not list S3 buckets: {e}")

    for bucket_name in buckets_to_clean:
        print(f"  Emptying bucket: {bucket_name}")
        try:
            s3.head_bucket(Bucket=bucket_name)
        except ClientError:
            print(f"    Bucket not found — skipping.")
            continue
        try:
            paginator = s3.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=bucket_name):
                for v in page.get("Versions", []):
                    s3.delete_object(Bucket=bucket_name, Key=v["Key"], VersionId=v["VersionId"])
                for m in page.get("DeleteMarkers", []):
                    s3.delete_object(Bucket=bucket_name, Key=m["Key"], VersionId=m["VersionId"])
            paginator2 = s3.get_paginator("list_objects_v2")
            for page in paginator2.paginate(Bucket=bucket_name):
                objs = page.get("Contents", [])
                if objs:
                    s3.delete_objects(Bucket=bucket_name, Delete={"Objects": [{"Key": o["Key"]} for o in objs]})
            print(f"    Emptied.")
        except Exception as e:
            print(f"    WARNING: {e}")

    return buckets_to_clean


def delete_cloudformation_stacks() -> None:
    """Delete all CustomerSupport CloudFormation stacks and wait for completion."""
    import time
    cfn = boto3.client("cloudformation", region_name=REGION)
    try:
        resp = cfn.list_stacks(
            StackStatusFilter=[
                "CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE",
                "ROLLBACK_COMPLETE", "DELETE_FAILED",
            ]
        )
        stacks = [
            s["StackName"] for s in resp.get("StackSummaries", [])
            if "CustomerSupportStack" in s["StackName"]
            or "customer-support" in s["StackName"].lower()
            or "customersupport" in s["StackName"].lower()
        ]
        if not stacks:
            print("  No CustomerSupport CloudFormation stacks found.")
            return
        for stack_name in stacks:
            print(f"  Deleting stack: {stack_name}")
            cfn.delete_stack(StackName=stack_name)
            waiter = cfn.get_waiter("stack_delete_complete")
            try:
                waiter.wait(StackName=stack_name, WaiterConfig={"Delay": 15, "MaxAttempts": 120})
                print(f"    Deleted.")
            except Exception:
                print(f"    Taking longer than expected — check CloudFormation console.")
    except Exception as e:
        print(f"  WARNING: {e}")


def delete_codebuild_projects() -> None:
    cb = boto3.client("codebuild", region_name=REGION)
    iam = boto3.client("iam", region_name=REGION)
    try:
        projects = cb.list_projects().get("projects", [])
        targets = [p for p in projects if any(k in p.lower() for k in ["agentcore", "customer-support", "bedrock-agentcore"])]
        for p in targets:
            cb.delete_project(name=p)
            print(f"  Deleted CodeBuild project: {p}")
        if not targets:
            print("  No AgentCore CodeBuild projects found.")
    except Exception as e:
        print(f"  WARNING: {e}")

    # Delete the CodeBuild IAM role created by the starter toolkit
    try:
        roles = iam.list_roles().get("Roles", [])
        cb_roles = [r["RoleName"] for r in roles if "AmazonBedrockAgentCoreSDKCodeBuild" in r["RoleName"]]
        for role_name in cb_roles:
            for policy in iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", []):
                iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
            for policy in iam.list_role_policies(RoleName=role_name).get("PolicyNames", []):
                iam.delete_role_policy(RoleName=role_name, PolicyName=policy)
            iam.delete_role(RoleName=role_name)
            print(f"  Deleted CodeBuild IAM role: {role_name}")
    except Exception as e:
        print(f"  WARNING CodeBuild IAM role: {e}")


def delete_ecr_repositories() -> None:
    ecr = boto3.client("ecr", region_name=REGION)
    try:
        repos = ecr.describe_repositories().get("repositories", [])
        targets = [r for r in repos if any(k in r["repositoryName"].lower() for k in ["agentcore", "customer-support", "customer_support"])]
        for r in targets:
            name = r["repositoryName"]
            image_ids = ecr.list_images(repositoryName=name).get("imageIds", [])
            if image_ids:
                ecr.batch_delete_image(repositoryName=name, imageIds=image_ids)
            ecr.delete_repository(repositoryName=name, force=True)
            print(f"  Deleted ECR repository: {name}")
        if not targets:
            print("  No AgentCore ECR repositories found.")
    except Exception as e:
        print(f"  WARNING: {e}")


def _delete_s3_vectors(account_id: str) -> None:
    """Delete all project S3 Vectors indexes and buckets."""
    s3vectors = boto3.client("s3vectors", region_name=REGION)
    base_bucket_prefix = f"{account_id}-{REGION}-kb-vector-bucket"
    try:
        all_buckets = s3vectors.list_vector_buckets().get("vectorBuckets", [])
        project_buckets = [b["vectorBucketName"] for b in all_buckets
                           if b.get("vectorBucketName", "").startswith(base_bucket_prefix)]
    except Exception:
        project_buckets = [base_bucket_prefix]

    for vb in project_buckets:
        try:
            indexes = s3vectors.list_indexes(vectorBucketName=vb).get("indexes", [])
            for idx in indexes:
                s3vectors.delete_index(vectorBucketName=vb, indexName=idx["indexName"])
                print(f"  Deleted S3 Vectors index: {idx['indexName']} (bucket: {vb})")
            s3vectors.delete_vector_bucket(vectorBucketName=vb)
            print(f"  Deleted S3 Vectors bucket: {vb}")
        except Exception as e:
            if "NoSuchBucket" not in str(e) and "does not exist" not in str(e).lower():
                print(f"  WARNING S3 Vectors ({vb}): {e}")


def _set_data_sources_retain_policy(bedrock, kb_id: str, kb_name: str) -> None:
    """Set dataDeletionPolicy=RETAIN on all data sources so KB deletion skips vector store cleanup."""
    try:
        ds_list = bedrock.list_data_sources(knowledgeBaseId=kb_id).get("dataSourceSummaries", [])
        for ds in ds_list:
            ds_id = ds["dataSourceId"]
            try:
                ds_detail = bedrock.get_data_source(knowledgeBaseId=kb_id, dataSourceId=ds_id)["dataSource"]
                update_kwargs = {
                    "knowledgeBaseId": kb_id,
                    "dataSourceId": ds_id,
                    "name": ds_detail["name"],
                    "dataSourceConfiguration": ds_detail["dataSourceConfiguration"],
                    "dataDeletionPolicy": "RETAIN",
                }
                if "vectorIngestionConfiguration" in ds_detail:
                    update_kwargs["vectorIngestionConfiguration"] = ds_detail["vectorIngestionConfiguration"]
                if "description" in ds_detail:
                    update_kwargs["description"] = ds_detail["description"]
                if "serverSideEncryptionConfiguration" in ds_detail:
                    update_kwargs["serverSideEncryptionConfiguration"] = ds_detail["serverSideEncryptionConfiguration"]
                bedrock.update_data_source(**update_kwargs)
                print(f"    Set RETAIN policy on data source {ds_id} ({kb_name})")
            except Exception as e:
                if "ResourceNotFoundException" not in str(e):
                    print(f"    WARNING updating data source {ds_id}: {e}")
    except Exception as e:
        if "ResourceNotFoundException" not in str(e):
            print(f"    WARNING listing data sources for {kb_name}: {e}")


def delete_knowledge_bases() -> None:
    """Delete Bedrock Knowledge Bases and S3 Vectors resources.

    Correct deletion sequence to avoid DELETE_UNSUCCESSFUL:
      1. Set dataDeletionPolicy=RETAIN on all data sources (prevents KB from
         trying to clean up vector store data that may already be gone)
      2. Delete the KB itself
      3. Poll until fully gone
      4. Delete S3 Vectors indexes and buckets (clean up storage separately)
    """
    import time
    bedrock = boto3.client("bedrock-agent", region_name=REGION)
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    try:
        kbs = bedrock.list_knowledge_bases().get("knowledgeBaseSummaries", [])
        targets = [kb for kb in kbs if account_id in kb.get("name", "") or REGION in kb.get("name", "")]
    except Exception as e:
        print(f"  WARNING KB: {e}")
        return

    if not targets:
        print("  No project Knowledge Bases found.")
        _delete_s3_vectors(account_id)
        return

    print(f"  Found {len(targets)} KB(s) to delete.")

    # Step 1: Set RETAIN policy on all data sources so KB deletion won't fail
    #         trying to clean up vector store data
    print("  Setting dataDeletionPolicy=RETAIN on all data sources...")
    for kb in targets:
        _set_data_sources_retain_policy(bedrock, kb["knowledgeBaseId"], kb["name"])

    # Step 2: Delete the KBs
    kb_ids = []
    retried = set()
    for kb in targets:
        kb_id = kb["knowledgeBaseId"]
        try:
            bedrock.delete_knowledge_base(knowledgeBaseId=kb_id)
            print(f"  Deletion triggered for KB: {kb['name']} ({kb_id})")
        except Exception as e:
            print(f"  WARNING KB {kb_id}: {e}")
        kb_ids.append(kb_id)

    # Step 3: Poll until all KBs are gone (up to 180s)
    if kb_ids:
        print("  Waiting for KB deletion to complete...")
        for attempt in range(36):  # up to 180s
            time.sleep(5)
            remaining = bedrock.list_knowledge_bases().get("knowledgeBaseSummaries", [])
            still_present = [k for k in remaining if k["knowledgeBaseId"] in kb_ids]
            if not still_present:
                print("  All KBs fully deleted.")
                break

            # Retry stuck KBs once: set RETAIN policy again and re-trigger deletion
            for k in still_present:
                if k["status"] == "DELETE_UNSUCCESSFUL" and k["knowledgeBaseId"] not in retried:
                    retried.add(k["knowledgeBaseId"])
                    print(f"    Retrying stuck KB: {k['name']} (setting RETAIN + re-deleting)")
                    _set_data_sources_retain_policy(bedrock, k["knowledgeBaseId"], k["name"])
                    try:
                        bedrock.delete_knowledge_base(knowledgeBaseId=k["knowledgeBaseId"])
                    except Exception:
                        pass

            if attempt % 4 == 0:
                statuses = [f"{k['name']}={k['status']}" for k in still_present]
                print(f"    Status: {statuses} — waiting...")
        else:
            print("  WARNING: KB did not finish deleting within 180s.")

    # Step 4: Clean up S3 Vectors storage separately
    _delete_s3_vectors(account_id)


def delete_cloudwatch_log_groups() -> None:
    logs = boto3.client("logs", region_name=REGION)
    patterns = ["/aws/bedrock/agentcore", "/aws/lambda/bedrock-agentcore", "customer_support_agent", "customer-support-agent"]
    count = 0
    try:
        paginator = logs.get_paginator("describe_log_groups")
        for page in paginator.paginate():
            for lg in page.get("logGroups", []):
                name = lg["logGroupName"]
                if any(p in name.lower() for p in patterns):
                    logs.delete_log_group(logGroupName=name)
                    print(f"  Deleted log group: {name}")
                    count += 1
        if count == 0:
            print("  No matching log groups found.")
    except Exception as e:
        print(f"  WARNING: {e}")


SSM_PARAMS = [
    "/app/customersupport/agentcore/runtime_arn",
    "/app/customersupport/agentcore/memory_id",
    "/app/customersupport/agentcore/gateway_id",
    "/app/customersupport/agentcore/gateway_name",
    "/app/customersupport/agentcore/gateway_arn",
    "/app/customersupport/agentcore/gateway_url",
    "/app/customersupport/agentcore/client_id",
    "/app/customersupport/agentcore/client_secret",
    "/app/customersupport/agentcore/cognito_domain",
    "/app/customersupport/agentcore/cognito_discovery_url",
    "/app/customersupport/agentcore/gateway_iam_role",
]


def run(dry_run: bool = False) -> None:
    """Run Step 7: delete all project resources. Pass dry_run=True to preview only.

    Deletion order matters:
      1. Empty S3 buckets   — CloudFormation cannot delete non-empty buckets
      2. Delete CF stack     — Lambda Delete handler does KB → wait → S3 Vectors → SSM (KB)
      3. KB fallback         — catch any KB the CF handler missed
      4. AgentCore Memory
      5. AgentCore Runtime
      6. AgentCore Gateway
      7. CodeBuild + ECR
      8. Observability       — CloudWatch log groups
      9. Remaining glue      — IAM roles, SSM params, Cognito, Secrets Manager, local files
     10. Delete S3 buckets   — safe now that CF and KB cleanup are done
    """
    print("\n=== Step 7: Complete Resource Cleanup ===")
    if dry_run:
        print("  DRY RUN mode — no resources will be deleted.\n")

    # ── 1 ── Empty S3 first so CloudFormation can delete the bucket
    print("\n[Step 1/10] Emptying S3 buckets (required before CloudFormation stack deletion)...")
    if not dry_run:
        empty_s3_buckets()
    else:
        print("  [DRY RUN] Would empty project S3 buckets.")

    # ── 2 ── CloudFormation stack deletion: the Lambda Delete handler handles
    #         KB deletion → poll until gone → S3 Vectors cleanup → SSM KB params
    print("\n[Step 2/10] Deleting CloudFormation prerequisite stack...")
    print("  (Lambda Delete handler: KB → waits for deletion → S3 Vectors → SSM KB params)")
    if not dry_run:
        delete_cloudformation_stacks()
    else:
        print("  [DRY RUN] Would delete CloudFormation stack and wait for completion.")

    # ── 3 ── Fallback: delete any KB the CF handler missed (e.g. already-stuck KBs)
    print("\n[Step 3/10] Knowledge Base fallback cleanup (catches any CF-missed KBs)...")
    if not dry_run:
        delete_knowledge_bases()
    else:
        print("  [DRY RUN] Would check for and delete any remaining KBs and S3 Vectors.")

    # ── 4 ── AgentCore Memory
    print("\n[Step 4/10] Deleting AgentCore Memory resource...")
    if not dry_run:
        try:
            memory_id = get_ssm_parameter("/app/customersupport/agentcore/memory_id")
            agentcore_memory_cleanup(memory_id)
            print("  Memory deleted.")
        except Exception as e:
            print(f"  Memory: {e}")
    else:
        print("  [DRY RUN] Would delete AgentCore Memory resource.")

    # ── 5 ── AgentCore Runtime
    print("\n[Step 5/10] Deleting AgentCore Runtime endpoint...")
    if not dry_run:
        try:
            runtime_arn = get_ssm_parameter("/app/customersupport/agentcore/runtime_arn")
            runtime_resource_cleanup(runtime_arn)
            print("  Runtime endpoint deleted.")
        except Exception as e:
            print(f"  Runtime: {e}")
    else:
        print("  [DRY RUN] Would delete AgentCore Runtime endpoint.")

    # ── 6 ── AgentCore Gateway
    print("\n[Step 6/10] Deleting AgentCore Gateway and targets...")
    if not dry_run:
        try:
            gateway_id = get_ssm_parameter("/app/customersupport/agentcore/gateway_id")
            gateway_target_cleanup(gateway_id)
            print("  Gateway deleted.")
        except Exception as e:
            print(f"  Gateway: {e}")
    else:
        print("  [DRY RUN] Would delete AgentCore Gateway and targets.")

    # ── 7 ── Build / container artifacts
    print("\n[Step 7/10] Deleting CodeBuild projects and ECR repositories...")
    if not dry_run:
        delete_codebuild_projects()
        delete_ecr_repositories()
    else:
        print("  [DRY RUN] Would delete CodeBuild projects and ECR repositories.")

    # ── 8 ── Observability
    print("\n[Step 8/10] Deleting CloudWatch log groups and observability resources...")
    if not dry_run:
        delete_cloudwatch_log_groups()
        try:
            delete_observability_resources()
        except Exception as e:
            print(f"  WARNING: {e}")
    else:
        print("  [DRY RUN] Would delete CloudWatch log groups.")

    # ── 9 ── IAM, SSM, Cognito, Secrets Manager, local files
    print("\n[Step 9/10] Deleting IAM roles, SSM parameters, Cognito, and Secrets Manager...")
    if not dry_run:
        try:
            delete_agentcore_runtime_execution_role()
            print("  IAM execution role deleted.")
        except Exception as e:
            print(f"  WARNING IAM role: {e}")

        for param in SSM_PARAMS:
            try:
                delete_ssm_parameter(param)
                print(f"  Deleted SSM: {param}")
            except ClientError as e:
                if e.response["Error"]["Code"] != "ParameterNotFound":
                    print(f"  WARNING: {param}: {e}")

        try:
            import json
            secret_value = get_customer_support_secret()
            if secret_value:
                cs = json.loads(secret_value)
                cleanup_cognito_resources(cs["pool_id"])
                print("  Cognito resources deleted.")
        except Exception as e:
            print(f"  WARNING Cognito: {e}")

        try:
            delete_customer_support_secret()
            print("  Secrets Manager secret deleted.")
        except Exception as e:
            print(f"  WARNING Secrets Manager: {e}")

        try:
            local_file_cleanup()
            print("  Local config files cleaned up.")
        except Exception as e:
            print(f"  WARNING local cleanup: {e}")

    # ── 10 ── Delete emptied S3 buckets (safe now that CF and KB are gone)
    print("\n[Step 10/10] Deleting emptied S3 buckets...")
    if not dry_run:
        s3 = boto3.client("s3", region_name=REGION)
        buckets_to_delete: list[str] = []
        try:
            for b in s3.list_buckets().get("Buckets", []):
                bn = b["Name"]
                if any(p in bn.lower() for p in ["agentcore", "customer-support", "customersupport", "bedrock-kb", "knowledgebase"]):
                    buckets_to_delete.append(bn)
        except Exception as e:
            print(f"  WARNING listing buckets: {e}")
        if not buckets_to_delete:
            print("  No project S3 buckets remaining.")
        for bucket_name in buckets_to_delete:
            try:
                s3.delete_bucket(Bucket=bucket_name)
                print(f"  Deleted bucket: {bucket_name}")
            except Exception as e:
                print(f"  WARNING deleting {bucket_name}: {e}")
    else:
        print("  [DRY RUN] Would delete emptied project S3 buckets.")

    print("\n=== Step 7 complete — all resources cleaned up ===\n")
