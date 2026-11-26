# Templates

The built-in templates are in [`src/donormail/templates`](https://github.com/cp-on-github/donormail/tree/main/src/donormail/templates):

| Template | Used for |
|---|---|
| `letter.html` | PDF letter: summary page, details page, and third-party page |
| `email.html`, `email.txt` | Email sent with the PDF attached |
| `event.html`, `event.txt` | Event email listing each item paid for, its value, and the deductible amount |

To change the wording:

1. Add `templates = "templates"` to your configuration and create that folder next to it.
2. Copy a template into the folder and edit it. Your copy is used instead of the built-in one.

Templates use [Jinja2](https://jinja.palletsprojects.com/templating/).

To show the logo in an HTML email, use `<img src="cid:logo">`. donormail puts the `[org]` logo file inside the email, so it shows even when the mail app blocks remote images.

`check` tries every template for every donor. A misspelled value is an error that names the template and line, and `make` writes nothing until it is fixed.

## Values

| Value | Contains |
|---|---|
| `org` | The `[org]` settings. In PDF letters, `org.logo` is the image itself as a `data:` address, for `<img src="{{ org.logo }}">` |
| `letter` | `name`, `label`, `start`, `end`, `year` |
| `today` | The date the letter is made |
| `statement` | One donor, below |

`statement` has:

| Value | Contains |
|---|---|
| `name`, `salutation` | The donor's name and greeting |
| `contact` | `street`, `city`, `state`, `zip`, `email` |
| `gifts` | All gifts in the period |
| `cash`, `benefits`, `in_kind`, `third_party` | Gifts of each kind |
| `rows` | Cash gifts combined by date, each with `date`, `programs`, `amount` |
| `third_party_rows` | Third-party gifts combined by date and fund, each with `date`, `fund`, `amount` |
| `total` | Total of all gifts |
| `cash_total`, `benefit_total`, `third_party_total` | Total of each kind |
| `contributed` | Cash gifts and payments for goods or services |
| `value` | Value of goods or services received |
| `nondeductible` | The part of `contributed` that is not deductible |
| `deductible` | The tax-deductible amount |
| `largest` | The largest single gift |
| `programs`, `funds` | Programs supported and third parties given through |
| `method` | `email`, `mail`, or `none` |
| `has_items` | Has gifts in the period |
| `has_receipt` | Has gifts other than third-party gifts |
| `has_contact`, `has_email`, `has_address` | Has a contact, an email address, or a full mailing address |

Each gift has:

| Value | Contains |
|---|---|
| `date`, `amount` | When and how much was paid |
| `value`, `deductible` | Value received and the deductible part |
| `program` | Program name as shown on letters |
| `item` | What was given or bought, as shown on letters |
| `product`, `description` | The full product name and description from the gifts file |
| `units` | Units bought |
| `kind` | `cash`, `benefit`, `in-kind`, or `third-party` |
| `fund` | The third party, for third-party gifts |

## Filters

| Filter | Example |
|---|---|
| `money` | 1,234.50 |
| `longdate` | January 5, 2025 |
| `shortdate` | 1/5/2025 |
| `series` | A, B, and C |
