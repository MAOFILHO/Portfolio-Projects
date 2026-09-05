"""
Service Definitions for MCPMark
================================

Single source of truth for all MCP service configurations.
Adding a new service only requires modifying this file.

Note: Environment variables are already loaded from .mcp_env when the app starts,
so we can reference them directly via the config system.

MCP server creation is now handled entirely within src.agent.MCPAgent; therefore,
the legacy "mcp_server" and "eval_config" entries in each service definition are
deprecated and set to None for backward-compatibility.
"""

# Service definitions
SERVICES = {
    "wrapper": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.tool_orchestrator.task_manager.ToolOrchestratorTaskManager",
            "state_manager": "src.mcp_services.tool_orchestrator.state_manager.ToolOrchestratorStateManager",
            "login_helper": "src.mcp_services.tool_orchestrator.login_helper.ToolOrchestratorLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
    "orchestrator": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.tool_orchestrator.task_manager.ToolOrchestratorTaskManager",
            "state_manager": "src.mcp_services.tool_orchestrator.state_manager.ToolOrchestratorStateManager",
            "login_helper": "src.mcp_services.tool_orchestrator.login_helper.ToolOrchestratorLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
    # Domain-Specific Adapter (Phase 2). Baseline reuses server_wrapper as-is
    # (ADR 0002); only the task set and backend reset differ from Tool
    # Orchestrator, so both point at domain_adapter's task/state managers.
    "domain_wrapper": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.domain_adapter.task_manager.DomainAdapterTaskManager",
            "state_manager": "src.mcp_services.domain_adapter.state_manager.DomainAdapterStateManager",
            "login_helper": "src.mcp_services.domain_adapter.login_helper.DomainAdapterLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
    "domain_adapter": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.domain_adapter.task_manager.DomainAdapterTaskManager",
            "state_manager": "src.mcp_services.domain_adapter.state_manager.DomainAdapterStateManager",
            "login_helper": "src.mcp_services.domain_adapter.login_helper.DomainAdapterLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
    # Stateful Session Server (Phase 3). Own baseline, not the reused
    # control, per ADR 0002 — the module under test is the baseline's
    # resend behavior (ADR 0007), not a smaller tool surface.
    "session_baseline": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.stateful_session.task_manager.StatefulSessionTaskManager",
            "state_manager": "src.mcp_services.stateful_session.state_manager.StatefulSessionStateManager",
            "login_helper": "src.mcp_services.stateful_session.login_helper.StatefulSessionLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
    "session_server": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.stateful_session.task_manager.StatefulSessionTaskManager",
            "state_manager": "src.mcp_services.stateful_session.state_manager.StatefulSessionStateManager",
            "login_helper": "src.mcp_services.stateful_session.login_helper.StatefulSessionLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
    # Proxy Aggregator (Phase 4). Baseline reuses server_wrapper, extended
    # with runbooks/deploys tools (ADR 0002); only the task set and backend
    # reset differ from Tool Orchestrator, so both point at proxy_aggregator's
    # task/state managers.
    "proxy_wrapper": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.proxy_aggregator.task_manager.ProxyAggregatorTaskManager",
            "state_manager": "src.mcp_services.proxy_aggregator.state_manager.ProxyAggregatorStateManager",
            "login_helper": "src.mcp_services.proxy_aggregator.login_helper.ProxyAggregatorLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
    "proxy_aggregator": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.proxy_aggregator.task_manager.ProxyAggregatorTaskManager",
            "state_manager": "src.mcp_services.proxy_aggregator.state_manager.ProxyAggregatorStateManager",
            "login_helper": "src.mcp_services.proxy_aggregator.login_helper.ProxyAggregatorLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
    # Resource Gateway (Phase 5). Baseline reuses server_wrapper, extended
    # with acknowledge_runbook (ADR 0002); only the task set and backend
    # reset differ from Tool Orchestrator, so both point at resource_gateway's
    # task/state managers.
    "resource_wrapper": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.resource_gateway.task_manager.ResourceGatewayTaskManager",
            "state_manager": "src.mcp_services.resource_gateway.state_manager.ResourceGatewayStateManager",
            "login_helper": "src.mcp_services.resource_gateway.login_helper.ResourceGatewayLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
    "resource_gateway": {
        "config_schema": {},
        "components": {
            "task_manager": "src.mcp_services.resource_gateway.task_manager.ResourceGatewayTaskManager",
            "state_manager": "src.mcp_services.resource_gateway.state_manager.ResourceGatewayStateManager",
            "login_helper": "src.mcp_services.resource_gateway.login_helper.ResourceGatewayLoginHelper",
        },
        "config_mapping": {},
        "mcp_server": None,
        "eval_config": None,
    },
}


def get_service_definition(service_name: str) -> dict:
    """Get MCP service definition by name."""
    if service_name not in SERVICES:
        raise ValueError(f"Unknown MCP service: {service_name}")
    return SERVICES[service_name]


def get_supported_mcp_services() -> list:
    """Get list of implemented MCP services."""
    return [
        name
        for name, config in SERVICES.items()
        if config["components"]["task_manager"] is not None
    ]
