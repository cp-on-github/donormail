import datetime
from decimal import Decimal

import pytest

from donormail.config import Config, ConfigError, Rule
from donormail.gifts import (
    Gift,
    _classify,
    load_contacts,
    load_gifts,
    split_third_party,
)
from donormail.statements import build_statements

SETTINGS = {
    "markers": ["NO RECEIPT"],
    "funds": ["Family Donor Fund"],
    "separator": ":",
}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("NO RECEIPT Workplace Giving:Jane Doe", ("Workplace Giving", "Jane Doe")),
        ("NO RECEIPT Hometown Bank:Jane Doe", ("Hometown Bank", "Jane Doe")),
        (
            "NO RECEIPT Community Foundation, Inc.",
            ("Community Foundation, Inc.", None),
        ),
        ("NO RECEIPT Workplace Giving", ("Workplace Giving", None)),
        ("NO RECEIPTS Workplace Giving:Jane Doe", None),
        ("NO RECEIPT:Workplace Giving:Jane Doe", ("Workplace Giving", "Jane Doe")),
        ("NO RECEIPT: Workplace Giving : Jane Doe ", ("Workplace Giving", "Jane Doe")),
        ("NO RECEIPT:Community Foundation", ("Community Foundation", None)),
        ("Family Donor Fund", ("Family Donor Fund", None)),
        ("Family Donor Fund:Jane Doe", ("Family Donor Fund", "Jane Doe")),
        ("Jane Doe", None),
        ("NO RECEIPTS:Workplace Giving:Jane Doe", None),
        ("NO RECEIPT:", ("NO RECEIPT", None)),
        ("NO RECEIPT", ("NO RECEIPT", None)),
    ],
)
def test_split_third_party(name, expected):
    """Third-party names split into fund and donor."""

    assert split_third_party(name, SETTINGS) == expected


def by_name(workdir):
    """Load the QuickBooks example and build annual statements by name."""

    config = Config(workdir / "quickbooks/config.toml")
    contacts, _ = load_contacts(config)
    gifts, warnings = load_gifts(config)
    statements, _ = build_statements(config.letter("annual"), gifts, contacts)
    return {s.name: s for s in statements}, warnings


def test_qbo_gifts(workdir):
    """Rules, third parties, and aliases classify the QuickBooks example."""

    statements, warnings = by_name(workdir)
    community = "Community Foundation, Inc. without a donor name totaling 2,000.00"
    assert warnings == [
        "gifts: 1 without a donor name totaling 10.00, skipped",
        f"gifts: 1 through {community}, skipped",
    ]

    # fund contacts without gifts, e.g. "NO RECEIPT Workplace Giving", are not donors
    assert list(statements) == ["Jane Doe", "ANONYMOUS Pat Kim", "Acme Corp", "Sam Lee"]

    jane = statements["Jane Doe"]
    assert [g.kind for g in jane.gifts] == ["cash", "benefit", "benefit", "third-party"]
    shirt, raffle = jane.benefits
    assert (shirt.units, shirt.value, shirt.deductible) == (
        Decimal(3),
        Decimal("45.00"),
        Decimal("30.00"),
    )
    assert (raffle.value, raffle.deductible) == (Decimal("25.00"), Decimal("0.00"))
    assert jane.third_party[0].fund == "Workplace Giving"
    assert jane.deductible == Decimal("130.00")
    assert jane.third_party_total == Decimal("500.00")
    assert jane.salutation == "Jane"
    assert jane.has_receipt

    # own contact wins over the third-party contact
    assert jane.contact is not None
    assert jane.contact.email == "jane@example.com"

    # third-party only donors use the third-party contact
    sam = statements["Sam Lee"]
    assert not sam.has_receipt
    assert sam.deductible == Decimal("0.00")
    assert sam.contact is not None
    assert sam.contact.email == "sam@example.com"
    assert sam.salutation == "Sam Lee"

    # deleted classes are renamed like current ones
    pat = statements["ANONYMOUS Pat Kim"]
    assert pat.salutation == "Pat"
    assert pat.programs == ["Housing"]

    acme = statements["Acme Corp"]
    assert acme.in_kind[0].description == "Two laptops"
    assert acme.deductible == Decimal("0.00")
    assert acme.method == "mail"


