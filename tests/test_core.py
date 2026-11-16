import os
from unittest import mock

import pytest

from antares_dotenv import Env, parse_dotenv
from antares_dotenv import core
from antares_dotenv.core import _parse_value


@pytest.fixture(autouse=True)
def isolated_environ(monkeypatch, tmp_path):
    """Restore os.environ and the injection registry after each test, run in a tmp dir."""
    monkeypatch.setattr(core, "_injected", {})
    monkeypatch.chdir(tmp_path)
    with mock.patch.dict(os.environ, clear=False):
        yield tmp_path


def write_env(directory, content, name=".env"):
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Auto-parsing
# --------------------------------------------------------------------------- #
def test_parse_value_boolean():
    assert _parse_value("true") is True
    assert _parse_value("True") is True
    assert _parse_value("false") is False
    assert _parse_value("False") is False


def test_parse_value_integer():
    assert _parse_value("42") == 42
    assert _parse_value("0") == 0
    assert _parse_value("-10") == -10


def test_parse_value_float():
    assert _parse_value("3.14") == 3.14
    assert _parse_value("-1.5") == -1.5
    assert _parse_value("0.0") == 0.0


def test_parse_value_does_not_treat_words_as_floats():
    assert _parse_value("nan") == "nan"
    assert _parse_value("inf") == "inf"
    assert _parse_value("1_000") == "1_000"


def test_parse_value_json():
    assert _parse_value('{"key": "value"}') == {"key": "value"}
    assert _parse_value("[1, 2, 3]") == [1, 2, 3]
    assert _parse_value('{"nested": {"key": 42}}') == {"nested": {"key": 42}}


def test_parse_value_list():
    assert _parse_value("a,b,c") == ["a", "b", "c"]
    assert _parse_value("1, 2, 3") == [1, 2, 3]
    assert _parse_value("true, false, true") == [True, False, True]
    assert _parse_value('1, 2.5, true, "string"') == [1, 2.5, True, "string"]


def test_parse_value_string():
    assert _parse_value("hello") == "hello"
    assert _parse_value("123abc") == "123abc"
    assert _parse_value("") == ""


# --------------------------------------------------------------------------- #
# .env file parsing
# --------------------------------------------------------------------------- #
def test_parse_dotenv_syntax():
    content = """
# a comment
export EXPORTED=yes
PLAIN=hello world  # inline comment
HASH=abc#def
SINGLE='raw ${PLAIN} \\n'
DOUBLE="line1\\nline2"
EXPANDED=${PLAIN}!
DEFAULTED=${MISSING:-fallback}
MULTI="first
second"
EMPTY=
not a valid line
"""
    assert parse_dotenv(content) == {
        "EXPORTED": "yes",
        "PLAIN": "hello world",
        "HASH": "abc#def",
        "SINGLE": "raw ${PLAIN} \\n",
        "DOUBLE": "line1\nline2",
        "EXPANDED": "hello world!",
        "DEFAULTED": "fallback",
        "MULTI": "first\nsecond",
        "EMPTY": "",
    }


# --------------------------------------------------------------------------- #
# Env class
# --------------------------------------------------------------------------- #
def test_env_loads_default_file(isolated_environ):
    write_env(isolated_environ, "DEBUG=true\nPORT=8000\nNAME=app\n")
    e = Env()
    assert e("DEBUG") is True
    assert e("PORT") == 8000
    assert e("NAME") == "app"
    assert os.environ["PORT"] == "8000"  # exported for other libraries


def test_env_custom_file(isolated_environ):
    write_env(isolated_environ, "DEBUG=true\n")
    write_env(isolated_environ, "DEBUG=false\n", name=".env.dev")
    assert Env(".env.dev")("DEBUG") is False


def test_env_searches_parent_directories(isolated_environ, monkeypatch):
    write_env(isolated_environ, "FOUND=1\n")
    child = isolated_environ / "a" / "b"
    child.mkdir(parents=True)
    monkeypatch.chdir(child)
    assert Env()("FOUND") == 1


def test_env_missing_file_uses_defaults():
    e = Env(".env.does-not-exist")
    assert e("DEBUG", False) is False
    assert e.bool("DEBUG", False) is False
    assert e("NOPE") is None


def test_quoted_values_are_strings(isolated_environ):
    write_env(
        isolated_environ,
        "HOSTS=localhost,127.0.0.1\n"
        "QUOTED_HOSTS=\"localhost,127.0.0.1\"\n"
        "SINGLE_QUOTED='42'\n"
        "BOOL_STR=\"true\"\n",
    )
    e = Env()
    assert e("HOSTS") == ["localhost", "127.0.0.1"]
    assert e("QUOTED_HOSTS") == "localhost,127.0.0.1"
    assert e("SINGLE_QUOTED") == "42"
    assert e("BOOL_STR") == "true"
    # Explicit casting still works on quoted values
    assert e.list("QUOTED_HOSTS") == ["localhost", "127.0.0.1"]
    assert e.int("SINGLE_QUOTED") == 42


