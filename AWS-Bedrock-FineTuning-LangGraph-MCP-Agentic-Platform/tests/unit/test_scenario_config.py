from bedrock_platform.config.scenario_loader import load_scenarios


def test_all_seven_configs_load() -> None:
    configs = load_scenarios()
    assert len(configs) == 7


def test_exactly_three_enabled() -> None:
    configs = load_scenarios()
    enabled = [c for c in configs if c.enabled]
    assert len(enabled) == 3
    assert {c.id for c in enabled} == {"banking", "it_helpdesk", "pharma"}
    print("7 scenarios loaded, 3 enabled")


def test_every_dataset_path_exists() -> None:
    configs = load_scenarios()
    for config in configs:
        assert config.dataset_path.exists(), f"{config.id}: {config.dataset_path} missing"


def test_no_duplicate_ids() -> None:
    configs = load_scenarios()
    ids = [c.id for c in configs]
    assert len(ids) == len(set(ids))
