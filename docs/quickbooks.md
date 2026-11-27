# QuickBooks Online

How to record gifts in QuickBooks Online so donormail can acknowledge them, and which reports to export. The [`examples/quickbooks`](https://github.com/cp-on-github/donormail/tree/main/examples/quickbooks) folder has a matching configuration and sample reports.

QuickBooks for nonprofits renames some things: customers are donors, invoices are pledges, and sales receipts are donations. This page uses the nonprofit names.

QuickBooks is a trademark of Intuit Inc., and donormail is not affiliated with Intuit.

## How donormail reads QuickBooks

There are two reports to export:

- a **gifts report**, with one row per line of each paid pledge or receipt
- a **contacts report**, with each donor's email and mailing address

QuickBooks writes nested names with a colon: a sub-donor is `Parent:Child`, a product in a category is `Category:Item`, and a sub-class is `Parent:Class`. These names are used to:

- find third-party gifts by the parent donor name
- show the last part of class and product names on letters
- match rules to the full product name

## Donors

- **Name donors as they should appear on letters.** Fix capitalization in QuickBooks, or add a salutation column to the contacts report for the greeting.
- **Keep one donor per person or household.** Gifts are grouped by exact name. `donormail check` lists donors with gifts but no contact, with a similar contact name when it finds one. Use `[aliases]` in the configuration for names you can't fix in QuickBooks.

## Classes are programs

Letters show the program each gift supported, taken from the class. Nested classes show only the last part, so `PROGRAMS:Education` shows as "Education". Name classes the way donors should see them, or rename them in the configuration by their full name:

```toml
[programs]
"PROGRAMS:EDU" = "Education"
```

## Products

- **Use categories.** Name products `Category:Item`, such as `Donations:General` or `Gala:Dinner Ticket`. Letters show only the item.
- **Give anything with a value received its own product.** A donor who buys a dinner ticket or a T-shirt can deduct only what they paid above its value. A rule tells donormail the product's value:

  ```toml
  [[rules]]
  product = "Gala:Dinner Ticket"   # full product name, * and ? are wildcards
  value = 45                       # value per unit

  [[rules]]
  product = "Gala:Raffle*"
  value = "amount"                 # the whole payment is value received
  ```

  Units are the amount paid divided by the sales price. Three $60 tickets paid in full are 3 units. Half of one ticket paid toward a pledge is half a unit.
- **Record extra donations on their own line.** If a donor pays $100 for a $60 ticket, put the ticket on one line and the extra $40 on a second line with a donation product. One line can't show which part was the ticket.
- **Every other product is a cash gift.** Nothing has a value received unless a rule says so.
- **Deleting products after an event is fine.** QuickBooks adds ` (deleted)` to deleted names, and donormail removes it. Reports show a product's current name, so if you rename a product, update its rule.

## Pledges and receipts

Both pledges (invoices) and receipts (sales receipts) work.

- **Run the report on a cash basis.** A gift counts when it is paid, not when it is pledged. An unpaid pledge doesn't appear, and a paid pledge appears on the date of each payment.
- **Partial payments are split across pledge lines.** QuickBooks divides a partial payment among the pledge's lines, which can give amounts like 107.74 and 107.75. Letters combine a donor's cash gifts by date, so they show the payment as made.

## Third-party gifts

Gifts through a donor-advised fund, workplace giving platform, or bank are receipted by the third party, not by you. The letter thanks the donor for them on a separate page headed "Gifts through third parties (not a tax receipt)".

Create a parent donor for each third party and add the donor under it, such as `NO RECEIPT Workplace Giving:Jane Doe`. Then tell donormail how to recognize the parents, using any marker text you like:

```toml
[third_party]
markers = ["NO RECEIPT"]         # parent names starting with a marker
funds = ["Family Donor Fund"]    # or parent names that are the fund itself
```

Name the sub-donor exactly like the donor's own record, so their gifts end up in one letter.

Gifts recorded under the parent alone can't be acknowledged. `donormail check` lists them as warnings.

## Non-cash gifts

A non-cash (in-kind) gift is described on the letter without a value. Either:

- **Record it in QuickBooks** with a product such as `In-Kind:Goods`, describe the item in the description, and add a rule:

  ```toml
  [[rules]]
  product = "In-Kind:*"
  kind = "in-kind"
  ```

- **List it in a spreadsheet** with a product column, such as `In-Kind`, and a rule with `product = "In-Kind"`. Enter 0 as each gift's amount, since a blank amount is skipped. Use the spreadsheet as the gifts file for a separate letter. [`examples/basic`](https://github.com/cp-on-github/donormail/tree/main/examples/basic) shows the columns and rule, with a non-cash gift in the same file as cash gifts.

## Exporting the gifts report

Use **Sales by Donor Detail** (Sales by Customer Detail outside the nonprofit edition), in classic or modern view:

1. Set the dates to the letter period and the accounting method to **Cash**.
2. In modern view, turn off grouping so every row has the donor's name.
3. Include the columns below, and export to Excel or CSV.

Title rows, footer rows, and extra columns are fine. The `TOTAL` row is checked against the gifts donormail read.

| Field | Classic view | Modern view | Needed |
|---|---|---|---|
| `date` | Date | Transaction date | Required |
| `name` | Donor | **Donor full name** | Required |
| `amount` | Amount | Amount | Required |
| `program` | Class | **Class full name** | Recommended, shown on letters |
| `product` | Product/Service | **Product/Service full name** | Recommended, used by rules |
| `price` | Sales Price | Sales price | Required for rules with a value per unit |
| `description` | Memo/Description | Description | For non-cash gifts, or items without a product |

In modern view, use the **full name** columns. The Donor, Product/Service, and Item class columns have only the last part of nested names, so third-party gifts and rules wouldn't be recognized. Modern view's Memo column is the transaction memo, not the line description.

Map the columns in the configuration. For modern view:

```toml
[gifts]
file = "gifts.xlsx"

[gifts.columns]
date = "Transaction date"
name = "Donor full name"
amount = "Amount"
program = "Class full name"
product = "Product/Service full name"
price = "Sales price"
description = "Description"
```

Leave out `description` if your descriptions are bookkeeping notes rather than what was given or bought.

## Exporting the contacts report

Use the **Donor Contact List** (Customer Contact List) with the donor name, email, and billing street, city, state, and zip, and export it to Excel or CSV.

```toml
[contacts]
file = "contacts.csv"

[contacts.columns]
name = "Donor full name"
email = "Email"
street = "Bill street"
city = "Bill city"
state = "Bill state"
zip = "Bill zip"
```

## Before you send

Run `donormail check config.toml` after each export. See [what `check` lists](commands.md#what-check-lists).
