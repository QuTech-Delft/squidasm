from dataclasses import dataclass
from typing import Callable, Dict, Any

from netqasm.sdk.config import LogConfig


@dataclass
class AppConfig:
    app_name: str
    node_name: str
    main_func: Callable
    log_config: LogConfig
    inputs: Dict[str, Any]
