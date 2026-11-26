import re
from decimal import ROUND_HALF_UP, Decimal

from donormail.sources import CENTS, parse_date, parse_money, read_table, text

KINDS = ("cash", "benefit", "in-kind", "third-party")
ZERO = Decimal("0.00")
ONE = Decimal(1)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# QuickBooks adds this to names of deleted customers, products, and classes
DELETED = " (deleted)"


class Gift:
    def __init__(
        self,
        date,
        name,
        amount,
        program="",
        product="",
        description="",
        units=ONE,
        line=0,
        product_name=None,
    ):
        """Create a gift from one line of the gifts file."""

        self.date = date
        self.name = name
        self.amount = amount
        self.program = program
        self.product = product
        self.description = description
        self.units = units
        self.line = line

        # last part of a nested product name, for letters
        self.product_name = product if product_name is None else product_name

        # classification defaults to a fully deductible cash gift
        self.kind = "cash"
        self.value = ZERO
        self.fund = ""

    @property
    def deductible(self):
        """Tax-deductible portion of the gift."""

        if self.kind == "cash":
            return self.amount
        if self.kind == "benefit":
            # a payment is never below zero, and a refund never above it
            deductible = self.amount - self.value
            if self.amount < ZERO:
                return min(deductible, ZERO)
            return max(deductible, ZERO)
        return ZERO

    @property
    def item(self):
        """What the gift paid for, or what was given for non-cash gifts."""

        if self.kind == "in-kind":
            return self.description or self.product_name
        return self.product_name or self.description

    def __repr__(self):
        """Show the gift's main details."""

        return f"Gift({self.date}, {self.name!r}, {self.amount}, {self.kind})"


class Contact:
    def __init__(
        self, name, email="", street="", city="", state="", zip="", salutation=""
    ):
        """Create a contact from one line of the contacts file."""

        self.name = name
        self.salutation = salutation
        self.third_party = False
        self.email = email.lower()
        self.street = street
        self.city = city
        self.state = state.upper()

        # restore leading zeros lost when zip codes are stored as numbers
        self.zip = zip.zfill(5) if zip.isdigit() else zip

    @property
    def has_email(self):
        """Contact has an email that looks valid."""

        return bool(EMAIL.match(self.email))

    @property
    def has_address(self):
        """Contact has a complete mailing address."""

        return all((self.street, self.city, self.state, self.zip))

    def __repr__(self):
        """Show the contact's name and email."""

        return f"Contact({self.name!r}, {self.email!r})"


def own_contacts(contacts):
    """Names of contacts that are donors themselves, not third parties."""

    return [name for name, contact in contacts.items() if not contact.third_party]


def clean_name(value):
    """Clean up spaces in a name and remove the deleted marker."""

    name = " ".join(text(value).split())
    return name.removesuffix(DELETED)


def last_part(name, separator):
    """Get the last part of a nested name, e.g. "Events:T-Shirt" gives "T-Shirt"."""

    return name.split(separator)[-1].strip()


def split_third_party(name, settings):
    """Split a third-party name into (fund, donor), or None if not one.

    Names are a parent and child, e.g. "Parent:Child", and the donor is
    always the last part. A marker starts the parent name, so
    "NO RECEIPT Workplace Giving:Jane Doe" gives ("Workplace Giving",
    "Jane Doe"). A marker may also stand alone as the parent, so
    "NO RECEIPT:Workplace Giving:Jane Doe" gives the same. A fund is the
    whole parent name, so "Family Donor Fund:Jane Doe" gives
    ("Family Donor Fund", "Jane Doe"). Without a child the donor is None,
    e.g. "NO RECEIPT Workplace Giving" gives ("Workplace Giving", None),
    and a marker alone gives ("NO RECEIPT", None).
    """

    separator = settings["separator"]
    parts = [part.strip() for part in name.split(separator)]
    parts = [part for part in parts if part]
    if not parts:
        return None
    parent, children = parts[0], parts[1:]

    if parent in settings["funds"]:
        return parent, children[-1] if children else None

    for marker in settings["markers"]:
        if parent == marker and not children:
            return marker, None
        if parent == marker:
            if len(children) == 1:
                return children[0], None
            return separator.join(children[:-1]), children[-1]
        if parent.startswith(marker + " "):
            fund = parent[len(marker) :].strip()
            return fund, children[-1] if children else None

    return None


def load_contacts(config):
    """Load contacts by name, with warnings for skipped rows.

    Contacts under third-party names fill in for donors without their own.
    """

    source = config.contacts
    contacts, warnings = {}, []
    fallbacks = {}

    for record in read_table(source["file"], source["columns"]):
        name = clean_name(record["name"])
        if not name:
            continue
        name = config.aliases.get(name, name)

        contact = Contact(
            name,
            email=text(record.get("email")),
            street=text(record.get("street")),
            city=text(record.get("city")),
            state=text(record.get("state")),
            zip=text(record.get("zip")),
            salutation=clean_name(record.get("salutation")),
        )

        # set third-party contacts aside until all own contacts are known
        split = split_third_party(name, config.third_party)
        if split:
            if split[1] is None:
                continue
            donor = config.aliases.get(split[1], split[1])
            contact.name = donor
            contact.third_party = True
            fallbacks.setdefault(donor, contact)
            continue

        # keep the first of duplicate contacts
        if name in contacts:
            warnings.append(
                f"contacts line {record['line']}: Duplicate contact {name!r}, skipped"
            )
            continue
        contacts[name] = contact

    for donor, contact in fallbacks.items():
        contacts.setdefault(donor, contact)

    return contacts, warnings