def test_real_environment_wins_over_file(isolated_environ):
    os.environ["DEBUG"] = "false"
    write_env(isolated_environ, "DEBUG=true\n")
    assert Env()("DEBUG") is False
    assert Env(override=True)("DEBUG") is True


def test_second_instance_is_not_shadowed_by_first(isolated_environ):
    write_env(isolated_environ, "MODE=prod\n")
    write_env(isolated_environ, "MODE=dev\n", name=".env.dev")
    prod = Env()
    dev = Env(".env.dev")
    assert prod("MODE") == "prod"
    assert dev("MODE") == "dev"


def test_bool():
    os.environ.update({"A": "true", "B": "0", "C": "Yes", "D": "off", "E": "maybe", "F": ""})
    e = Env(".env.none")
    assert e.bool("A") is True
    assert e.bool("B") is False
    assert e.bool("C") is True
    assert e.bool("D") is False
    assert e.bool("F", True) is True
    assert e.bool("MISSING", False) is False
    with pytest.raises(ValueError):
        e.bool("E")


def test_list():
    os.environ.update({
        "HOSTS": "localhost, 127.0.0.1,",
        "PORTS": "80,443",
        "JSON_LIST": '["a", "b"]',
        "PIPES": "a|b|c",
    })
    e = Env(".env.none")
    assert e.list("HOSTS") == ["localhost", "127.0.0.1"]
    assert e.list("PORTS") == ["80", "443"]
    assert e.list("PORTS", cast=int) == [80, 443]
    assert e.list("JSON_LIST") == ["a", "b"]
    assert e.list("PIPES", separator="|") == ["a", "b", "c"]
    assert e.list("MISSING", []) == []


def test_str_int_float_json():
    os.environ.update({"N": "42", "F": "3.5", "J": '{"a": 1}', "BAD": "x"})
    e = Env(".env.none")
    assert e.str("N") == "42"
    assert e.int("N") == 42
    assert e.float("F") == 3.5
    assert e.json("J") == {"a": 1}
    assert e.int("MISSING", 7) == 7
    with pytest.raises(ValueError):
        e.int("BAD")
    with pytest.raises(ValueError):
        e.json("BAD")


def test_contains():
    os.environ["PRESENT"] = "1"
    e = Env(".env.none")
    assert "PRESENT" in e
    assert "ABSENT" not in e


# --------------------------------------------------------------------------- #
# Module-level `env` (deprecated, still backward compatible)
# --------------------------------------------------------------------------- #
@pytest.fixture
def env():
    with pytest.deprecated_call():
        from antares_dotenv import env as old_env
    return old_env


def test_env_import_is_deprecated():
    with pytest.warns(DeprecationWarning, match="Env()") as record:
        from antares_dotenv import env  # noqa: F401
    assert record[0].filename == __file__  # points at the user's import line

    with pytest.deprecated_call():
        core.env
    with pytest.deprecated_call():
        import antares_dotenv
        antares_dotenv.env


def test_new_api_does_not_warn(recwarn):
    from antares_dotenv import Env as NewEnv  # noqa: F401
    NewEnv(".env.none")("ANYTHING")
    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


def test_unknown_attribute_still_raises():
    import antares_dotenv
    with pytest.raises(AttributeError):
        antares_dotenv.nope


@mock.patch.dict(os.environ, {"TEST_STRING": "hello", "TEST_INT": "42", "TEST_BOOL": "true"})
def test_env_function_existing_variables(env):
    assert env("TEST_STRING") == "hello"
    assert env("TEST_INT") == 42
    assert env("TEST_BOOL") is True
    assert env.bool("TEST_BOOL") is True


def test_env_function_nonexistent_variable(env):
    assert env("NON_EXISTENT") is None
    assert env("NON_EXISTENT", default=123) == 123


@mock.patch.dict(os.environ, {"EMPTY_STRING": ""})
def test_env_function_empty_string(env):
    assert env("EMPTY_STRING") == ""
    assert env("EMPTY_STRING", default="default") == ""


def test_env_function_with_complex_types(env):
    test_env = {
        "TEST_JSON": '{"key": [1, 2, 3]}',
        "TEST_LIST": "a,b,c",
        "TEST_MIXED": '1, 2.5, true, "string"',
    }
    with mock.patch.dict(os.environ, test_env):
        assert env("TEST_JSON") == {"key": [1, 2, 3]}
        assert env("TEST_LIST") == ["a", "b", "c"]
        assert env("TEST_MIXED") == [1, 2.5, True, "string"]