def test_value_column_overrides_rule(workdir):
    """A value from the gifts file replaces a rule value."""

    config_path = workdir / "quickbooks/config.toml"
    config_path.write_text(
        config_path.read_text().replace(
            'description = "Memo/Description"',
            'description = "Memo/Description"\nvalue = "Value"',
        )
    )
    gifts = workdir / "quickbooks/gifts.csv"
    gifts.write_text(
        gifts.read_text()
        .replace("Transaction Type\n", "Transaction Type,Value\n")
        .replace("SR-1002,Receipt\n", "SR-1002,Receipt,20.00\n", 1)
    )

    statements, _ = by_name(workdir)
    shirt = statements["Jane Doe"].benefits[0]
    assert shirt.value == Decimal("20.00")


def test_value_column_ignored_for_in_kind(workdir):
    """A value on a non-cash gift leaves it non-cash, without a value."""

    gifts = workdir / "basic/gifts.csv"
    gifts.write_text(gifts.read_text().replace("Food,In-Kind,,", "Food,In-Kind,500,"))

    config = Config(workdir / "basic/config.toml")
    grocery = [g for g in load_gifts(config)[0] if g.name == "Main Street Grocery"]
    assert [(g.kind, g.value) for g in grocery] == [("in-kind", Decimal("0.00"))]


def test_invalid_price(workdir):
    """Unreadable prices skip the gift with a warning."""

    gifts = workdir / "quickbooks/gifts.csv"
    text = gifts.read_text().replace("Events:T-Shirt,25.00", "Events:T-Shirt,x")
    gifts.write_text(text)

    _, warnings = by_name(workdir)
    assert "gifts line 7: Invalid price 'x', skipped" in warnings


def test_partial_payment_units(workdir):
    """A partial payment of a pledge receives value for the part paid."""

    gifts = workdir / "quickbooks/gifts.csv"
    text = gifts.read_text().replace("75.00  ,Events:T-Shirt", "37.50  ,Events:T-Shirt")
    gifts.write_text(text.replace("$ 4,010.00", "$ 3,972.50"))

    statements, _ = by_name(workdir)
    shirt = statements["Jane Doe"].benefits[0]
    assert (shirt.units, shirt.value, shirt.deductible) == (
        Decimal("1.5"),
        Decimal("22.50"),
        Decimal("15.00"),
    )


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        ("value = 5", "Missing setting: rules[1].product"),
        ('product = "A"', 'rules[1].value must be a number or "amount"'),
        ('product = "A"\nvalue = -1', "must not be negative"),
        ('product = "A"\nvalue = "all"', 'must be a number or "amount"'),
        ('product = "A"\nkind = "gift"', "rules[1].kind must be one of"),
        ('product = "A"\nkind = "in-kind"\nvalue = 5', "only used with kind benefit"),
        ('product = "A"\nvalue = 5\nprice = 9', "Unknown settings: rules[1].price"),
    ],
)
def test_invalid_rules(workdir, rule, message):
    """Invalid rules raise a readable error."""

    config_path = workdir / "quickbooks/config.toml"
    content = config_path.read_text().split("# value received per unit")[0]
    config_path.write_text(
        content
        + f"\n[[rules]]\n{rule}\n"
        + "\n[letters.annual]\nyear = 2025\n"
        + '\n[email]\naddress = "a@example.org"\n'
    )
    with pytest.raises(ConfigError, match=message.replace("[", r"\[")):
        Config(config_path)


def test_invalid_third_party(workdir):
    """Third-party settings must be lists of names."""

    config_path = workdir / "quickbooks/config.toml"
    config_path.write_text(
        config_path.read_text().replace(
            'markers = ["NO RECEIPT"]', 'markers = "NO RECEIPT"'
        )
    )
    with pytest.raises(ConfigError, match="third_party.markers must be a list"):
        Config(config_path)


