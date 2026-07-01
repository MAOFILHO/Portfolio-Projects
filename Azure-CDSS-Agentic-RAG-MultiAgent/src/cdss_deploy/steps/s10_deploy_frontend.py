"""Step 10: Build and deploy React frontend to Azure Static Web Apps."""

from __future__ import annotations

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_cmd


def run(ctx: dict) -> dict:
    config = ctx["config"]
    state = ctx["state"]
    source_dir = ctx["source_dir"]
    frontend_dir = source_dir / "frontend"

    if config.cdss_skip_frontend_deploy:
        print_substep("Frontend deploy skipped (CDSS_SKIP_FRONTEND_DEPLOY=true)", "info")
        return {"success": True}

    swa_token = state.deployed_resources.get("swa_token", "")
    if not swa_token:
        return {"success": False, "error": "SWA deployment token not found — run step 9 first"}

    if not (frontend_dir / "package.json").exists():
        return {"success": False, "error": f"Frontend not found at {frontend_dir}"}

    # npm ci
    print_substep("Installing frontend dependencies (npm ci)...", "info")
    result = run_cmd(["npm", "ci"], cwd=frontend_dir, stream=True, timeout=300)
    if not result.success:
        return {"success": False, "error": f"npm ci failed: {result.stderr[-300:]}"}
    print_substep("Dependencies installed", "ok")

    # npm run build
    print_substep("Building frontend (npm run build)...", "info")
    result = run_cmd(["npm", "run", "build"], cwd=frontend_dir, stream=True, timeout=300)
    if not result.success:
        return {"success": False, "error": f"npm run build failed: {result.stderr[-300:]}"}
    print_substep("Frontend built", "ok")

    # Copy staticwebapp.config.json
    config_src = frontend_dir / "staticwebapp.config.json"
    config_dst = frontend_dir / "dist" / "staticwebapp.config.json"
    if config_src.exists():
        import shutil
        shutil.copy2(config_src, config_dst)
        print_substep("Copied staticwebapp.config.json to dist/", "ok")

    # Deploy to SWA
    print_substep("Deploying to Azure Static Web Apps...", "info")
    result = run_cmd(
        [
            "npx", "@azure/static-web-apps-cli", "deploy", "./dist",
            "--deployment-token", swa_token,
            "--env", "production",
        ],
        cwd=frontend_dir,
        stream=True,
        timeout=300,
    )

    if not result.success:
        return {"success": False, "error": f"SWA deploy failed: {result.stderr[-300:]}"}

    swa_host = state.deployed_resources.get("swa_host", "")
    print_substep(f"Frontend deployed: https://{swa_host}", "ok")

    return {"success": True, "resources": {"frontend_url": f"https://{swa_host}"}}
