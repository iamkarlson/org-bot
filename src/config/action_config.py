"""Action configuration dataclass."""

from dataclasses import dataclass
from typing import Callable


@dataclass
class ActionConfig:
    """Configuration for a single action."""

    function: Callable
    response_message: str