def load_gifts(config):
    """Load and classify gifts, with warnings for skipped rows and a wrong total."""

    source = config.gifts
    gifts, warnings = [], []
    total = None
    unnamed = []
    no_donor = {}

    for record in read_table(source["file"], source["columns"]):
        line = record["line"]
        name = clean_name(record["name"])

        # rows without a donor or a real date are summary rows, e.g. TOTAL
        if not name and not _is_date(record["date"], source["date_format"]):
            if text(record["amount"]):
                total = _parse_total(record["amount"], line, warnings)
            continue

        try:
            date = parse_date(record["date"], source["date_format"])
            amount = parse_money(record["amount"])
            units = _parse_units(amount, record.get("price"))
            value = _parse_value(record.get("value"))
        except ValueError as e:
            warnings.append(f"gifts line {line}: {e}, skipped")
            continue

        # gifts without a donor, e.g. event cash, cannot be acknowledged
        if not name:
            unnamed.append(amount)
            continue
        name = config.aliases.get(name, name)

        # third-party gifts need a child name for the donor
        fund = None
        split = split_third_party(name, config.third_party)
        if split:
            fund, donor = split
            if donor is None:
                no_donor.setdefault(fund, []).append(amount)
                continue
            name = config.aliases.get(donor, donor)

        # programs are renamed by full name, or shown by their last part
        separator = config.third_party["separator"]
        program = clean_name(record.get("program"))
        if program in config.programs:
            program = config.programs[program]
        else:
            program = last_part(program, separator)

        product = clean_name(record.get("product"))
        gift = Gift(
            date,
            name,
            amount,
            program=program,
            product=product,
            description=text(record.get("description")),
            units=units,
            line=line,
            product_name=last_part(product, separator),
        )
        _classify(gift, value, fund, config.rules)
        gifts.append(gift)

    if unnamed:
        warnings.append(
            f"gifts: {len(unnamed)} without a donor name "
            f"totaling {sum(unnamed, ZERO):,.2f}, skipped"
        )
    for fund, amounts in no_donor.items():
        warnings.append(
            f"gifts: {len(amounts)} through {fund} without a donor name "
            f"totaling {sum(amounts, ZERO):,.2f}, skipped"
        )

    # verify gifts against the file total, including skipped gifts
    if total is not None:
        skipped = unnamed + [a for amounts in no_donor.values() for a in amounts]
        parsed = sum((gift.amount for gift in gifts), sum(skipped, ZERO))
        if parsed != total:
            warnings.append(
                f"gifts: Loaded gifts total {parsed:,.2f} "
                f"but file total is {total:,.2f}"
            )

    return gifts, warnings


def _classify(gift, value, fund, rules):
    """Set a gift's kind and value from its fund, the rules, and its value column."""

    # third-party gifts are acknowledged to the donor but never deductible
    if fund is not None:
        gift.fund = fund
        gift.kind = "third-party"
        return

    # the first rule matching the product applies
    rule = next((r for r in rules if r.matches(gift.product)), None)
    if rule and rule.kind == "in-kind":
        gift.kind = "in-kind"
    elif rule:
        gift.kind = "benefit"
        if rule.value == "amount":
            gift.value = gift.amount
        else:
            gift.value = (rule.value * gift.units).quantize(
                CENTS, rounding=ROUND_HALF_UP
            )

    # a value from the gifts file overrides rules, but non-cash gifts never
    # have a value received
    if value > ZERO and gift.kind != "in-kind":
        gift.kind = "benefit"
        gift.value = value

    # nothing of value received, e.g. a token item, is a cash gift
    if gift.kind == "benefit" and gift.value == ZERO:
        gift.kind = "cash"


def _parse_units(amount, price):
    """Count the units an amount pays for at a price, or one without a price.

    A partial payment on a pledge pays for part of a unit.
    """

    if not text(price):
        return ONE
    try:
        price = parse_money(price)
    except ValueError:
        raise ValueError(f"Invalid price {text(price)!r}") from None
    return amount / price if price else ONE


def _parse_value(value):
    """Parse an optional value received, or zero if blank."""

    if not text(value):
        return ZERO
    try:
        return parse_money(value)
    except ValueError:
        raise ValueError(f"Invalid value {text(value)!r}") from None


def _is_date(value, date_format):
    """Check if a cell holds a date."""

    try:
        parse_date(value, date_format)
    except ValueError:
        return False
    return True


def _parse_total(value, line, warnings):
    """Parse the amount on a total row, or warn and return None."""

    try:
        return parse_money(value)
    except ValueError as e:
        warnings.append(f"gifts line {line}: Unreadable total, {e}")
        return None
