"""Minimal .env loader with automatic type casting. No third-party dependencies."""

from __future__ import annotations

import json
import os
import re
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Union

__all__ = ["Env", "parse_dotenv"]


class _Value(NamedTuple):
    value: str
    quoted: bool  # True when the value was wrapped in '' or "" -> always a string


_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]*")
_INLINE_COMMENT_RE = re.compile(r"\s+#")
_EXPAND_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
_ESCAPE_RE = re.compile(r"\\(.)", re.DOTALL)
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "$": "$"}
_INT_RE = re.compile(r"[+-]?\d+")
_FLOAT_RE = re.compile(r"[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?")
_QUOTES = ("'", '"')

_TRUE = {"true", "1", "yes", "y", "on"}
_FALSE = {"false", "0", "no", "n", "off"}

# Values that an Env instance wrote into os.environ (key -> value). Lets us tell
# "real" environment variables (which take precedence over .env files) apart
# from values that were only injected by loading a .env file.
_injected: Dict[str, str] = {}


# --------------------------------------------------------------------------- #
# Parsing the .env file
# --------------------------------------------------------------------------- #
def _find_closing_quote(text: str, quote: str) -> int:
    i = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and quote == '"':
            i += 2
            continue
        if char == quote:
            return i
        i += 1
    return -1


def _unescape(text: str) -> str:
    return _ESCAPE_RE.sub(lambda m: _ESCAPES.get(m.group(1), m.group(0)), text)


def _expand(text: str, parsed: Dict[str, _Value]) -> str:
    """Expand ``${VAR}`` and ``${VAR:-default}`` references."""

    def replace(match: "re.Match[str]") -> str:
        name, default = match.group(1), match.group(2)
        if name in os.environ and _injected.get(name) != os.environ[name]:
            return os.environ[name]
        if name in parsed:
            return parsed[name].value
        if name in os.environ:
            return os.environ[name]
        return default or ""

    return _EXPAND_RE.sub(replace, text)


def _parse(text: str) -> Dict[str, _Value]:
    result: Dict[str, _Value] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()

        key, sep, rest = line.partition("=")
        key = key.strip()
        if not sep or not _KEY_RE.fullmatch(key):
            continue
        rest = rest.lstrip()

        if rest[:1] in _QUOTES:
            quote, body = rest[0], rest[1:]
            end = _find_closing_quote(body, quote)
            # Quoted values may span several lines.
            while end == -1 and i < len(lines):
                body += "\n" + lines[i]
                i += 1
                end = _find_closing_quote(body, quote)
            value = body if end == -1 else body[:end]
            if quote == '"':
                value = _expand(_unescape(value), result)
            result[key] = _Value(value, True)
        else:
            value = _INLINE_COMMENT_RE.split(rest, maxsplit=1)[0].strip()
            result[key] = _Value(_expand(value, result), False)
    return result


def parse_dotenv(text: str) -> Dict[str, str]:
    """Parse the content of a .env file into a ``{key: value}`` dict."""
    return {key: item.value for key, item in _parse(text).items()}


# --------------------------------------------------------------------------- #
# Type casting
# --------------------------------------------------------------------------- #
def _is_quoted(value: str) -> bool:
    return len(value) >= 2 and value[0] == value[-1] and value[0] in _QUOTES


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if _is_quoted(value):
        return value[1:-1]

    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if _INT_RE.fullmatch(value):
        return int(value)
    if _FLOAT_RE.fullmatch(value):
        return float(value)
    return value


