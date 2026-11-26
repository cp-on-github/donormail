import datetime
import tomllib
from decimal import Decimal
from fnmatch import fnmatchcase
from pathlib import Path

SETTINGS = {
    "output",
    "templates",
    "org",
    "contacts",
    "gifts",
    "programs",
    "aliases",
    "third_party",
    "rules",
    "letters",
    "email",
    "smtp",
}

CONTACT_COLUMNS = {
    "required": {"name"},
    "optional": {"salutation", "email", "street", "city", "state", "zip"},
}

GIFT_COLUMNS = {
    "required": {"date", "name", "amount"},
    "optional": {
        "program",
        "product",
        "description",
        "price",
        "value",
    },
}

ORG_DEFAULTS = {
    "name": "",
    "ein": "",
    "address": "",
    "email": "",
    "website": "",
    "logo": "",
    "signer": {},
}

LETTER_DEFAULTS = {
    "year": None,
    "label": None,
    "start": None,
    "end": None,
    "subject": "{{ letter.label }} {{ org.name }} Contributions",
    "template": "letter.html",
    "email_html": "email.html",
    "email_text": "email.txt",
    "attach": True,
    "products": [],
    "exclude_products": [],
}

EMAIL_DEFAULTS = {"name": "", "address": None, "reply_to": "", "bcc": ""}

SMTP_DEFAULTS = {
    "host": None,
    "port": 0,
    "security": "ssl",
    "user": "",
    "limit": None,
}

SECURITY = {"ssl", "starttls", "none"}

THIRD_PARTY_DEFAULTS = {"markers": [], "funds": [], "separator": ":"}

RULE_KINDS = {"benefit", "in-kind"}


class ConfigError(Exception):
    """Invalid configuration."""


class Letter:
    def __init__(self, name, settings):
        """Create a letter from its settings."""

        self.name = name
        self.subject = settings["subject"]
        self.template = settings["template"]
        self.email_html = settings["email_html"]
        self.email_text = settings["email_text"]
        self.attach = settings["attach"]

        # product filters use the same wildcards as rules
        for key in ("products", "exclude_products"):
            patterns = settings[key]
            if not isinstance(patterns, list) or not all(
                isinstance(p, str) and p for p in patterns
            ):
                raise ConfigError(f"letters.{name}.{key} must be a list of products")
        self.products = settings["products"]
        self.exclude_products = settings["exclude_products"]

        # a year is shorthand for January 1 to December 31
        year, start, end = settings["year"], settings["start"], settings["end"]
        if year and (start or end):
            raise ConfigError(f"letters.{name}: Use year or start and end, not both")
        if year:
            if not isinstance(year, int):
                raise ConfigError(f"letters.{name}.year must be a number like 2025")
            start = datetime.date(year, 1, 1)
            end = datetime.date(year, 12, 31)
        # TOML date-times are dates too, but can't be compared with dates
        if not all(
            isinstance(d, datetime.date) and not isinstance(d, datetime.datetime)
            for d in (start, end)
        ):
            raise ConfigError(
                f"letters.{name}: Set year, or start and end dates like 2025-01-01"
            )
        if start > end:
            raise ConfigError(f"letters.{name}: start is after end")

        self.year = year
        self.start = start
        self.end = end
        self.label = settings["label"] or (str(year) if year else f"{start} to {end}")

    def covers(self, date):
        """Check if a date is within the letter period."""

        return self.start <= date <= self.end

    def selects(self, product):
        """Check if a product passes the letter's product filters."""

        if self.products and not any(fnmatchcase(product, p) for p in self.products):
            return False
        return not any(fnmatchcase(product, p) for p in self.exclude_products)


class Rule:
    def __init__(self, index, settings):
        """Create a product rule from its settings."""

        prefix = f"rules[{index}]"
        self.name = prefix
        if not isinstance(settings, dict):
            raise ConfigError(f"{prefix} must be a table")
        _check_keys(prefix, settings, {"product", "kind", "value"})

        product = settings.get("product")
        if not isinstance(product, str) or not product:
            raise ConfigError(f"Missing setting: {prefix}.product")
        self.product = product

        self.kind = settings.get("kind", "benefit")
        if self.kind not in RULE_KINDS:
            choices = ", ".join(sorted(RULE_KINDS))
            raise ConfigError(f"{prefix}.kind must be one of: {choices}")

        # value is per unit, or "amount" when the whole payment is value received
        self.value = settings.get("value")
        if self.kind == "benefit":
            if self.value == "amount":
                pass
            elif isinstance(self.value, (int, float)) and not isinstance(
                self.value, bool
            ):
                if self.value < 0:
                    raise ConfigError(f"{prefix}.value must not be negative")
                self.value = Decimal(str(self.value))
            else:
                raise ConfigError(f'{prefix}.value must be a number or "amount"')
        elif self.value is not None:
            raise ConfigError(f"{prefix}.value is only used with kind benefit")

    def matches(self, product):
        """Check if a product name matches, with * and ? wildcards."""

        return fnmatchcase(product, self.product)


