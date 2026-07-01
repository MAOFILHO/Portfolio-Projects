"""Step 2: Collect API keys and secrets from user."""

from __future__ import annotations

from rich.prompt import Prompt

from cdss_deploy.console import console, print_substep


def run(ctx: dict) -> dict:
    config = ctx["config"]

    # PubMed credentials
    if not config.cdss_pubmed_api_key:
        console.print()
        console.print(
            "[yellow]PubMed API key required for literature search.[/yellow]\n"
            "[dim]Get yours at: https://www.ncbi.nlm.nih.gov/account/ → API Key Management[/dim]"
        )
        api_key = Prompt.ask("PubMed API key", password=True)
        config.cdss_pubmed_api_key = api_key

        import os
        os.environ["CDSS_PUBMED_API_KEY"] = api_key
    else:
        print_substep("PubMed API key: provided via environment", "ok")

    if not config.cdss_pubmed_email:
        email = Prompt.ask("PubMed contact email")
        config.cdss_pubmed_email = email

        import os
        os.environ["CDSS_PUBMED_EMAIL"] = email
    else:
        print_substep(f"PubMed email: {config.cdss_pubmed_email}", "ok")

    # Validate
    if not config.cdss_pubmed_api_key:
        return {"success": False, "error": "PubMed API key is required"}
    if not config.cdss_pubmed_email:
        return {"success": False, "error": "PubMed email is required"}

    print_substep(f"PubMed email: {config.cdss_pubmed_email}", "ok")
    print_substep("PubMed API key: ****" + config.cdss_pubmed_api_key[-4:], "ok")

    # DrugBank (optional)
    if config.cdss_drugbank_api_key:
        print_substep("DrugBank API key: provided", "ok")
    else:
        print_substep("DrugBank API key: not provided (optional, using OpenFDA fallback)", "info")

    return {"success": True}