def _parse_value(value: str) -> Any:
    """Guess the Python type of an unquoted value."""
    value = value.strip()
    if _is_quoted(value):
        return value[1:-1]

    # JSON objects / arrays (checked before comma-separated lists)
    if value[:1] in ("{", "["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

    if "," in value:
        return [_parse_scalar(item) for item in value.split(",") if item.strip()]

    return _parse_scalar(value)


def _split_list(value: str, separator: str) -> List[str]:
    items = []
    for item in value.split(separator):
        item = item.strip()
        if _is_quoted(item):
            items.append(item[1:-1])
        elif item:
            items.append(item)
    return items


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
class Env:
    """Load a .env file and read variables with automatic or explicit casting.

    >>> env = Env()              # loads ".env"
    >>> env = Env(".env.dev")    # loads another file
    >>> env("DEBUG", False)      # auto-cast with default values
    >>> env.bool("DEBUG", False) # explicit cast

    Variables already present in the real environment take precedence over the
    file, unless ``override=True``.
    """

    def __init__(
        self,
        path: Union[str, "os.PathLike[str]"] = ".env",
        *,
        override: bool = False,
        encoding: str = "utf-8",
        lazy: bool = False,
    ) -> None:
        self.path = Path(path)
        self.override = override
        self.encoding = encoding
        self._values: Dict[str, _Value] = {}
        self._loaded = False
        if not lazy:
            self.load()

    # -- loading ----------------------------------------------------------- #
    def _resolve_path(self) -> Optional[Path]:
        if self.path.is_absolute():
            return self.path if self.path.is_file() else None
        # Look in the current directory, then walk up the parents.
        cwd = Path.cwd()
        for directory in (cwd, *cwd.parents):
            candidate = directory / self.path
            if candidate.is_file():
                return candidate
        return None

    def load(self) -> "Env":
        """(Re)load the file and export its variables to ``os.environ``."""
        path = self._resolve_path()
        self._values = _parse(path.read_text(encoding=self.encoding)) if path else {}
        for key, item in self._values.items():
            current = os.environ.get(key)
            is_real = current is not None and _injected.get(key) != current
            if self.override or not is_real:
                os.environ[key] = item.value
                _injected[key] = item.value
        self._loaded = True
        return self

    def _lookup(self, key: str) -> Optional[_Value]:
        if not self._loaded:
            self.load()
        own = self._values.get(key)
        current = os.environ.get(key)

        if current is not None and _injected.get(key) != current:
            # A real environment variable: it wins over the file.
            if own is not None and own.value == current:
                return own
            if _is_quoted(current):
                return _Value(current[1:-1], True)
            return _Value(current, False)
        if own is not None:
            return own
        if current is not None:  # injected by another Env instance
            return _Value(current, False)
        return None

    # -- accessors --------------------------------------------------------- #
    def __call__(self, key: str, default: Any = None) -> Any:
        """Return the variable, auto-cast to bool/int/float/list/dict/str.

        Values wrapped in quotes in the .env file are always returned as str.
        """
        item = self._lookup(key)
        if item is None:
            return default
        if item.quoted:
            return item.value
        return _parse_value(item.value)

    def __contains__(self, key: str) -> bool:
        return self._lookup(key) is not None

    def str(self, key: str, default: Any = None) -> Any:
        item = self._lookup(key)
        return default if item is None else item.value

    def bool(self, key: str, default: Any = None) -> Any:
        item = self._lookup(key)
        if item is None or not item.value.strip():
            return default
        value = item.value.strip().lower()
        if value in _TRUE:
            return True
        if value in _FALSE:
            return False
        raise ValueError(f"{key}={item.value!r} is not a valid boolean")

    def int(self, key: str, default: Any = None) -> Any:
        return self._cast(key, default, int, "an integer")

    def float(self, key: str, default: Any = None) -> Any:
        return self._cast(key, default, float, "a float")

    def list(
        self,
        key: str,
        default: Any = None,
        *,
        cast: Optional[Callable[[str], Any]] = None,
        separator: str = ",",
    ) -> Any:
        """Return a list from a comma-separated (or JSON array) value.

        Items are strings unless ``cast`` is given, e.g. ``env.list("PORTS", cast=int)``.
        """
        item = self._lookup(key)
        if item is None:
            return default
        value = item.value.strip()
        items: List[Any] = _split_list(value, separator)
        if value.startswith("["):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                items = parsed
        return [cast(i) for i in items] if cast else items

    def json(self, key: str, default: Any = None) -> Any:
        item = self._lookup(key)
        if item is None:
            return default
        try:
            return json.loads(item.value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{key} is not valid JSON: {exc}") from exc

    def _cast(self, key: str, default: Any, cast: Callable[[str], Any], label: str) -> Any:
        item = self._lookup(key)
        if item is None:
            return default
        try:
            return cast(item.value.strip())
        except ValueError:
            raise ValueError(f"{key}={item.value!r} is not {label}") from None

    def __repr__(self) -> str:
        return f"Env({str(self.path)!r})"


# Backs the deprecated module-level `env`. Loaded on first access, so importing
# the package never touches the filesystem.
_default_env = Env(lazy=True)

_ENV_DEPRECATION = (
    "`antares_dotenv.env` is deprecated and will be removed in 2.0. "
    "Use `from antares_dotenv import Env` and `env = Env()` instead."
)


def _get_deprecated_env(stacklevel: int) -> Env:
    """Warn about the old `env` and return it. `stacklevel` is relative to the caller."""
    warnings.warn(_ENV_DEPRECATION, DeprecationWarning, stacklevel=stacklevel + 1)
    return _default_env


def __getattr__(name: str) -> Any:
    if name == "env":
        return _get_deprecated_env(stacklevel=2)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
