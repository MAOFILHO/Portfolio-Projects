from pathlib import Path

import yaml

from bedrock_platform.config.scenario_config import ScenarioConfig

SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "configs" / "scenarios"


def load_scenarios(scenarios_dir: Path = SCENARIOS_DIR) -> list[ScenarioConfig]:
    configs: list[ScenarioConfig] = []
    seen_ids: set[str] = set()

    for path in sorted(scenarios_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        config = ScenarioConfig.model_validate(raw)
        if config.id in seen_ids:
            raise ValueError(f"Duplicate scenario id: {config.id!r} (from {path})")
        seen_ids.add(config.id)
        configs.append(config)

    return configs


def enabled_scenarios(scenarios_dir: Path = SCENARIOS_DIR) -> list[ScenarioConfig]:
    return [s for s in load_scenarios(scenarios_dir) if s.enabled]
