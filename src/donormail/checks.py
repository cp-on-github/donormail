from decimal import Decimal
from difflib import get_close_matches

from donormail.gifts import own_contacts
from donormail.render import RenderError

# gifts of this amount or more require a written acknowledgement
ACKNOWLEDGEMENT_THRESHOLD = Decimal(250)

# payments over this amount with goods or services received need a disclosure
DISCLOSURE_THRESHOLD = Decimal(75)


def run_checks(config, gifts, contacts, statements):
    """Find problems worth fixing before sending.

    Returns a list of (title, items) sections, skipping empty ones.
    """

    names = own_contacts(contacts)
    letters = [s for s in statements if s.gets_letter]

    sections = [
        ("Donors without a contact", _missing_contacts(statements, names)),
        ("Acknowledgements required but undeliverable", _undeliverable(statements)),
        ("Names to clean up", _odd_names(letters)),
        ("Invalid email addresses", _invalid_emails(contacts)),
        ("Rules matching no gifts", _unused_rules(config.rules, gifts)),
    ]
    return [(title, items) for title, items in sections if items]


def _missing_contacts(statements, names):
    """Donors with gifts but no contact, with close name suggestions."""

    items = []
    for statement in statements:
        if not statement.has_items or statement.has_contact:
            continue
        match = get_close_matches(statement.name, names, n=1, cutoff=0.8)
        hint = f" (similar contact: {match[0]})" if match else ""
        items.append(f"{statement.name}{hint}")
    return items


def _undeliverable(statements):
    """Donors who need a written acknowledgement or disclosure but can't be reached.

    A single payment of $250 or more needs a written acknowledgement, and a
    payment over $75 with goods or services received needs a disclosure.
    Lines on the same date are one payment, since reports split payments
    across the lines they paid.
    """

    items = []
    for statement in statements:
        if statement.method != "none":
            continue
        receipted = [g for g in statement.gifts if g.kind != "third-party"]
        largest = max(_payments(receipted), default=Decimal(0))
        disclosed = [
            amount
            for amount in _payments(g for g in statement.benefits if g.value > 0)
            if amount > DISCLOSURE_THRESHOLD
        ]
        if largest >= ACKNOWLEDGEMENT_THRESHOLD:
            items.append(f"{statement.name}: single payment of {largest:,.2f}")
        elif disclosed:
            items.append(
                f"{statement.name}: payment of {max(disclosed):,.2f} "
                "with goods or services received"
            )
    return items


def _payments(gifts):
    """Add up gifts by date, giving one total per payment."""

    totals = {}
    for gift in gifts:
        totals[gift.date] = totals.get(gift.date, Decimal(0)) + gift.amount
    return list(totals.values())


def _odd_names(statements):
    """Greetings in all capitals or all lowercase, or that include "anonymous"."""

    items = []
    for statement in statements:
        greeting = statement.salutation
        if greeting.isupper() or greeting.islower():
            items.append(f"{greeting}: not in mixed case")
        elif "anonymous" in greeting.lower():
            items.append(f"{greeting}: greeting includes 'anonymous'")
    return items


def _invalid_emails(contacts):
    """Contacts with an email that does not look like an address."""

    return [
        f"{contact.name}: {contact.email}"
        for contact in contacts.values()
        if contact.email and not contact.has_email
    ]


def _unused_rules(rules, gifts):
    """Rules whose product pattern matches no gift."""

    products = {gift.product for gift in gifts}
    return [
        f"rules[{index}] {rule.product}"
        for index, rule in enumerate(rules, start=1)
        if not any(rule.matches(product) for product in products)
    ]


def check_templates(renderer, statements):
    """Try the templates for every letter, listing each problem once."""

    problems = {}
    for statement in statements:
        if not statement.gets_letter:
            continue
        try:
            renderer.verify(statement)
        except RenderError as e:
            problems.setdefault(e.problem, []).append(statement.name)

    items = []
    for problem, donors in problems.items():
        more = f" and {len(donors) - 1} more" if len(donors) > 1 else ""
        items.append(f"{problem} (for {donors[0]}{more})")
    return items
