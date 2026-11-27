# Getting started

## Install

Requires Python 3.11 or later.

With [uv](https://docs.astral.sh/uv/):

```sh
uv tool install git+https://github.com/cp-on-github/donormail
```

Or with [pipx](https://pipx.pypa.io/):

```sh
pipx install git+https://github.com/cp-on-github/donormail
```

Or, in a virtual environment:

```sh
pip install git+https://github.com/cp-on-github/donormail
```

## Try an example

The examples are in the repository, not in the installed program. Download them with **Code > Download ZIP** on the [GitHub page](https://github.com/cp-on-github/donormail), or clone it:

```sh
git clone https://github.com/cp-on-github/donormail
```

Copy an example and run it:

```sh
cp -r donormail/examples/basic my-acknowledgements
cd my-acknowledgements
donormail check config.toml   # find problems, writes nothing
donormail make config.toml    # write letters and emails to output/annual
```

Review the files in `output/annual`. Emails are `.eml` files that most mail programs can open.

There are two examples:

- `examples/basic`: a plain contacts list and gifts list, with donations, an auction item, and a non-cash gift.
- `examples/quickbooks`: QuickBooks Online reports with product rules, third-party gifts, aliases, salutations, and an event letter.

## Set up your own

Keep your files outside the donormail folder you cloned, so donor information never ends up in a git commit.

1. Copy the example closest to your data, such as `examples/quickbooks`.
2. Replace its contacts and gifts files with your own. For QuickBooks, see [QuickBooks Online](quickbooks.md) for which reports to export.
3. Edit `config.toml`: your organization, the column names in your files, and the letter period. See [Configuration](configuration.md).
4. Run `donormail check config.toml` and fix what it lists.
5. Run `donormail make config.toml` and review the letters and emails.

## Send

Set up [`[email]` and `[smtp]`](configuration.md#email-and-smtp) for your mail server, then:

```sh
donormail send config.toml --dry-run   # list what would be sent
donormail send config.toml             # send, up to smtp.limit at a time
```

Print `mail.pdf` for donors without email. See [Commands](commands.md) for the output folder.

## Next steps

- [How it works](how-it-works.md): what donormail does with your files
- [Templates](templates.md): changing the wording
