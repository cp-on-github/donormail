# How it works

1. **Read** the contacts and gifts files. Title rows above the column headers are ignored. A row that can't be read is skipped with a warning.
2. **Classify** each gift as one of the kinds below.
3. **Collect** each donor's gifts in the letter period (a year, or start and end dates) set in the [configuration](configuration.md#lettersname).
4. **Write** an email for donors with an email address, or a PDF to mail for donors with a full mailing address. Donors with neither are listed in the report.
5. **Send** the emails after you review them.

| Kind | Example | Deductible | Shown as |
|---|---|---|---|
| Cash | A donation | The full amount | Contributions |
| Benefit | A $75 dinner ticket worth $45 | Amount paid less value received | Contributions with goods or services received |
| In-kind | Donated laptops | Not stated | Non-cash contributions, described without a value |
| Third-party | A donor-advised fund grant | None for the donor | A separate page that says it is not a tax receipt |
