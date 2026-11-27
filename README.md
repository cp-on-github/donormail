# donormail

Donation acknowledgement letters and emails for nonprofits.

It reads contacts and gifts from CSV or Excel files, including QuickBooks Online reports. For each donor, it writes an email with a PDF letter, or a PDF to print and mail. Nothing is sent until you run `donormail send`.

- Year-end letters and event acknowledgements from the same data
- Wording for cash, goods received, non-cash, and third-party gifts
- `check` finds missing contacts, unreachable donors, and names to fix
- Emails already sent are not sent again
- Wording can be changed without touching code
- Runs on your computer, with no online account or service

> The default wording is written for 501(c)(3) organizations and is not tax or legal advice. Review it with your accountant before you use it.

## Install

Requires Python 3.11 or later.

```sh
uv tool install git+https://github.com/cp-on-github/donormail
```

[Getting started](docs/getting-started.md) has other ways to install.

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

Changes are in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE.txt)

QuickBooks is a trademark of Intuit Inc., and donormail is not affiliated with Intuit.
