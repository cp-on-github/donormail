from operator import attrgetter

from donormail.gifts import ZERO, own_contacts


class Statement:
    def __init__(self, name, gifts, contact):
        """Create a donor statement from gifts in the letter period."""

        self.name = name
        self.gifts = sorted(gifts, key=attrgetter("date"))
        self.contact = contact

    @property
    def salutation(self):
        """Greeting name, falling back to the donor name."""

        if self.contact and self.contact.salutation:
            return self.contact.salutation
        return self.name

    @property
    def has_items(self):
        """Donor has gifts in the letter period."""

        return bool(self.gifts)

    @property
    def gets_letter(self):
        """Donor has gifts and a way to reach them."""

        return self.has_items and self.method != "none"

    @property
    def has_receipt(self):
        """Donor has gifts acknowledged for tax purposes."""

        return any(gift.kind != "third-party" for gift in self.gifts)

    @property
    def has_contact(self):
        """Donor has a contact record."""

        return self.contact is not None

    @property
    def has_email(self):
        """Donor has an email address."""

        return self.contact is not None and self.contact.has_email

    @property
    def has_address(self):
        """Donor has a complete mailing address."""

        return self.contact is not None and self.contact.has_address

    @property
    def method(self):
        """How the letter is delivered: email, mail, or none."""

        if self.has_email:
            return "email"
        if self.has_address:
            return "mail"
        return "none"

    def _kind(self, kind):
        """Gifts of one kind."""

        return [gift for gift in self.gifts if gift.kind == kind]

    @property
    def cash(self):
        """Gifts with nothing received in return."""

        return self._kind("cash")

    @property
    def benefits(self):
        """Gifts with goods or services received in return."""

        return self._kind("benefit")

    @property
    def in_kind(self):
        """Non-cash gifts."""

        return self._kind("in-kind")

    @property
    def third_party(self):
        """Gifts made through third parties, not deductible by the donor."""

        return self._kind("third-party")

    @property
    def total(self):
        """Total amount of all gifts."""

        return _sum(gift.amount for gift in self.gifts)

    @property
    def cash_total(self):
        """Total amount of cash gifts."""

        return _sum(gift.amount for gift in self.cash)

    @property
    def benefit_total(self):
        """Total amount paid for gifts with goods or services received."""

        return _sum(gift.amount for gift in self.benefits)

    @property
    def third_party_total(self):
        """Total amount of gifts made through third parties."""

        return _sum(gift.amount for gift in self.third_party)

    @property
    def contributed(self):
        """Total paid in cash gifts and gifts with goods or services received."""

        return self.cash_total + self.benefit_total

    @property
    def nondeductible(self):
        """Part of the amount contributed that is not deductible."""

        return self.contributed - self.deductible

    @property
    def programs(self):
        """Programs supported by cash gifts and gifts with goods or services."""

        gifts = self.cash + self.benefits
        return sorted({gift.program for gift in gifts if gift.program})

    @property
    def funds(self):
        """Third parties that gifts were made through."""

        return sorted({gift.fund for gift in self.third_party})

    @property
    def value(self):
        """Total value of goods or services received."""

        return _sum(gift.value for gift in self.gifts)

    @property
    def deductible(self):
        """Total tax-deductible amount."""

        return _sum(gift.deductible for gift in self.gifts)

    @property
    def largest(self):
        """Largest single gift amount."""

        return max((gift.amount for gift in self.gifts), default=ZERO)

    @property
    def rows(self):
        """Cash gifts combined by date, with their programs."""

        # cash basis reports split one payment across the lines of the
        # pledge it paid, so combining by date shows the payment as made
        rows = {}
        for gift in self.cash:
            row = rows.setdefault(
                gift.date, {"date": gift.date, "programs": set(), "amount": ZERO}
            )
            if gift.program:
                row["programs"].add(gift.program)
            row["amount"] += gift.amount

        # sort program names for display
        for row in rows.values():
            row["programs"] = sorted(row["programs"])
        return list(rows.values())

    @property
    def third_party_rows(self):
        """Third-party gifts combined by date and fund."""

        rows = {}
        for gift in self.third_party:
            row = rows.setdefault(
                (gift.date, gift.fund),
                {"date": gift.date, "fund": gift.fund, "amount": ZERO},
            )
            row["amount"] += gift.amount
        return list(rows.values())


def _sum(amounts):
    """Sum amounts starting from zero cents."""

    return sum(amounts, ZERO)


def build_statements(letter, gifts, contacts):
    """Build a statement for every contact, then for donors only in gifts.

    Returns statements and warnings.
    """

    warnings = []

    # keep gifts in the letter period
    in_period = [gift for gift in gifts if letter.covers(gift.date)]
    skipped = len(gifts) - len(in_period)
    if skipped:
        warnings.append(
            f"gifts: {skipped} outside {letter.start} to {letter.end}, skipped"
        )

    # product filters are intentional, so they do not warn
    selected = [gift for gift in in_period if letter.selects(gift.product)]

    # group gifts by donor
    by_name = {}
    for gift in selected:
        by_name.setdefault(gift.name, []).append(gift)

    # third-party contacts only fill in for donors with gifts
    names = list(dict.fromkeys([*own_contacts(contacts), *by_name]))
    statements = [
        Statement(name, by_name.get(name, []), contacts.get(name)) for name in names
    ]
    return statements, warnings
