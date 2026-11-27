import pytest

from parlimen import config


def test_api_key_prefers_the_environment(monkeypatch, tmp_path):
    key_file = tmp_path / "key.txt"
    key_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setattr(config, "KEY_FILE", key_file)
    monkeypatch.setenv("ANTHROPIC_API_KEY", " from-env ")
    assert config.api_key() == "from-env"


def test_api_key_falls_back_to_the_key_file(monkeypatch, tmp_path):
    key_file = tmp_path / "key.txt"
    key_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setattr(config, "KEY_FILE", key_file)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.api_key() == "from-file"


def test_api_key_missing_names_both_ways(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "KEY_FILE", tmp_path / "absent.txt")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        config.api_key()
