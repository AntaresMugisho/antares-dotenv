import os
from unittest import mock
import pytest
from antares_dotenv.core import _parse_value, env


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


def test_parse_value_json():
    assert _parse_value('{"key": "value"}') == {"key": "value"}
    assert _parse_value('[1, 2, 3]') == [1, 2, 3]
    assert _parse_value('{"nested": {"key": 42}}') == {"nested": {"key": 42}}


def test_parse_value_list():
    assert _parse_value("a,b,c") == ["a", "b", "c"]
    assert _parse_value("1, 2, 3") == [1, 2, 3]
    assert _parse_value("true, false, true") == [True, False, True]


def test_parse_value_string():
    assert _parse_value("hello") == "hello"
    assert _parse_value("123abc") == "123abc"
    assert _parse_value("") == ""


@mock.patch.dict(os.environ, {"TEST_STRING": "hello", "TEST_INT": "42", "TEST_BOOL": "true"})
def test_env_existing_variables():
    assert env("TEST_STRING") == "hello"
    assert env("TEST_INT") == 42
    assert env("TEST_BOOL") is True


def test_env_nonexistent_variable():
    assert env("NON_EXISTENT") is None
    assert env("NON_EXISTENT", default=123) == 123


@mock.patch.dict(os.environ, {"EMPTY_STRING": ""})
def test_env_empty_string():
    assert env("EMPTY_STRING") == ""
    assert env("EMPTY_STRING", default="default") == ""


@mock.patch('antares_dotenv.core.load_dotenv')
def test_env_calls_load_dotenv(mock_load_dotenv):
    env("TEST")
    mock_load_dotenv.assert_called_once()


def test_env_with_complex_types():
    test_env = {
        "TEST_JSON": '{"key": [1, 2, 3]}',
        "TEST_LIST": "a,b,c",
        "TEST_MIXED": '1, 2.5, true, "string"'
    }
    
    with mock.patch.dict(os.environ, test_env):
        assert env("TEST_JSON") == {"key": [1, 2, 3]}
        assert env("TEST_LIST") == ["a", "b", "c"]
        assert env("TEST_MIXED") == [1, 2.5, True, "string"]
