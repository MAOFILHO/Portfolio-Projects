"""Tests for service registration (src/services.py)."""

from src.factory import MCPServiceFactory
from src.mcp_services.domain_adapter.task_manager import DomainAdapterTaskManager
from src.mcp_services.proxy_aggregator.task_manager import ProxyAggregatorTaskManager
from src.mcp_services.resource_gateway.task_manager import ResourceGatewayTaskManager
from src.mcp_services.tool_orchestrator.task_manager import ToolOrchestratorTaskManager
from src.services import get_supported_mcp_services


def test_orchestrator_is_a_supported_service():
    assert "orchestrator" in get_supported_mcp_services()


def test_orchestrator_uses_the_shared_tool_orchestrator_task_manager():
    task_manager = MCPServiceFactory.create_task_manager("orchestrator")

    assert isinstance(task_manager, ToolOrchestratorTaskManager)


def test_domain_wrapper_and_domain_adapter_are_supported_services():
    supported = get_supported_mcp_services()

    assert "domain_wrapper" in supported
    assert "domain_adapter" in supported


def test_domain_wrapper_and_domain_adapter_share_the_domain_adapter_task_manager():
    assert isinstance(
        MCPServiceFactory.create_task_manager("domain_wrapper"), DomainAdapterTaskManager
    )
    assert isinstance(
        MCPServiceFactory.create_task_manager("domain_adapter"), DomainAdapterTaskManager
    )


def test_proxy_wrapper_and_proxy_aggregator_are_supported_services():
    supported = get_supported_mcp_services()

    assert "proxy_wrapper" in supported
    assert "proxy_aggregator" in supported


def test_proxy_wrapper_and_proxy_aggregator_share_the_proxy_aggregator_task_manager():
    assert isinstance(
        MCPServiceFactory.create_task_manager("proxy_wrapper"), ProxyAggregatorTaskManager
    )
    assert isinstance(
        MCPServiceFactory.create_task_manager("proxy_aggregator"), ProxyAggregatorTaskManager
    )


def test_resource_wrapper_and_resource_gateway_are_supported_services():
    supported = get_supported_mcp_services()

    assert "resource_wrapper" in supported
    assert "resource_gateway" in supported


def test_resource_wrapper_and_resource_gateway_share_the_resource_gateway_task_manager():
    assert isinstance(
        MCPServiceFactory.create_task_manager("resource_wrapper"), ResourceGatewayTaskManager
    )
    assert isinstance(
        MCPServiceFactory.create_task_manager("resource_gateway"), ResourceGatewayTaskManager
    )
