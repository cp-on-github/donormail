import datetime
from decimal import Decimal

from donormail.config import Config
from donormail.gifts import Contact, Gift, load_contacts, load_gifts


def test_load_example(workdir):
    """Example gifts and contacts load with programs mapped."""

    config = Config(workdir / "basic/config.toml")
    gifts, gift_warnings = load_gifts(config)
    contacts, contact_warnings = load_contacts(config)

    assert gift_warnings == []
    assert contact_warnings == []
    assert len(gifts) == 11
    assert gifts[0].date == datetime.date(2025, 1, 1)
    assert gifts[0].amount == Decimal("25.00")
    assert gifts[0].program == "Education"
    assert gifts[0].line == 2
    assert set(contacts) == {
        "John Appleseed",
        "John Doe",
        "John Smith",
        "Jane Smith",
        "Main Street Grocery",
    }
    assert contacts["John Appleseed"].has_address
    assert not contacts["Jane Smith"].has_email


def test_load_gifts_warnings(workdir):
    """Bad rows are skipped with warnings and checked against the file total."""

    items = workdir / "basic/gifts.csv"
    with items.open("a") as f:
        f.write("13/1/2025,20,Bad Date,Check,10,Food\n")
        f.write("4/1/2025,21,Bad Amount,Check,ten,Food\n")
        f.write("4/2/2025,22,,Cash,20,Food\n")
        f.write("4/2/2025,23,,Cash,5,Food\n")
        f.write(",,,,999.00,\n")

    gifts, warnings = load_gifts(Config(workdir / "basic/config.toml"))
    assert len(gifts) == 11
    assert warnings == [
        "gifts line 14: Invalid date '13/1/2025', skipped",
        "gifts line 15: Invalid amount 'ten', skipped",
        "gifts: 2 without a donor name totaling 25.00, skipped",
        "gifts: Loaded gifts total 1,000.00 but file total is 999.00",
    ]


def test_total_row_in_date_column(workdir):
    """A total or footer in the date column is a summary row, not a gift."""

    with (workdir / "basic/gifts.csv").open("a") as f:
        f.write("TOTAL,,,,975.00,\n")
        f.write("Cash Basis Monday,,,,,\n")

    gifts, warnings = load_gifts(Config(workdir / "basic/config.toml"))
    assert len(gifts) == 11
    assert warnings == []

    # a wrong total is still reported
    with (workdir / "basic/gifts.csv").open("a") as f:
        f.write("TOTAL,,,,900.00,\n")
    _, warnings = load_gifts(Config(workdir / "basic/config.toml"))
    assert warnings == ["gifts: Loaded gifts total 975.00 but file total is 900.00"]


def test_aliases_and_duplicates(workdir):
    """Aliases merge names, and duplicate contacts keep the first."""

    config_path = workdir / "basic/config.toml"
    with config_path.open("a") as f:
        f.write('\n[aliases]\n"Jane Smith" = "John Smith"\n')

    config = Config(config_path)
    gifts, _ = load_gifts(config)
    contacts, warnings = load_contacts(config)

    assert "Jane Smith" not in {gift.name for gift in gifts}
    assert contacts["John Smith"].email == "bounce@email.com"
    assert warnings == ["contacts line 5: Duplicate contact 'John Smith', skipped"]


