# Configuration

Settings are in a TOML file. Paths are relative to that file. Misspelled or unknown settings are errors.

```toml
output = "output"          # output folder, default "output"
templates = "templates"    # optional folder of your own templates
```

## `[org]`

```toml
[org]
name = "Anytown Charity"                    # required
ein = "XX-XXXXXXX"
address = "PO Box 123456, Anytown, TX 12345"
email = "info@example.org"
website = "www.example.org"
logo = "logo.png"                           # shown on PDF letters and inside HTML emails
signer = { name = "I. M. Treasurer", title = "Treasurer" }
```

## `[contacts]` and `[gifts]`

Each names a CSV or Excel file and maps fields to its column headers. Other columns are ignored.

```toml
[contacts]
file = "contacts.csv"

[contacts.columns]
name = "Donor"            # required
salutation = "Greeting"   # used after "Dear", or the name if blank
email = "Email"
street = "Street"
city = "City"
state = "State"
zip = "Zip"

[gifts]
file = "gifts.xlsx"
date_format = "%m/%d/%Y"  # for dates stored as text, default shown

[gifts.columns]
date = "Date"             # required
name = "Donor"            # required
amount = "Amount"         # required
program = "Class"
product = "Product/Service"
price = "Sales Price"     # units bought are amount ÷ price
description = "Memo/Description"
value = "Value"           # value received, for spreadsheets that track it
```

- Amounts like `1,234.50`, `$ 25.00`, and `(25.00)` are understood.
- A row with an amount but no donor or real date, such as a QuickBooks `TOTAL` row, is treated as the file total and checked against the sum of the gifts. A row like that without an amount, such as a report footer, is ignored.
- Letters show the last part of nested names, so class `PROGRAMS:Education` shows as "Education".
- ` (deleted)`, which QuickBooks adds to deleted names, is removed.
- Letters name each gift by its product, or by its description when there is no product. Non-cash gifts use the description first, since it says what was given.

## `[programs]` and `[aliases]`

```toml
[programs]                # rename programs by their full name
"PROGRAMS:SUMMER" = "Summer Camp"

[aliases]                 # merge or correct donor names in both files
"Jon Smith" = "John Smith"
```

## `[third_party]`

Gifts through a donor-advised fund, workplace giving platform, or bank are thanked but not receipted. They are recognized by name, using the `Parent:Child` form of QuickBooks sub-donors. The donor is the last part of the name.

```toml
[third_party]
markers = ["NO RECEIPT"]         # parent names starting with a marker
funds = ["Family Donor Fund"]    # parent names that are the fund itself
separator = ":"                  # default shown, also used for program and product names
```

| Name | Fund | Donor |
|---|---|---|
| `NO RECEIPT Workplace Giving:Jane Doe` | Workplace Giving | Jane Doe |
| `NO RECEIPT:Workplace Giving:Jane Doe` | Workplace Giving | Jane Doe |
| `Family Donor Fund:Jane Doe` | Family Donor Fund | Jane Doe |
| `NO RECEIPT Workplace Giving` | Workplace Giving | none, skipped with a warning |

Third-party gifts are listed on their own page after the tax receipt. Donors with only third-party gifts get a one-page thank you.

A third-party donor with the same name as a regular donor is treated as the same person and gets one letter, with their own gifts in the tax summary and their third-party gifts on the last page. Names must match exactly, so use `[aliases]` when they don't. The letter goes to the donor's own contact. A donor without one uses the first contact under a third-party name, such as `NO RECEIPT Workplace Giving:Jane Doe`.

## `[[rules]]`

Rules classify gifts by product. The first matching rule applies. Rules match the full product name, such as `Fundraisers:Gala:Dinner Ticket`, and `*` and `?` are wildcards.

```toml
# value received per unit
[[rules]]
product = "Events:Dinner Ticket"
value = 45

# the whole payment is value received, e.g. raffle tickets
[[rules]]
product = "Events:Raffle*"
value = "amount"

# non-cash gifts, described by the description column
[[rules]]
product = "In-Kind:*"
kind = "in-kind"
```

- A value per unit needs the `price` column to count the units bought. A row with no price counts as one unit.
- A value in the `value` column overrides rules. Non-cash gifts ignore it, since they are described without a value.
- A gift with no value received is a cash gift.

## `[letters.NAME]`

Each letter has a period and optional settings. The name is used for the output folder and the `--letter` option.

```toml
[letters.annual]
year = 2025

[letters.gala]
start = 2025-10-18
end = 2025-10-18
label = "2025 Gala"                  # used in file names and subjects
subject = "Thank you for attending the {{ letter.label }}"
products = ["Events:*"]              # only these products
exclude_products = []                # never these products
template = "letter.html"             # PDF letter
email_html = "event.html"            # email body
email_text = "event.txt"
attach = false                       # attach the PDF to emails
```

| Setting | Default |
|---|---|
| `label` | The year, or `2025-10-18 to 2025-10-18` for start and end dates |
| `subject` | `"{{ letter.label }} {{ org.name }} Contributions"` |
| `template`, `email_html`, `email_text` | `letter.html`, `email.html`, `email.txt` |
| `attach` | `true` |

`attach` only affects emails. Donors without email always get a PDF in `mail/`.

## `[email]` and `[smtp]`

```toml
[email]
name = "I. M. Treasurer"
address = "treasurer@example.org"          # required
reply_to = ""
bcc = ""                                   # e.g. an archive address

[smtp]
host = "smtp.example.org"
port = 465                                 # default 465 for ssl, otherwise 25 (starttls usually uses 587)
security = "ssl"                           # ssl, starttls, or none
user = "treasurer@example.org"             # log in when set
limit = 50                                 # most emails sent per run
```

The password is read from the `DONORMAIL_SMTP_PASSWORD` environment variable, or asked for when sending.
