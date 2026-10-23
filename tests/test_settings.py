from pathlib import Path

from config.settings import get_env_path_list


def test_get_env_path_list_falls_back_to_a_single_default_path():
    paths = get_env_path_list("AUTOGRAPH_TEST_UNSET_VAR", "~/projects")

    assert paths == [Path("~/projects").expanduser().resolve()]


def test_get_env_path_list_splits_a_comma_separated_value(monkeypatch):
    monkeypatch.setenv("AUTOGRAPH_TEST_SEARCH_DIRS", "~/Dev, ~/Knowit")

    paths = get_env_path_list("AUTOGRAPH_TEST_SEARCH_DIRS", "~/projects")

    assert paths == [
        Path("~/Dev").expanduser().resolve(),
        Path("~/Knowit").expanduser().resolve(),
    ]