def test_value_column(tmp_path):
    """A value received makes a gift a purchase deductible above its value."""

    (tmp_path / "event.csv").write_text(
        "Date,Donor,Donation,Items,Value\n"
        "10/24/2025,Jane,50,1 dress,277.52\n"
        "10/24/2025,Ann,300,1 dress,$200.00\n"
        "10/24/2025,Sue,25,,\n"
        "10/24/2025,Bad,25,1 dress,abc\n"
    )
    (tmp_path / "config.toml").write_text(
        '[org]\nname = "Org"\n'
        '[contacts]\nfile = "event.csv"\ncolumns = { name = "Donor" }\n'
        '[gifts]\nfile = "event.csv"\n'
        'columns = { date = "Date", name = "Donor", amount = "Donation", '
        'description = "Items", value = "Value" }\n'
        "[letters.event]\nyear = 2025\n"
        '[email]\naddress = "a@example.org"\n'
    )

    gifts, warnings = load_gifts(Config(tmp_path / "config.toml"))
    jane, ann, sue = gifts
    assert (jane.kind, jane.value, jane.deductible) == (
        "benefit",
        Decimal("277.52"),
        Decimal("0.00"),
    )
    assert jane.description == "1 dress"
    assert jane.item == "1 dress"
    assert (ann.kind, ann.deductible) == ("benefit", Decimal("100.00"))
    assert (sue.kind, sue.deductible) == ("cash", Decimal("25.00"))
    assert warnings == ["gifts line 5: Invalid value 'abc', skipped"]


def test_deductible():
    """Deductible amount depends on the kind of gift."""

    gift = Gift(datetime.date(2025, 1, 1), "Jane", Decimal("150.00"))
    assert gift.deductible == Decimal("150.00")

    gift.kind = "benefit"
    gift.value = Decimal("60.00")
    assert gift.deductible == Decimal("90.00")

    gift.value = Decimal("200.00")
    assert gift.deductible == Decimal("0.00")

    for kind in ("in-kind", "daf"):
        gift.kind = kind
        assert gift.deductible == Decimal("0.00")


def test_contact_fields():
    """Contacts normalize email, state, and zip."""

    contact = Contact("Jane", "Jane@Example.COM", "1 Main", "Town", "tx", "2134")
    assert contact.email == "jane@example.com"
    assert contact.state == "TX"
    assert contact.zip == "02134"
    assert contact.has_address

    assert Contact("Jane", zip="12345-6789").zip == "12345-6789"
    assert not Contact("Jane", street="1 Main").has_address


def test_names_and_items(tmp_path):
    """Nested names show their last part, without deleted markers."""

    (tmp_path / "gifts.csv").write_text(
        "Date,Donor,Amount,Class,Product,Memo,Price\n"
        "2/15/2025,Jane (deleted),75,PROGRAMS:EVENTS,Events:T-Shirt (deleted),Paid,75\n"
        "3/1/2025,Jane,50,PROGRAMS:SCHOOL (deleted),Donations:General,Books,\n"
        "4/1/2025,Jane,90,OLD:FOOD,In-Kind:Goods,Two laptops,\n"
        "5/1/2025,Jane,10,,In-Kind:Goods,,\n"
    )
    (tmp_path / "config.toml").write_text(
        '[org]\nname = "Org"\n'
        '[contacts]\nfile = "gifts.csv"\ncolumns = { name = "Donor" }\n'
        '[gifts]\nfile = "gifts.csv"\ndate_format = "%m/%d/%Y"\n'
        'columns = { date = "Date", name = "Donor", amount = "Amount", '
        'program = "Class", product = "Product", description = "Memo", '
        'price = "Price" }\n'
        '[programs]\n"OLD:FOOD" = "Food Pantry"\n'
        '[[rules]]\nproduct = "Events:T-Shirt"\nvalue = 15\n'
        '[[rules]]\nproduct = "In-Kind:*"\nkind = "in-kind"\n'
        "[letters.annual]\nyear = 2025\n"
        '[email]\naddress = "a@example.org"\n'
    )

    gifts, _ = load_gifts(Config(tmp_path / "config.toml"))
    shirt, books, laptops, goods = gifts

    # rules match full product names without the deleted marker
    assert (shirt.name, shirt.kind, shirt.value) == ("Jane", "benefit", Decimal(15))
    assert (shirt.program, shirt.product, shirt.item) == (
        "EVENTS",
        "Events:T-Shirt",
        "T-Shirt",
    )
    assert (books.program, books.item) == ("SCHOOL", "General")

    # programs are renamed by full name, and non-cash gifts use the description
    assert (laptops.program, laptops.item) == ("Food Pantry", "Two laptops")
    assert goods.item == "Goods"