def test_letter_product_filters(workdir):
    """Letters can include or exclude gifts by product."""

    config_path = workdir / "quickbooks/config.toml"
    content = config_path.read_text().replace(
        "[letters.annual]\nyear = 2025",
        "[letters.annual]\nyear = 2025\n"
        'exclude_products = ["Events:*"]\n\n'
        '[letters.events]\nyear = 2025\nproducts = ["Events:*", "In-Kind:*"]',
    )
    config_path.write_text(content)
    config = Config(config_path)
    contacts, _ = load_contacts(config)
    gifts, _ = load_gifts(config)

    annual, _ = build_statements(config.letter("annual"), gifts, contacts)
    jane = next(s for s in annual if s.name == "Jane Doe")
    assert [g.kind for g in jane.gifts] == ["cash", "third-party"]

    events, _ = build_statements(config.letter("events"), gifts, contacts)
    with_gifts = {s.name: s for s in events if s.has_items}
    assert list(with_gifts) == ["Jane Doe", "Acme Corp"]
    assert [g.product for g in with_gifts["Jane Doe"].gifts] == [
        "Events:T-Shirt",
        "Events:Raffle Tickets",
    ]


def test_invalid_product_filter(workdir):
    """Product filters must be lists of products."""

    config_path = workdir / "quickbooks/config.toml"
    config_path.write_text(
        config_path.read_text().replace(
            'products = ["Events:*"]', 'products = "Events:*"'
        )
    )
    with pytest.raises(ConfigError, match="letters.welcome.products must be a list"):
        Config(config_path)


@pytest.mark.parametrize(
    ("amount", "value", "deductible"),
    [
        ("75", "45", "30"),
        ("100", "150", "0"),
        ("-25", "-15", "-10"),
        ("-100", "-150", "0"),
    ],
)
def test_benefit_deductible(amount, value, deductible):
    """Payments never go below zero deductible, and refunds never above it."""

    gift = Gift(datetime.date(2025, 2, 1), "Jane", Decimal(amount))
    gift.kind, gift.value = "benefit", Decimal(value)
    assert gift.deductible == Decimal(deductible)


def test_zero_value_is_cash():
    """A rule giving nothing of value leaves the gift as cash."""

    rule = Rule(1, {"product": "Events:Pin", "value": 0})
    gift = Gift(datetime.date(2025, 2, 1), "Jane", Decimal(10), product="Events:Pin")
    _classify(gift, Decimal(0), None, [rule])
    assert (gift.kind, gift.deductible) == ("cash", Decimal(10))


def test_item_names():
    """Items are the product name, or the description for non-cash gifts."""

    date = datetime.date(2025, 2, 1)
    shirt = Gift(date, "Jane", Decimal(20), product="Events:T-Shirt")
    assert shirt.item == "Events:T-Shirt"

    shirt = Gift(
        date, "Jane", Decimal(20), product="Events:T-Shirt", product_name="T-Shirt"
    )
    assert shirt.item == "T-Shirt"
    dress = Gift(date, "Jane", Decimal(20), description="1 dress")
    assert dress.item == "1 dress"

    laptops = Gift(
        date, "Jane", Decimal(0), product="In-Kind:Goods", description="Laptops"
    )
    laptops.kind = "in-kind"
    assert laptops.item == "Laptops"


def test_bare_marker_skipped(workdir):
    """Gifts under a marker alone are skipped with a warning."""

    with (workdir / "quickbooks/gifts.csv").open("a") as f:
        f.write(
            ",03/01/2025,NO RECEIPT,EDUCATION,40.00,Donations:General,,,SR-9,Receipt\n"
        )

    statements, warnings = by_name(workdir)
    assert "NO RECEIPT" not in statements
    assert (
        "gifts: 1 through NO RECEIPT without a donor name totaling 40.00, skipped"
        in warnings
    )


def test_price_required_for_unit_values(tmp_path):
    """Rules with a value per unit need a price column."""

    base = (
        '[org]\nname = "Org"\n'
        '[contacts]\nfile = "c.csv"\ncolumns = { name = "Donor" }\n'
        '[gifts]\nfile = "g.csv"\n'
        'columns = { date = "Date", name = "Donor", amount = "Amount" }\n'
        "[letters.annual]\nyear = 2025\n"
        '[email]\naddress = "a@example.org"\n'
    )
    path = tmp_path / "config.toml"
    path.write_text(base + '[[rules]]\nproduct = "Raffle"\nvalue = "amount"\n')
    Config(path)

    path.write_text(base + '[[rules]]\nproduct = "Shirt"\nvalue = 15\n')
    with pytest.raises(ConfigError, match=r"rules\[1\] gives a value per unit"):
        Config(path)
