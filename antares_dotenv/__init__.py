from typing import Any

from .core import Env, _get_deprecated_env, parse_dotenv

__all__ = ["Env", "parse_dotenv"]


def __getattr__(name: str) -> Any:
    # `env` is deprecated: served lazily so that using it emits a DeprecationWarning.
    if name == "env":
        return _get_deprecated_env(stacklevel=2)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
