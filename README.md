# donormail

Donation acknowledgement letters and emails for nonprofit organizations.

donormail reads donor contacts and gifts from CSV or Excel files, such as QuickBooks Online reports, and writes an acknowledgement for each donor: an email with a PDF letter attached, or a PDF to print and mail. You review everything before anything is sent.

- Year-end tax letters and event acknowledgements from the same data
- IRS-required wording for cash gifts, gifts with goods or services received, non-cash gifts, and gifts through donor-advised funds
- A `check` command that finds missing contacts, unreachable donors, and names to clean up
- Safe to rerun: emails already sent are not sent again
- Wording you can change without touching code
- Your data stays on your computer

> donormail helps prepare acknowledgements but is not tax or legal advice. Review the default wording with your accountant before relying on it.

## Install

donormail needs Python 3.11 or later.

```sh
pipx install git+https://github.com/cp-on-github/donormail
```

Or use `uv tool install` with the same address. See [Getting started](docs/getting-started.md) for more ways to install.

## Quick start

```sh
git clone https://github.com/cp-on-github/donormail
cp -r donormail/examples/basic my-acknowledgements
cd my-acknowledgements
donormail check config.toml   # find problems, writes nothing
donormail make config.toml    # write letters and emails to output/annual
```

## Documentation

- [Getting started](docs/getting-started.md)
- [How it works](docs/how-it-works.md)
- [Commands](docs/commands.md)
- [Configuration](docs/configuration.md)
- [QuickBooks Online](docs/quickbooks.md)
- [Templates](docs/templates.md)
- [Development](docs/development.md)

Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE.txt)
