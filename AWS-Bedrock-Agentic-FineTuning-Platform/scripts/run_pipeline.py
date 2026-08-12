#!/usr/bin/env python3
"""Runs one scenario end-to-end: split -> upload -> fine-tune -> deploy -> infer -> validate.

Usage: run_pipeline.py --scenario {id} [--skip-training] [--force-retrain]

--skip-training reuses an existing completed custom model for the scenario instead of
launching a new fine-tune job. --force-retrain launches a new job even if a completed
model already exists (requires typed approval, same as a fresh launch).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import boto3

# `python scripts/run_pipeline.py` puts this file's directory on sys.path, so this
# imports the sibling script directly rather than duplicating its cost-table logic.
import print_cost_estimate as cost_cli
from bedrock_platform.aws.deployment_client import DeploymentClient
from bedrock_platform.aws.finetune_client import APPROVAL_TOKEN, FinetuneClient, RetrainRefusedError
from bedrock_platform.aws.inference_client import InferenceClient
from bedrock_platform.aws.naming import bedrock_role_arn, data_bucket_name, deployment_name
from bedrock_platform.aws.s3_client import S3Client
from bedrock_platform.aws.session import get_session
from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.config.scenario_loader import load_scenarios
from bedrock_platform.config.settings import Settings
from bedrock_platform.data.splitter import split_records
from bedrock_platform.validation.schema_guard import validate_output
from bedrock_platform.validation.violation import SchemaViolation

REPO_ROOT = Path(__file__).resolve().parent.parent
TRAINING_JOB_POLL_SECONDS = 60
DEPLOYMENT_POLL_SECONDS = 15
DEPLOYMENT_MAX_WAIT_SECONDS = 1800


def _find_scenario(scenario_id: str) -> ScenarioConfig:
    for scenario in load_scenarios():
        if scenario.id == scenario_id:
            if not scenario.enabled:
                print(
                    f"ERROR: scenario {scenario_id!r} is disabled in its config.", file=sys.stderr
                )
                sys.exit(1)
            return scenario
    print(f"ERROR: unknown scenario id {scenario_id!r}.", file=sys.stderr)
    sys.exit(1)


def _split_dataset(scenario: ScenarioConfig) -> tuple[Path, Path]:
    """Leak-free deterministic split — see bedrock_platform.data.splitter for why a
    positional tail slice was wrong for these datasets. No RNG; reruns of the same
    dataset always split identically."""
    lines = scenario.dataset_path.read_text().splitlines()
    records = [line for line in lines if line.strip()]

    train_records, val_records = split_records(records, scenario.validation_split)

    split_dir = REPO_ROOT / "artifacts" / scenario.id / "splits"
    split_dir.mkdir(parents=True, exist_ok=True)

    train_path = split_dir / "train.jsonl"
    val_path = split_dir / "validation.jsonl"
    train_path.write_text("\n".join(train_records) + "\n")
    val_path.write_text("\n".join(val_records) + "\n")

    print(
        f"Split {len(records)} records -> {len(train_records)} train / "
        f"{len(val_records)} validation"
    )
    return train_path, val_path


def _block_on_typed_approval() -> str | None:
    typed = input(f"Type '{APPROVAL_TOKEN}' to proceed, anything else to abort: ").strip()
    return typed if typed == APPROVAL_TOKEN else None


def _launch_finetune(
    scenario: ScenarioConfig,
    settings: Settings,
    session: boto3.Session,
    force_retrain: bool,
) -> str:
    train_path, val_path = _split_dataset(scenario)

    bucket = data_bucket_name(settings.project_suffix, settings.aws_region)
    s3_client = S3Client(bucket=bucket, session=session)
    train_key = s3_client.upload_training_data(scenario.id, train_path)
    val_key = s3_client.upload_validation_data(scenario.id, val_path)
    print(f"Uploaded to s3://{bucket}/{train_key} and s3://{bucket}/{val_key}")

    estimate = cost_cli._estimate_scenario_cost(scenario)
    cost_cli.print_cost_table([estimate])

    typed_token = _block_on_typed_approval()
    if typed_token is None:
        print("Not approved — aborting before any fine-tune job is launched.")
        sys.exit(1)

    finetune_client = FinetuneClient(project_suffix=settings.project_suffix, session=session)
    role_arn = bedrock_role_arn(session, settings.project_suffix)
    output_s3_uri = f"s3://{bucket}/output/{scenario.id}/"

    try:
        response = finetune_client.create_model_customization_job(
            scenario_id=scenario.id,
            base_model_id=scenario.base_model_id,
            role_arn=role_arn,
            training_data_s3_uri=f"s3://{bucket}/{train_key}",
            validation_data_s3_uri=f"s3://{bucket}/{val_key}",
            output_s3_uri=output_s3_uri,
            epochs=scenario.epochs,
            force_retrain=force_retrain,
            approval_token=typed_token if force_retrain else None,
        )
    except RetrainRefusedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Pass --force-retrain to retrain (still requires typed approval).", file=sys.stderr)
        sys.exit(1)

    job_arn = response["jobArn"]
    print(f"Launched fine-tune job: {job_arn}")

    last_status = None
    while True:
        job = finetune_client.get_model_customization_job(job_arn)
        status = job["status"]
        if status != last_status:
            print(f"Job status: {status}")
            last_status = status
        if status == "Completed":
            return job["outputModelArn"]
        if status in ("Failed", "Stopped"):
            print(
                f"ERROR: fine-tune job ended with status {status}: {job.get('failureMessage')}",
                file=sys.stderr,
            )
            sys.exit(1)
        time.sleep(TRAINING_JOB_POLL_SECONDS)


def _reuse_existing_model(
    scenario: ScenarioConfig, settings: Settings, session: boto3.Session
) -> str:
    finetune_client = FinetuneClient(project_suffix=settings.project_suffix, session=session)
    models = finetune_client.find_custom_models(scenario.id)
    if not models:
        print(
            f"ERROR: --skip-training passed but no custom model matches prefix "
            f"{finetune_client.scenario_model_prefix(scenario.id)!r}.",
            file=sys.stderr,
        )
        sys.exit(1)

    chosen = models[0]
    if len(models) > 1:
        # Newest wins, but say so — silently picking among several models is how a demo
        # ends up reporting numbers from a model nobody meant to test.
        print(f"Found {len(models)} custom models for {scenario.id!r}; using the newest:")
        for model in models:
            marker = "->" if model is chosen else "  "
            print(f"  {marker} {model['modelName']}  ({model.get('creationTime')})")
    print(f"Reusing existing custom model: {chosen['modelArn']}")
    return str(chosen["modelArn"])


def _deploy_model(
    scenario: ScenarioConfig, settings: Settings, session: boto3.Session, custom_model_arn: str
) -> str:
    deployment_client = DeploymentClient(session=session)
    name = deployment_name(settings.project_suffix, scenario.id)

    # Custom Model on-Demand deployments cost $0/hr idle, so a live one is worth reusing
    # rather than replacing. Creating a second deployment under the same name fails, and
    # creating one under a new name would leave the old deployment orphaned — still
    # holding the model open against teardown.
    for existing in deployment_client.list_custom_model_deployments():
        if existing["modelArn"] == custom_model_arn and existing["status"] == "Active":
            print(
                f"Reusing existing Active deployment: "
                f"{existing['customModelDeploymentName']} "
                f"({existing['customModelDeploymentArn']})"
            )
            return str(existing["customModelDeploymentArn"])

    response = deployment_client.create_custom_model_deployment(name, custom_model_arn)
    deployment_arn = response["customModelDeploymentArn"]
    print(f"Created deployment: {deployment_arn}")

    waited = 0
    last_status = None
    while True:
        deployment = deployment_client.get_custom_model_deployment(deployment_arn)
        status = deployment["status"]
        if status != last_status:
            print(f"Deployment status: {status}")
            last_status = status
        if status == "Active":
            return deployment_arn
        if status == "Failed":
            print(f"ERROR: deployment failed: {deployment.get('failureMessage')}", file=sys.stderr)
            sys.exit(1)
        if waited >= DEPLOYMENT_MAX_WAIT_SECONDS:
            print("ERROR: deployment did not become Active in time.", file=sys.stderr)
            sys.exit(1)
        time.sleep(DEPLOYMENT_POLL_SECONDS)
        waited += DEPLOYMENT_POLL_SECONDS


def _run_inference(
    scenario: ScenarioConfig, session: boto3.Session, deployment_arn: str
) -> list[dict]:
    inference_client = InferenceClient(session=session)
    results = []
    for prompt in scenario.sample_prompts:
        base = inference_client.invoke_base_model(
            scenario.base_inference_model_id,
            scenario.system_prompt,
            prompt,
            scenario.max_output_tokens,
        )
        tuned = inference_client.invoke_tuned_model(
            deployment_arn, scenario.system_prompt, prompt, scenario.max_output_tokens
        )

        print(f"\nPrompt: {prompt}")
        print(f"  Base  ({base.latency_ms}ms): {base.text[:200]}")
        print(f"  Tuned ({tuned.latency_ms}ms): {tuned.text[:200]}")

        verdict = validate_output(scenario, tuned.text) if scenario.output_schema_ref else None
        if verdict is None:
            print("  Schema verdict: n/a (no strict schema configured for this scenario)")
        elif isinstance(verdict, SchemaViolation):
            print(f"  Schema verdict: VIOLATION CAUGHT — {verdict.error_path}")
        else:
            print("  Schema verdict: valid")

        results.append(
            {
                "prompt": prompt,
                "base": base.model_dump(),
                "tuned": tuned.model_dump(),
                "schema_valid": (
                    None if verdict is None else not isinstance(verdict, SchemaViolation)
                ),
                "verdict": None if verdict is None else verdict.model_dump(),
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--skip-training", action="store_true")
    parser.add_argument("--force-retrain", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    session = get_session()
    scenario = _find_scenario(args.scenario)

    if args.skip_training:
        custom_model_arn = _reuse_existing_model(scenario, settings, session)
    else:
        custom_model_arn = _launch_finetune(
            scenario, settings, session, force_retrain=args.force_retrain
        )

    deployment_arn = _deploy_model(scenario, settings, session, custom_model_arn)
    results = _run_inference(scenario, session, deployment_arn)

    artifacts_dir = REPO_ROOT / "artifacts" / scenario.id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    results_path = artifacts_dir / "results.json"
    finetune_client = FinetuneClient(project_suffix=settings.project_suffix, session=session)
    results_path.write_text(
        json.dumps(
            {
                "scenario_id": scenario.id,
                "region": settings.aws_region,
                "base_model_id": scenario.base_model_id,
                "base_inference_model_id": scenario.base_inference_model_id,
                "job_arn": finetune_client.job_arn_for_model(custom_model_arn),
                "custom_model_arn": custom_model_arn,
                "deployment_arn": deployment_arn,
                "results": results,
            },
            indent=2,
        )
    )
    print(f"\nWrote results to {results_path}")
    print("Resources are live and billing. Run `make teardown` when done.")


if __name__ == "__main__":
    main()
