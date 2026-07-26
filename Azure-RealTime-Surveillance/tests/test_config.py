from surveil_deploy.config import DeployConfig


def test_default_resource_group_derived_from_env_name():
    config = DeployConfig(azure_env_name="demo", azure_resource_group="", _env_file=None)
    assert config.resource_group_name() == "demo-rg"


def test_explicit_resource_group_overrides_default():
    config = DeployConfig(azure_env_name="demo", azure_resource_group="custom-rg", _env_file=None)
    assert config.resource_group_name() == "custom-rg"


def test_defaults_are_cost_minimal():
    config = DeployConfig(_env_file=None)
    assert config.vision_sku == "S1"
    assert config.storage_sku_name == "Standard_LRS"
    assert config.azure_location == "eastus2"
