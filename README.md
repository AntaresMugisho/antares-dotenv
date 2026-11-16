# antares-dotenv

A minimalistic and developer-friendly way to handle environment variables in Python with automatic type casting. Create an `Env` instance and start using it.

## Installation

```bash
pip install antares-dotenv
```

## Usage

Create a `.env` file in your project root:

```
# .env

# Strings
APP_NAME=My Awesome App

# Integers
PORT=8000

# Booleans
DEBUG=True

# Lists (comma-separated)
ALLOWED_HOSTS=localhost,127.0.0.1

# JSON
DATABASE_CONFIG={"user": "admin", "password": "secret"}
```

Now you can access these variables in your Python code:

```python
# main.py

from antares_dotenv import Env

env = Env()

# String
app_name = env("APP_NAME", default="My App")
print(f"App Name: {app_name}")

# Integer (auto-parsed)
port = env("PORT")
print(f"Port: {port} (type: {type(port).__name__})")

# Boolean (auto-parsed)
debug_mode = env("DEBUG")
print(f"Debug Mode: {debug_mode} (type: {type(debug_mode).__name__})")

# List (auto-parsed)
allowed_hosts = env("ALLOWED_HOSTS")
print(f"Allowed Hosts: {allowed_hosts} (type: {type(allowed_hosts).__name__})")

# JSON (auto-parsed to dict)
db_config = env("DATABASE_CONFIG")
print(f"Database User: {db_config['user']}")

# Using a default value for a missing key
secret_key = env("SECRET_KEY", default="a-very-secret-key")
print(f"Secret Key: {secret_key}")
```

## Using the `Env` class

Use `Env` to load a specific file or to cast a value explicitly:

```python
from antares_dotenv import Env

env = Env()             # loads .env (searched in the current dir, then its parents)
env = Env(".env.dev")   # loads another file instead

env("DEBUG", False)             # auto-cast, with a default
env.bool("DEBUG", False)        # true/false, 1/0, yes/no, on/off
env.int("PORT", 8000)
env.float("RATIO", 0.5)
env.str("APP_NAME")
env.list("ALLOWED_HOSTS")       # ["localhost", "127.0.0.1"]
env.list("PORTS", cast=int)     # [80, 443]
env.list("TAGS", separator="|")
env.json("DATABASE_CONFIG")
"DEBUG" in env                  # True if the variable is defined
```

### Quoted values are always strings

```
ALLOWED_HOSTS=localhost,127.0.0.1      # env("ALLOWED_HOSTS") -> ["localhost", "127.0.0.1"]
ALLOWED_HOSTS="localhost,127.0.0.1"    # env("ALLOWED_HOSTS") -> "localhost,127.0.0.1"
PORT='8000'                            # env("PORT") -> "8000"
```

The explicit methods (`env.list`, `env.int`, ...) still cast quoted values.

### Supported `.env` syntax

- `# comments`, blank lines, and inline comments after unquoted values (`KEY=value  # note`)
- `export KEY=value`
- Single quotes (taken literally) and double quotes (handle `\n`, `\t`, `\"` and can span several lines)
- Variable expansion: `${OTHER}` and `${OTHER:-default}` (unquoted and double-quoted values)

### Precedence

Variables already set in the real environment win over the file. Use `Env(override=True)` to make the file win.
Loaded values are also exported to `os.environ`, so other libraries can read them.

## Why antares-dotenv?

`antares-dotenv` is designed to reduce boilerplate and simplify your code.

**Before (with `python-dotenv` and `os`):**

```python
import os
from dotenv import load_dotenv

load_dotenv()

port = int(os.getenv("PORT"))
debug = os.getenv("DEBUG").lower() == 'true'
hosts = os.getenv("ALLOWED_HOSTS").split(',')
```

**After (with `antares-dotenv`):**

```python
from antares_dotenv import Env

env = Env()

port = env("PORT")
debug = env("DEBUG")
hosts = env("ALLOWED_HOSTS")
```

`antares-dotenv` automatically handles the type casting for you, eliminating the need for manual type conversion and making your code cleaner, more readable, and less verbose.


> [!Warning]
> **Deprecated since 1.2.0:** `from antares_dotenv import env` (the ready-made instance) still works but emits a
> `DeprecationWarning` and will be removed in 2.0. Replace it with:
>
> ```python
> from antares_dotenv import Env
>
> env = Env()
> ```

**_PS: This package is tailored to my specific needs !_**
