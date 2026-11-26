import datetime

import pytest

from donormail.config import Config, ConfigError


def write(path, content):
    """Write a configuration file and return its path."""

    path.write_text(content)
    return path


MINIMAL = """
[org]
name = "Anytown Charity"

[contacts]
file = "contacts.csv"
columns = { name = "Donor" }

[gifts]
file = "gifts.csv"
columns = { date = "Date", name = "Donor", amount = "Amount" }

[letters.annual]
year = 2025

[email]
address = "treasurer@example.org"
"""


def test_example_config(workdir):
    """Example configuration loads with paths relative to its file."""

    config = Config(workdir / "basic/config.toml")
    assert config.org["name"] == "Anytown Charity"
    assert config.org["signer"]["title"] == "Treasurer"
    assert config.output == workdir / "basic/output"
    assert config.org["logo"] == workdir / "basic/logo.png"
    assert config.gifts["file"] == workdir / "basic/gifts.csv"
    assert config.gifts["date_format"] == "%m/%d/%Y"
    assert config.programs["Housing Repairs"] == "Housing"
    assert config.aliases == {}
    assert config.smtp["security"] == "none"


def test_defaults(tmp_path):
    """Optional settings get defaults."""

    config = Config(write(tmp_path / "config.toml", MINIMAL))
    assert config.org["signer"] == {"name": "", "title": ""}
    assert config.org["ein"] == ""
    assert config.templates is None
    assert config.smtp["security"] == "ssl"
    assert config.smtp["limit"] is None

    letter = config.letter()
    assert letter.name == "annual"
    assert letter.label == "2025"
    assert letter.attach is True
    assert letter.covers(datetime.date(2025, 12, 31))
    assert not letter.covers(datetime.date(2026, 1, 1))


def test_paths_relative_to_config(tmp_path, monkeypatch):
    """Paths resolve against the configuration file, not the working directory."""

    sub = tmp_path / "sub"
    sub.mkdir()
    config_path = write(sub / "config.toml", MINIMAL)
    monkeypatch.chdir(tmp_path)

    config = Config(config_path)
    assert config.contacts["file"] == sub / "contacts.csv"


def test_letter_period(tmp_path):
    """Letters can use start and end dates, and are chosen by name."""

    content = MINIMAL + "\n[letters.gala]\nstart = 2025-10-18\nend = 2025-10-18\n"
    config = Config(write(tmp_path / "config.toml", content))

    gala = config.letter("gala")
    assert gala.label == "2025-10-18 to 2025-10-18"
    assert gala.covers(datetime.date(2025, 10, 18))
    assert not gala.covers(datetime.date(2025, 10, 19))

    content += 'label = "2025 Gala"\n'
    labeled = Config(write(tmp_path / "config.toml", content)).letter("gala")
    assert labeled.label == "2025 Gala"

    with pytest.raises(ConfigError, match="Choose a letter: annual, gala"):
        config.letter()
    with pytest.raises(ConfigError, match="Unknown letter: spring"):
        config.letter("spring")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("[org]", "[orgs]"), "Unknown settings: orgs"),
        (('name = "Anytown Charity"', ""), "Missing setting: org.name"),
        (('file = "gifts.csv"', ""), "Missing setting: gifts.file"),
        ((' amount = "Amount"', ' amt = "Amount"'), "gifts.columns.amount"),
        (
            ('{ name = "Donor" }', '{ name = "Donor", phone = "P" }'),
            "contacts.columns.phone",
        ),
        (("[gifts]", "[gifts]\ndate_fmt = 'x'"), "Unknown settings: gifts.date_fmt"),
        (("[org]", "[org"), "config.toml"),
        (("[org]", "[org]\nsigner = { nme = 'x' }"), "org.signer.nme"),
        (("[org]", "[org]\nlogo = 'missing.png'"), "Logo not found"),
        (("[letters.annual]\nyear = 2025", ""), "at least one"),
        (("year = 2025", "year = '2025'"), "letters.annual.year must be a number"),
        (("year = 2025", "start = 2025-01-01"), "Set year, or start and end"),
        (("year = 2025", "year = 2025\nend = 2025-06-30"), "not both"),
        (
            ("year = 2025", "start = 2025-06-30\nend = 2025-01-01"),
            "start is after end",
        ),
        (("year = 2025", "year = 2025\npdf = true"), "letters.annual.pdf"),
        (('address = "treasurer@example.org"', ""), "email.address"),
        (("[email]", "[smtp]\nsecurity = 'tls'\n[email]"), "smtp.security"),
        (
            ("year = 2025", "start = 2025-01-01T00:00:00\nend = 2025-06-30"),
            "start and end dates like 2025-01-01",
        ),
        (("[email]", "[smtp]\nlimit = 0\n[email]"), "smtp.limit must be a number"),
        (("[email]", "[smtp]\nlimit = '50'\n[email]"), "smtp.limit must be a number"),
        (("[email]", "[smtp]\nport = '465'\n[email]"), "smtp.port must be a number"),
    ],
)
def test_invalid_config(tmp_path, change, message):
    """Invalid configuration raises a readable error."""

    content = MINIMAL.replace(*change)
    with pytest.raises(ConfigError, match=message):
        Config(write(tmp_path / "config.toml", content))
