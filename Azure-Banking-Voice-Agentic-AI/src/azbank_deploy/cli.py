"""`azbank-deploy deploy` / `azbank-deploy teardown` -- the Typer CLI `make deploy`/`make teardown`
drive (docs/PLAN.md decision 3). Both commands: resume live state, compute the legal order, run it
step by step, checkpoint after every step (not just at the end) so a crash mid-run loses at most one
step's progress.
"""
from __future__ import annotations

import typer

from . import actions, config, resources, state

app = typer.Typer(add_completion=False, help="Stand up or tear down every Azure resource this project owns.")


_IMAGE_HELP = "Full image ref, including tag -- never :latest."


@app.command()
def deploy(
    voice_agent_image: str = typer.Option(..., envvar="VOICE_AGENT_IMAGE", help=_IMAGE_HELP),
    core_banking_image: str = typer.Option(..., envvar="CORE_BANKING_IMAGE", help=_IMAGE_HELP),
    dockerhub_username: str = typer.Option("maofilho", envvar="DOCKERHUB_USERNAME"),
    dockerhub_password: str = typer.Option(..., envvar="DOCKERHUB_PASSWORD"),
) -> None:
    """Deploys everything this project owns, in the one legal order, resuming from wherever a
    previous run left off. ACS is included -- it's a normal deploy target, only teardown excludes
    it (D5)."""
    resource_group = config.resource_group()
    typer.echo(f"resource group: {resource_group}")

    current = state.resume_state(resource_group, config.NAMES)
    steps = resources.legal_deploy_order(current)
    if not steps:
        typer.echo("nothing to do -- every resource is already deployed.")
        raise typer.Exit(0)

    typer.echo(f"{len(steps)} step(s) to run: {', '.join(resources.RESOURCES[k].label for k in steps)}")

    image = {"voice_agent": voice_agent_image, "core_banking": core_banking_image}
    dockerhub = {"username": dockerhub_username, "password": dockerhub_password}

    for key in steps:
        label = resources.RESOURCES[key].label
        typer.echo(f"deploying {label} ({key}) ...")
        actions.deploy_one(resource_group, key, image, dockerhub)
        current[key] = "deployed"
        state.save(current)
        typer.echo(f"  done: {label}")

    typer.echo("deploy complete.")


_YES_HELP = (
    "Skip the confirmation prompt. Never set this in an automated context without a human "
    "watching (docs/phase7/exit-criteria.md, 'What this phase must not do')."
)


@app.command()
def teardown(
    yes: bool = typer.Option(False, "--yes", help=_YES_HELP),
) -> None:
    """Tears down every teardown-eligible resource, in the one legal reverse order, then purges any
    soft-deleted AOAI account so the next deploy doesn't trip over a name collision that isn't
    actually this project's own live resource. ACS and the phone number are never touched -- not an
    option this command exposes, not a flag that could bypass it (D5, R-09)."""
    resource_group = config.resource_group()
    typer.echo(f"resource group: {resource_group}")

    current = state.resume_state(resource_group, config.NAMES)
    steps = resources.legal_teardown_order(current)
    if not steps:
        typer.echo("nothing to tear down -- every eligible resource is already absent.")
    else:
        typer.echo(f"{len(steps)} step(s) to run: {', '.join(resources.RESOURCES[k].label for k in steps)}")
        typer.echo("ACS and the phone number are excluded -- not a step in this list, by design.")

        if not yes and not typer.confirm("Proceed with teardown?"):
            raise typer.Exit(1)

        for key in steps:
            label = resources.RESOURCES[key].label
            typer.echo(f"tearing down {label} ({key}) ...")
            actions.teardown_one(resource_group, key)
            current[key] = "absent"
            state.save(current)
            typer.echo(f"  done: {label}")

    purged = actions.purge_soft_deleted_aoai(resource_group)
    if purged:
        typer.echo(f"purged soft-deleted AOAI account: {purged}")
    else:
        typer.echo("no soft-deleted AOAI account found -- nothing to purge.")

    typer.echo("teardown complete.")


if __name__ == "__main__":
    app()