class Config:
    def __init__(self, path):
        """Load and validate configuration from a TOML file."""

        self.path = Path(path)
        self.root = self.path.parent

        try:
            with self.path.open("rb") as f:
                self.data = tomllib.load(f)
        except FileNotFoundError:
            raise ConfigError(f"File not found: {self.path}") from None
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"{self.path}: {e}") from None
        _check_keys("", self.data, SETTINGS)

        self.output = self.resolve(self.data.get("output", "output"))
        self.templates = self.data.get("templates")
        if self.templates:
            self.templates = self.resolve(self.templates)

        self.org = self._org()
        self.contacts = self._source("contacts", CONTACT_COLUMNS, {})
        self.gifts = self._source("gifts", GIFT_COLUMNS, {"date_format": "%m/%d/%Y"})

        self.programs = self._section("programs")
        self.aliases = self._section("aliases")
        self.third_party = self._third_party()
        self.rules = self._rules()
        self._check_units()
        self.letters = self._letters()
        self.email = self._settings("email", EMAIL_DEFAULTS)
        self.smtp = self._settings("smtp", SMTP_DEFAULTS)

        if not self.email["address"]:
            raise ConfigError("Missing setting: email.address")
        if self.smtp["security"] not in SECURITY:
            choices = ", ".join(sorted(SECURITY))
            raise ConfigError(f"smtp.security must be one of: {choices}")
        if not _whole_number(self.smtp["port"]):
            raise ConfigError("smtp.port must be a number like 465")
        limit = self.smtp["limit"]
        if limit is not None and not (_whole_number(limit) and limit > 0):
            raise ConfigError("smtp.limit must be a number like 50, or left out")

    def resolve(self, path):
        """Resolve a path relative to the configuration file."""

        return (self.root / path).resolve()

    def letter(self, name=None):
        """Get a letter by name, or the only one if no name is given."""

        if name is None:
            if len(self.letters) > 1:
                names = ", ".join(self.letters)
                raise ConfigError(f"Choose a letter: {names}")
            return next(iter(self.letters.values()))
        if name not in self.letters:
            raise ConfigError(f"Unknown letter: {name}")
        return self.letters[name]

    def _section(self, name):
        """Get a section as a table, empty if missing."""

        section = self.data.get(name, {})
        if not isinstance(section, dict):
            raise ConfigError(f"[{name}] must be a table")
        return section

    def _settings(self, name, defaults):
        """Get a section with defaults for missing settings."""

        section = self._section(name)
        _check_keys(name, section, defaults)
        return {**defaults, **section}

    def _org(self):
        """Get organization details."""

        org = self._settings("org", ORG_DEFAULTS)
        if not org["name"]:
            raise ConfigError("Missing setting: org.name")
        if org["logo"]:
            org["logo"] = self.resolve(org["logo"])
            if not org["logo"].is_file():
                raise ConfigError(f"Logo not found: {org['logo']}")

        # signer is optional, but both fields exist for templates
        signer = org["signer"]
        if not isinstance(signer, dict):
            raise ConfigError("org.signer must be a table")
        _check_keys("org.signer", signer, {"name", "title"})
        org["signer"] = {"name": "", "title": "", **signer}

        return org

    def _source(self, name, columns, defaults):
        """Get the settings for an input file and its columns."""

        section = self._settings(name, {"file": None, "columns": {}, **defaults})
        if not section["file"]:
            raise ConfigError(f"Missing setting: {name}.file")
        section["file"] = self.resolve(section["file"])

        # check column mapping
        mapping = section["columns"]
        missing = columns["required"] - set(mapping)
        if missing:
            keys = ", ".join(f"{name}.columns.{key}" for key in sorted(missing))
            raise ConfigError(f"Missing settings: {keys}")
        _check_keys(
            f"{name}.columns", mapping, columns["required"] | columns["optional"]
        )
        section["columns"] = dict(mapping)

        return section

    def _third_party(self):
        """Get the settings that recognize third-party names."""

        settings = self._settings("third_party", THIRD_PARTY_DEFAULTS)
        for key in ("markers", "funds"):
            values = settings[key]
            if not isinstance(values, list) or not all(
                isinstance(v, str) and v for v in values
            ):
                raise ConfigError(f"third_party.{key} must be a list of names")
        if not settings["separator"]:
            raise ConfigError("third_party.separator must not be empty")
        return settings

    def _rules(self):
        """Get product rules in file order."""

        rules = self.data.get("rules", [])
        if not isinstance(rules, list):
            raise ConfigError("[[rules]] must be an array of tables")
        return [Rule(index, rule) for index, rule in enumerate(rules, start=1)]

    def _check_units(self):
        """Require a price column when a rule gives a value per unit."""

        if "price" in self.gifts["columns"]:
            return
        for rule in self.rules:
            if rule.kind == "benefit" and rule.value != "amount":
                raise ConfigError(
                    f"{rule.name} gives a value per unit, so map the sales price "
                    'column, e.g. price = "Sales Price" in [gifts.columns]'
                )

    def _letters(self):
        """Get letters by name."""

        letters = {}
        for name, settings in self._section("letters").items():
            if not isinstance(settings, dict):
                raise ConfigError(f"[letters.{name}] must be a table")
            _check_keys(f"letters.{name}", settings, LETTER_DEFAULTS)
            letters[name] = Letter(name, {**LETTER_DEFAULTS, **settings})
        if not letters:
            raise ConfigError("Missing setting: at least one [letters.<name>] table")
        return letters


def _whole_number(value):
    """Check for a whole number of zero or more, but not true or false."""

    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _check_keys(prefix, section, allowed):
    """Reject settings that aren't allowed."""

    unknown = set(section) - set(allowed)
    if unknown:
        keys = ", ".join(
            f"{prefix}.{key}" if prefix else key for key in sorted(unknown)
        )
        raise ConfigError(f"Unknown settings: {keys}")
