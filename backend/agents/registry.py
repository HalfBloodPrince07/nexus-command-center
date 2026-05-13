import logging
from typing import Any

logger = logging.getLogger(__name__)

_AGENT_REGISTRY: dict[str, type] = {}

def register_agent(name: str, cls: type) -> None:
    _AGENT_REGISTRY[name] = cls
    logger.debug("Registered agent: %s -> %s", name, cls.__name__)

def get_agent_class(name: str) -> type | None:
    return _AGENT_REGISTRY.get(name)

def get_agent(name: str, **kwargs: Any) -> Any:
    cls = _AGENT_REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"Agent '{name}' not found in registry")
    return cls(**kwargs)

def list_agents() -> list[str]:
    return sorted(_AGENT_REGISTRY.keys())
