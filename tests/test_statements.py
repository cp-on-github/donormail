import datetime
from decimal import Decimal

from donormail.config import Config
from donormail.gifts import Contact, Gift, load_contacts, load_gifts
from donormail.statements import Statement, build_statements


def gift(month, day, amount, program=""):
    """Create a 2025 gift for Jane."""

    return Gift(
        datetime.date(2025, month, day), "Jane", Decimal(amount), program=program
    )


def test_statement_rows_by_date():
    """Rows combine same-day gifts in date order with sorted programs."""

    statement = Statement(
        "Jane",
        [
            gift(10, 15, "50", "Food"),
            gift(2, 1, "25", "Housing"),
            gift(2, 1, "10", "Education"),
            gift(2, 1, "5", "Education"),
        ],
        None,
    )
    assert statement.rows == [
        {
            "date": datetime.date(2025, 2, 1),
            "programs": ["Education", "Housing"],
            "amount": Decimal(40),
        },
        {
            "date": datetime.date(2025, 10, 15),
            "programs": ["Food"],
            "amount": Decimal(50),
        },
    ]
    assert statement.total == Decimal(90)
    assert statement.largest == Decimal(50)


def test_statement_contributed():
    """Contributed leaves out in-kind and third-party gifts."""

    shirt = gift(2, 1, "75", "Events")
    shirt.kind, shirt.value = "benefit", Decimal(45)
    auction = gift(2, 1, "100", "Events")
    auction.kind, auction.value = "benefit", Decimal(150)
    laptop = gift(3, 1, "250", "In-Kind")
    laptop.kind = "in-kind"
    grant = gift(4, 1, "500", "Food")
    grant.kind, grant.fund = "third-party", "Workplace Giving"
    statement = Statement(
        "Jane", [gift(1, 1, "100", "Food"), shirt, auction, laptop, grant], None
    )

    # an item bought below its value has nothing deductible, never less
    assert statement.contributed == Decimal(275)
    assert statement.deductible == Decimal(130)
    assert statement.nondeductible == Decimal(145)
    assert statement.programs == ["Events", "Food"]
    assert statement.funds == ["Workplace Giving"]


def test_statement_third_party_rows():
    """Third-party rows combine same-day gifts through the same fund."""

    gifts = [gift(4, 1, "60"), gift(4, 1, "40"), gift(4, 1, "25"), gift(5, 1, "10")]
    work, family = "Workplace Giving", "Family Donor Fund"
    for item, fund in zip(gifts, [work, work, family, work]):
        item.kind, item.fund = "third-party", fund
    statement = Statement("Jane", gifts, None)
    assert [(r["fund"], r["amount"]) for r in statement.third_party_rows] == [
        ("Workplace Giving", Decimal(100)),
        ("Family Donor Fund", Decimal(25)),
        ("Workplace Giving", Decimal(10)),
    ]


def test_statement_method():
    """Email is preferred over mail, and no contact means none."""

    gifts = [gift(1, 1, "10")]
    full = Contact("Jane", "j@example.com", "1 Main", "Town", "TX", "12345")
    address = Contact("Jane", "", "1 Main", "Town", "TX", "12345")

    assert Statement("Jane", gifts, full).method == "email"
    assert Statement("Jane", gifts, address).method == "mail"
    assert Statement("Jane", gifts, Contact("Jane")).method == "none"
    assert Statement("Jane", gifts, None).method == "none"
    assert not Statement("Jane", gifts, None).has_contact


def test_build_statements(workdir):
    """Statements cover contacts, then donors only in gifts, within the period."""

    config = Config(workdir / "basic/config.toml")
    with (workdir / "basic/gifts.csv").open("a") as f:
        f.write("1/2/2026,30,John Smith,Check,40,Food\n")

    contacts, _ = load_contacts(config)
    gifts, _ = load_gifts(config)
    statements, warnings = build_statements(config.letter(), gifts, contacts)

    names = [statement.name for statement in statements]
    assert names == [
        "John Appleseed",
        "John Doe",
        "John Smith",
        "Jane Smith",
        "Main Street Grocery",
        "Mary Major",
    ]
    assert warnings == ["gifts: 1 outside 2025-01-01 to 2025-12-31, skipped"]

    smith = statements[2]
    assert smith.total == Decimal("100.00")
    assert smith.contact is not None
    assert smith.contact.email == "john.smith@example.com"
