import os

from bedrock_platform.aws.finetune_client import FinetuneClient
from bedrock_platform.aws.session import get_session


def test_job_status_completed(run_results: dict) -> None:
    suffix = os.environ["PROJECT_SUFFIX"]

    # Identify the job by the ARN the run actually recorded, not by rebuilding the
    # canonical job name. Bedrock reserves a job name permanently, so a scenario that
    # took several attempts has earlier Stopped/Failed jobs holding the base names —
    # rebuilding the name can resolve to one of those instead of the run under test.
    client = FinetuneClient(project_suffix=suffix, session=get_session())
    job = client.get_model_customization_job(run_results["job_arn"])
    assert job["status"] == "Completed"


def test_custom_model_arn_resolves(run_results: dict) -> None:
    suffix = os.environ["PROJECT_SUFFIX"]
    client = FinetuneClient(project_suffix=suffix, session=get_session())

    custom_model_arn = run_results["custom_model_arn"]
    matching = [m for m in client.list_custom_models() if m["modelArn"] == custom_model_arn]
    assert len(matching) == 1, f"custom model {custom_model_arn} does not resolve"
