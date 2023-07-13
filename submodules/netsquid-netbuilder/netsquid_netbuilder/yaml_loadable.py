from __future__ import annotations

from abc import ABC
from typing import Any

import yaml
from pydantic import BaseModel


def _from_file(path: str, typ: Any) -> Any:
    with open(path, "r") as f:
        raw_config = yaml.load(f, Loader=yaml.Loader)
        return typ(**raw_config)


class YamlLoadable(BaseModel, ABC):
    @classmethod
    def from_file(cls, path: str) -> __class__:
        """Load the configuration from a YAML file."""
        return _from_file(path, cls)  # type: ignore
