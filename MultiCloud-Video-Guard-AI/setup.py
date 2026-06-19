#!/usr/bin/env python3
"""
MultiCloud MLOps - Setup Orchestrator

Usage:
  python setup.py                      # Full end-to-end setup
  python setup.py --stage aws          # AWS only  (Section 7)
  python setup.py --stage azure        # Azure infra only  (Section 8)
  python setup.py --stage images       # Docker build & push  (Section 9)
  python setup.py --stage k8s          # Deploy to Kubernetes  (Sections 10-11)
  python setup.py --stage devops       # Azure DevOps pipelines  (Section 12.1-12.4)
  python setup.py --stage ml           # Azure ML workspace+train+deploy  (Section 12.5-12.7)
  python setup.py --check              # Verify prerequisites only
  python setup.py --cleanup            # Teardown all resources  (Section 14)
  python setup.py --resume-from azure  # Resume full run from a given stage

Stage order (full run):
  1. aws      §7   S3 / SQS / DynamoDB             ~2 min
  2. azure    §8   RG / ACR / AKS / NGINX          ~15 min
  3. images   §9   Docker build & push (8 images)  ~20 min
  4. k8s      §10-11  ConfigMap + deploy services  ~5 min
  5. devops   §12.1-12.4  DevOps + agent + pipelines  ~5 min
  6. ml       §12.5-12.7  ML workspace + train + deploy  ~30 min
  Total: ~75 min (dominated by AKS creation + ML training)
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from automation.config import config
from automation.utils.shell import check_tools, get_logger, step

log = get_logger("setup")

STAGES = ["aws", "azure", "images", "k8s", "devops", "ml"]


# ─── Stage runners ────────────────────────────────────────────────────────────

def _run_aws() -> dict:
    from automation.aws.setup_aws import setup_aws
    return setup_aws()


def _run_azure() -> dict:
    from automation.azure.setup_azure import setup_azure
    return setup_azure()


def _run_images() -> list:
    from automation.azure.build_images import build_images
    return build_images()


def _run_k8s(aws_resources: dict) -> dict:
    from automation.k8s.deploy_k8s import deploy_kubernetes
    deploy_kubernetes(aws_resources)
    return {"status": "deployed", "external_ip": config.azure.external_ip}


def _run_devops() -> dict:
    from automation.devops.setup_devops import setup_devops
    return setup_devops()


def _run_ml() -> dict:
    from automation.ml.setup_ml import setup_azure_ml
    return setup_azure_ml()


def _run_cleanup() -> None:
    from automation.cleanup import cleanup_all
    cleanup_all()


# ─── Prerequisite check ───────────────────────────────────────────────────────

def run_checks() -> bool:
    step("Prerequisites Check")
    ok = check_tools()
    if ok:
        log.info("✅ All tools present — ready to run setup")
    return ok


# ─── Full pipeline ────────────────────────────────────────────────────────────

def full_setup(start_from: str | None = None) -> None:
    start = time.time()
    results: dict = {}
    active = start_from is None

    log.info("\n" + "=" * 66)
    log.info("  Guardian AI — MultiCloud MLOps Setup")
    log.info("  AWS (S3/SQS/DynamoDB) + Azure (AKS/ACR/ML) + DevOps")
    log.info("=" * 66)

    if not run_checks():
        log.error("Install missing tools first.")
        sys.exit(1)

    runners = [
        ("aws",    _run_aws),
        ("azure",  _run_azure),
        ("images", _run_images),
        ("k8s",    None),        # special: needs aws results
        ("devops", _run_devops),
        ("ml",     _run_ml),
    ]

    for stage, runner in runners:
        if start_from and stage == start_from:
            active = True
        if not active:
            log.info("⏭  Skipping: %s", stage)
            continue

        log.info("\n🚀 Stage: %s", stage.upper())
        try:
            if stage == "k8s":
                result = _run_k8s(results.get("aws", {}))
            else:
                result = runner()
            results[stage] = result if isinstance(result, dict) else {"done": True}
        except Exception as exc:
            log.error("❌ Stage '%s' failed: %s", stage, exc)
            log.error("   Fix the issue then: python setup.py --resume-from %s", stage)
            _save(results)
            sys.exit(1)

        log.info("✅ Stage '%s' done\n", stage)

    elapsed = time.time() - start
    _save(results)

    log.info("\n" + "=" * 66)
    log.info("  ✅  FULL SETUP COMPLETE")
    log.info("  Time    : %d min %d sec", int(elapsed // 60), int(elapsed % 60))
    log.info("  App URL : http://%s", config.azure.external_ip or "(run: kubectl get svc -n ingress-nginx)")
    log.info("  DevOps  : https://dev.azure.com/%s", config.devops.organization_name)
    log.info("  ML Studio: https://ml.azure.com")
    log.info("=" * 66)


def _save(results: dict) -> None:
    out = config.project_root / ".run_outputs.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    log.info("Run outputs saved to: %s", out)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MultiCloud MLOps Setup Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--stage",       choices=STAGES, help="Run only this stage")
    p.add_argument("--resume-from", choices=STAGES, dest="resume_from",
                   help="Resume full run from this stage")
    p.add_argument("--check",    action="store_true", help="Check prerequisites")
    p.add_argument("--cleanup",  action="store_true", help="Teardown all resources")
    return p.parse_args()


def main() -> None:
    args = _parse()

    if args.check:
        sys.exit(0 if run_checks() else 1)

    if args.cleanup:
        _run_cleanup()
        return

    if args.stage:
        runners = {
            "aws": _run_aws, "azure": _run_azure,
            "images": _run_images, "k8s": lambda: _run_k8s({}),
            "devops": _run_devops, "ml": _run_ml,
        }
        runners[args.stage]()
        return

    full_setup(start_from=args.resume_from)


if __name__ == "__main__":
    main()
