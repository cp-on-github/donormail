# Commands

| Command | What it does |
|---|---|
| `donormail check CONFIG` | Lists problems to fix without writing anything |
| `donormail make CONFIG` | Writes emails, mail PDFs, and a report |
| `donormail send CONFIG` | Sends the emails and moves them to `sent/` |

Options:

- `--letter NAME` chooses the letter when the configuration has more than one.
- `make --force` also rewrites emails already sent, so `send` sends them again.
- `send --dry-run` lists the emails without sending.
- `send --limit N` sends at most N emails.

## What `check` lists

| Section | What it means |
|---|---|
| Warnings | Problems reading the files, such as rows that couldn't be read, gifts without a donor, or a total that doesn't match the file |
| Template problems | Mistakes in your templates, with the template and line |
| Donors without a contact | Donors with gifts but no contact, with a similar contact name when there is one |
| Acknowledgements required but undeliverable | Donors with no email or mailing address who made a single payment of $250 or more, or paid over $75 for goods or services |
| Names to clean up | Greetings in all capitals or all lowercase, or that include "anonymous" |
| Invalid email addresses | Contacts whose email doesn't look like an address |
| Rules matching no gifts | Rules that may have a misspelled product name |

## Output

Each letter has its own folder, named after the letter in the configuration, such as `annual`:

```
output/annual/
  email/          emails waiting to be sent
  sent/           emails already sent
  mail/           one PDF per donor to mail
  mail.pdf        all mail letters in one file for printing
  addresses.csv   names and addresses for envelopes or labels
  report.csv      every donor, how they are reached, and their totals
```

Each `make` clears `email/` and `mail/` first, so old files are never sent. Donors already in `sent/` are skipped.
