import csv

HEADER = [
    "Items",
    "Contact",
    "Email",
    "Mail",
    "Method",
    "Total",
    "Deductible",
    "Max",
    "Name",
]


def _row(statement):
    """Build report values for a statement."""

    return [
        statement.has_items,
        statement.has_contact,
        statement.has_email,
        statement.has_address,
        statement.method,
        statement.total,
        statement.deductible,
        statement.largest,
        statement.name,
    ]


def write_report(path, statements):
    """Write the donor report CSV."""

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(_row(statement) for statement in statements)


def format_report(statements):
    """Format the donor report as console lines."""

    labels = "Items Contact Email Mail  Method  Total         Deductible    Max"
    dashes = "----- ------- ----- ----- ------- ------------- ------------- -----"
    lines = [f"{labels}           Name", f"{dashes}-------- ----"]
    for row in map(_row, statements):
        items, contact, email, mail, method, total, deductible, largest, name = row
        lines.append(
            f"[{items:^3}] [{contact:^5}] [{email:^3}] [{mail:^3}] [{method:>5}] "
            f"[${total:>10,.2f}] [${deductible:>10,.2f}] [${largest:>10,.2f}] "
            f"{name}"
        )
    return lines
