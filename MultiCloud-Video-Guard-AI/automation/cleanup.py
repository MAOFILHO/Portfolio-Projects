"""
MultiCloud MLOps - Resource Cleanup
Automates Section 14 of the manual guide.

Uses the repo's own aws_resource_cleanup.sh for AWS teardown,
and az CLI for Azure teardown. Both require explicit confirmation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.config import config
from automation.utils.shell import get_logger, run, run_or_skip, step

log = get_logger("cleanup")


def _confirm(prompt: str) -> bool:
    answer = input(f"\n{prompt} [yes/no]: ").strip().lower()
    return answer == "yes"


def delete_azure() -> None:
    step("14. Delete Azure Resources")
    rg = config.azure.resource_group

    if not _confirm(
        f"⚠  Delete Azure resource group '{rg}'\n"
        f"   (AKS, ACR, ML workspace, endpoints — everything)?"
    ):
        log.info("Skipping Azure cleanup")
        return

    # Delete ML endpoints first (avoids lingering compute charges)
    for ep in (config.ml.nsfw_endpoint_name, config.ml.violence_endpoint_name):
        run_or_skip(
            ["az", "ml", "online-endpoint", "delete",
             "--name", ep, "--resource-group", rg,
             "--workspace-name", config.ml.workspace_name, "--yes"],
            description=f"Delete endpoint: {ep}",
        )

    # Delete entire resource group (async)
    run_or_skip(
        ["az", "group", "delete", "--name", rg, "--yes", "--no-wait"],
        description=f"Delete resource group {rg}",
    )
    log.info("✅ Azure deletion initiated (async).")
    log.info("   Monitor: https://portal.azure.com → Resource groups → %s", rg)


def delete_aws() -> None:
    step("14. Delete AWS Resources")

    script = config.project_root / "aws_resource_cleanup.sh"
    if not script.exists():
        script = config.project_root / "resource_cleanup.sh"

    if not _confirm(
        "⚠  Delete ALL AWS resources (S3, SQS, DynamoDB) for this project?"
    ):
        log.info("Skipping AWS cleanup")
        return

    if script.exists():
        script.chmod(0o755)
        run(["bash", str(script)], cwd=config.project_root,
            description="aws_resource_cleanup.sh")
    else:
        log.warning("Cleanup script not found — deleting resources manually")
        from automation.utils.shell import aws
        account_id = aws("sts", "get-caller-identity", "--query", "Account", "--output", "text")
        bucket = f"guardian-videos-{account_id[:8]}"
        run_or_skip(["aws", "s3", "rm", f"s3://{bucket}", "--recursive"],
                    description=f"Empty s3://{bucket}")
        run_or_skip(["aws", "s3api", "delete-bucket", "--bucket", bucket],
                    description=f"Delete s3://{bucket}")
        for q in ("guardian-video-processing", "guardian-gpu-processing"):
            url_r = run(["aws", "sqs", "get-queue-url", "--queue-name", q,
                         "--query", "QueueUrl", "--output", "text"],
                        capture=True, check=False)
            if url_r.returncode == 0:
                run_or_skip(["aws", "sqs", "delete-queue", "--queue-url", url_r.stdout.strip()])
        for t in ("guardian-videos", "guardian-events"):
            run_or_skip(["aws", "dynamodb", "delete-table", "--table-name", t])

    log.info("✅ AWS resources deleted")


def cleanup_all() -> None:
    log.info("=" * 62)
    log.info("  Resource Cleanup  (Section 14)")
    log.info("=" * 62)
    delete_azure()
    delete_aws()
    log.info("=" * 62)
    log.info("  ✅ Cleanup complete. Verify in Azure Portal & AWS Console.")
    log.info("=" * 62)


if __name__ == "__main__":
    cleanup_all()
