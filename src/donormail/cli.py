import csv
from io import BytesIO

import click
from pypdf import PdfReader, PdfWriter

from donormail.checks import check_templates, run_checks
from donormail.config import Config, ConfigError
from donormail.gifts import load_contacts, load_gifts
from donormail.mailer import Mailer, MailError
from donormail.render import Renderer, RenderError
from donormail.report import format_report, write_report
from donormail.sources import SourceError
from donormail.statements import build_statements

ERRORS = (ConfigError, SourceError, RenderError, MailError)

config_argument = click.argument(
    "config_file", type=click.Path(exists=True, dir_okay=False)
)
letter_option = click.option(
    "--letter", "letter_name", help="Which letter, if there is more than one."
)


@click.group()
@click.version_option(package_name="donormail")
def donormail():
    """Write and send donor acknowledgements."""


@donormail.command()
@config_argument
@letter_option
def check(config_file, letter_name):
    """List problems to fix without writing anything."""

    try:
        config, letter, gifts, contacts, statements, warnings = _load(
            config_file, letter_name
        )
    except ERRORS as e:
        raise click.ClickException(str(e)) from e

    sections = run_checks(config, gifts, contacts, statements)
    problems = check_templates(Renderer(config, letter), statements)
    if problems:
        sections.insert(0, ("Template problems", problems))
    if warnings:
        sections.insert(0, ("Warnings", warnings))

    for title, items in sections:
        click.echo(f"\n{title} ({len(items)})")
        for item in items:
            click.echo(f"  {item}")

    letters = sum(1 for s in statements if s.gets_letter)
    click.echo(f"\n{letters} acknowledgements ready for letter {letter.name}.")
    if not sections:
        click.echo("No problems found.")


@donormail.command()
@config_argument
@letter_option
@click.option("--force", is_flag=True, help="Also rewrite emails already sent.")
def make(config_file, letter_name, force):
    """Write donor acknowledgements."""

    try:
        _make(config_file, letter_name, force)
    except ERRORS as e:
        raise click.ClickException(str(e)) from e


@donormail.command()
@config_argument
@letter_option
@click.option("--limit", type=click.IntRange(min=1), help="Most emails to send.")
@click.option("--dry-run", is_flag=True, help="List emails without sending.")
def send(config_file, letter_name, limit, dry_run):
    """Send donor acknowledgement emails."""

    try:
        config = Config(config_file)
        letter = config.letter(letter_name)
        mailer = Mailer(config, config.output / letter.name)

        if dry_run:
            batch = mailer.batch(limit)
            for path in batch:
                click.echo(f"Would send {path.name}")
            click.echo(f"Emails to send:    {len(batch)}")
            click.echo(f"Emails remaining:  {len(mailer.pending()) - len(batch)}")
            return

        sent = mailer.send(limit)
    except ERRORS as e:
        raise click.ClickException(str(e)) from e

    click.echo(f"Emails sent:       {sent}")
    click.echo(f"Emails remaining:  {len(mailer.pending())}")


def _load(config_file, letter_name):
    """Load the configuration and files, and build statements for a letter."""

    config = Config(config_file)
    letter = config.letter(letter_name)

    contacts, contact_warnings = load_contacts(config)
    gifts, gift_warnings = load_gifts(config)
    statements, statement_warnings = build_statements(letter, gifts, contacts)
    warnings = contact_warnings + gift_warnings + statement_warnings

    return config, letter, gifts, contacts, statements, warnings


def _make(config_file, letter_name, force):
    """Write acknowledgements for one letter."""

    config, letter, _, _, statements, warnings = _load(config_file, letter_name)

    folder = config.output / letter.name
    email_path = folder / "email"
    mail_path = folder / "mail"
    sent_path = folder / "sent"

    # render everything first, so a template error leaves earlier output alone
    renderer = Renderer(config, letter)
    stems = set()
    emails, mailed, already_sent = [], [], 0
    for statement in statements:
        if not statement.gets_letter:
            continue
        stem = _unique(renderer.filename(statement), stems)

        if statement.method == "email":
            if (sent_path / f"{stem}.eml").exists() and not force:
                already_sent += 1
                continue
            pdf = renderer.pdf(statement) if letter.attach else None
            emails.append((stem, renderer.email(statement, pdf).as_bytes()))
        else:
            mailed.append((stem, statement, renderer.pdf(statement)))

    # clear output from earlier runs, but leave sent emails alone
    for path in [*email_path.glob("*.eml"), *mail_path.glob("*.pdf")]:
        path.unlink()
    for path in (folder / "mail.pdf", folder / "addresses.csv"):
        path.unlink(missing_ok=True)
    email_path.mkdir(parents=True, exist_ok=True)
    mail_path.mkdir(parents=True, exist_ok=True)

    for stem, message in emails:
        (email_path / f"{stem}.eml").write_bytes(message)
    for stem, _, pdf in mailed:
        (mail_path / f"{stem}.pdf").write_bytes(pdf)
    if mailed:
        _write_print_files(folder, mailed)

    # report results
    write_report(folder / "report.csv", statements)
    for line in format_report(statements):
        click.echo(line)
    click.echo(f"\nEmails written:    {len(emails)}")
    click.echo(f"Letters to mail:   {len(mailed)}")
    if already_sent:
        click.echo(f"Already sent:      {already_sent}, use --force to rewrite")
    for warning in warnings:
        click.echo(f"Warning: {warning}", err=True)


def _write_print_files(folder, mailed):
    """Write one PDF of all mail letters and an address list for envelopes."""

    writer = PdfWriter()
    for _, _, pdf in mailed:
        writer.append(PdfReader(BytesIO(pdf)))
    with (folder / "mail.pdf").open("wb") as f:
        writer.write(f)

    with (folder / "addresses.csv").open("w", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        out.writerow(["Name", "Street", "City", "State", "Zip"])
        for _, statement, _ in mailed:
            contact = statement.contact
            out.writerow(
                [
                    statement.name,
                    contact.street,
                    contact.city,
                    contact.state,
                    contact.zip,
                ]
            )


def _unique(stem, stems):
    """Make a file name stem unique by adding a number."""

    candidate, number = stem, 1
    while candidate in stems:
        number += 1
        candidate = f"{stem}_{number}"
    stems.add(candidate)
    return candidate
