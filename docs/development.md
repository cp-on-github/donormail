# Development

Development uses [uv](https://docs.astral.sh/uv/). `uv sync` creates `.venv` with donormail and the pinned versions of pytest, ruff, and pyright that CI uses.

```sh
git clone https://github.com/cp-on-github/donormail
cd donormail
uv sync
uv run pytest
uv run ruff format --check src tests
uv run ruff check src tests
uv run pyright src tests
```

The code uses simple docstrings, short comments above blocks, and no type hints.

For each change users would notice, add a one-line entry under Unreleased in [CHANGELOG.md](https://github.com/cp-on-github/donormail/blob/main/CHANGELOG.md).

## Code map

The code is in `src/donormail`, one file per step:

| File | What it does |
|---|---|
| `cli.py` | Runs the `check`, `make`, and `send` commands |
| `config.py` | Reads the configuration file and reports mistakes in it |
| `sources.py` | Reads rows from CSV and Excel files |
| `gifts.py` | Turns rows into donors' contacts and gifts |
| `statements.py` | Collects each donor's gifts and adds up the totals |
| `checks.py` | Finds the problems `check` lists |
| `render.py` | Writes the emails and PDF letters |
| `mailer.py` | Sends the emails |
| `report.py` | Writes the report of every donor |
| `templates/` | The wording of the default letters and emails |

Where each rule is decided:

| Rule | File | Function |
|---|---|---|
| Whether a gift is cash, benefit, in-kind, or third-party | `gifts.py` | `_classify` |
| How much of a gift is deductible | `gifts.py` | `Gift.deductible` |
| Who the donor is for a gift through a fund | `gifts.py` | `split_third_party` |
| How many units were bought, from the sales price | `gifts.py` | `_parse_units` |
| Which rows are one payment on the letter | `statements.py` | `Statement.rows` |
| Which donors must get a letter but can't be reached | `checks.py` | `_undeliverable` |

The tests in `tests/` show each rule with small examples.
