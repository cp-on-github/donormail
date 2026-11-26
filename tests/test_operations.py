import csv
from io import BytesIO

from click.testing import CliRunner
from pypdf import PdfReader

from donormail.cli import donormail


def run(*args):
    """Run a command with the QuickBooks example configuration."""

    return CliRunner().invoke(donormail, [args[0], "quickbooks/config.toml", *args[1:]])


def test_check(workdir):
    """Check lists problems by section without writing output."""

    with (workdir / "quickbooks/gifts.csv").open("a") as f:
        f.write(
            ",03/01/2025,Jane Do,EDUCATION,20.00,Donations:General,1,,SR-9,Receipt\n"
        )
        f.write(
            ",03/02/2025,Lee Park,EDUCATION,300.00,Donations:General,1,,SR-10,Receipt\n"
        )
    with (workdir / "quickbooks/contacts.csv").open("a") as f:
        f.write("Lee Park,,lee-at-example.com,,,,,\n")
        f.write("ROSE GRAY,,rose@example.com,,,,,\n")
    with (workdir / "quickbooks/gifts.csv").open("a") as f:
        f.write(
            ",03/03/2025,ROSE GRAY,EDUCATION,5.00,Donations:General,1,,SR-11,Receipt\n"
        )
        f.write(",02/15/2025,Sam Lane,EVENTS,80.00,Events:Raffle,1,,SR-12,Receipt\n")
        f.write(",02/15/2025,Kim Ray,EVENTS,75.00,Events:Raffle,1,,SR-13,Receipt\n")
        f.write(",02/15/2025,Ann Bell,EVENTS,50.00,Events:Raffle,1,,SR-14,Receipt\n")
        f.write(",02/15/2025,Ann Bell,EVENTS,50.00,Events:Raffle,1,,SR-14,Receipt\n")
        f.write(",04/01/2025,Max Roe,EDUCATION,150.00,Donations:General,,,P-1,Pledge\n")
        f.write(",04/01/2025,Max Roe,HOUSING,150.00,Donations:General,,,P-1,Pledge\n")
    config = workdir / "quickbooks/config.toml"
    config.write_text(
        config.read_text().replace(
            "[letters.annual]",
            '[[rules]]\nproduct = "Gala:*"\nvalue = 1\n\n[letters.annual]',
        )
    )

    result = run("check", "--letter", "annual")
    assert result.exit_code == 0, result.output
    out = result.output
    assert "Warnings (3)" in out
    assert "Donors without a contact (5)\n  Jane Do (similar contact: Jane Doe)" in out
    assert "Lee Park: single payment of 300.00" in out
    assert "Max Roe: single payment of 300.00" in out
    assert "Ann Bell: payment of 100.00 with goods or services received" in out
    assert "Sam Lane: payment of 80.00 with goods or services received" in out
    assert "Kim Ray: payment" not in out
    assert "ROSE GRAY: not in mixed case" in out
    assert "ANONYMOUS" not in out
    assert "Lee Park: lee-at-example.com" in out
    assert "rules[4] Gala:*" in out
    assert "acknowledgements ready for letter annual" in out
    assert not (workdir / "quickbooks/output").exists()


def test_make_skips_sent_and_clears_stale(workdir):
    """Make skips emails already sent and removes files from earlier runs."""

    assert run("make", "--letter", "annual").exit_code == 0
    folder = workdir / "quickbooks/output/annual"
    sent = folder / "sent"
    sent.mkdir()
    (folder / "email/2025_Anytown_Charity_Jane_Doe.eml").rename(
        sent / "2025_Anytown_Charity_Jane_Doe.eml"
    )
    (folder / "email/stale.eml").write_text("old")

    result = run("make", "--letter", "annual")
    assert result.exit_code == 0, result.output
    emails = sorted(p.name for p in (folder / "email").iterdir())
    assert "stale.eml" not in emails
    assert "2025_Anytown_Charity_Jane_Doe.eml" not in emails
    assert "Already sent:      1, use --force to rewrite" in result.output

    result = run("make", "--letter", "annual", "--force")
    assert (folder / "email/2025_Anytown_Charity_Jane_Doe.eml").exists()
    assert (sent / "2025_Anytown_Charity_Jane_Doe.eml").exists()


def test_print_files(workdir):
    """Mail letters are combined into one PDF with an address list."""

    result = run("make", "--letter", "annual")
    assert "Letters to mail:   1" in result.output
    folder = workdir / "quickbooks/output/annual"

    pages = PdfReader(BytesIO((folder / "mail.pdf").read_bytes())).pages
    assert len(pages) == 2
    assert "Two laptops" in pages[1].extract_text()

    with (folder / "addresses.csv").open() as f:
        assert list(csv.reader(f)) == [
            ["Name", "Street", "City", "State", "Zip"],
            ["Acme Corp", "1 Main St", "Town", "TX", "75001"],
        ]


def test_send_dry_run(workdir):
    """Dry run lists emails up to the limit without connecting."""

    run("make", "--letter", "annual")
    result = run("send", "--letter", "annual", "--dry-run", "--limit", "2")
    assert result.exit_code == 0, result.output
    assert result.output.count("Would send") == 2
    assert "Emails to send:    2" in result.output
    assert "Emails remaining:  1" in result.output
    assert len(list((workdir / "quickbooks/output/annual/email").iterdir())) == 3


def test_send_connection_error(workdir):
    """Connection failures report the host without a traceback."""

    run("make", "--letter", "annual")
    config = workdir / "quickbooks/config.toml"
    config.write_text(config.read_text().replace("port = 8025", "port = 1"))

    result = run("send", "--letter", "annual")
    assert result.exit_code == 1
    assert "Error: Unable to connect to localhost" in result.output


def break_template(workdir):
    """Override the email text template with a misspelled value."""

    templates = workdir / "basic/templates"
    templates.mkdir()
    (templates / "email.txt").write_text("Dear {{ statement.name }},\n{{ org.nmae }}\n")
    config = workdir / "basic/config.toml"
    config.write_text('templates = "templates"\n' + config.read_text())


def test_template_error_keeps_output(workdir):
    """A template error is explained and earlier output is left alone."""

    make = ["make", "basic/config.toml"]
    assert CliRunner().invoke(donormail, make).exit_code == 0
    emails = sorted((workdir / "basic/output/annual/email").iterdir())

    break_template(workdir)
    result = CliRunner().invoke(donormail, make)
    assert result.exit_code == 1
    assert "Error: Template email.txt line 2:" in result.output
    assert "has no attribute 'nmae', for John Appleseed" in result.output
    assert sorted((workdir / "basic/output/annual/email").iterdir()) == emails


def test_check_templates(workdir):
    """Check lists each template problem once."""

    break_template(workdir)
    result = CliRunner().invoke(donormail, ["check", "basic/config.toml"])
    assert result.exit_code == 0, result.output
    assert "Template problems (1)\n  Template email.txt line 2:" in result.output
    assert "(for John Appleseed and 1 more)" in result.output


def use_templates(workdir, files):
    """Add template overrides to the basic example."""

    templates = workdir / "basic/templates"
    templates.mkdir()
    for name, content in files.items():
        data = content if isinstance(content, bytes) else content.encode()
        (templates / name).write_bytes(data)
    config = workdir / "basic/config.toml"
    config.write_text('templates = "templates"\n' + config.read_text())


def check_output(workdir):
    """Run check on the basic example."""

    result = CliRunner().invoke(donormail, ["check", "basic/config.toml"])
    assert result.exit_code == 0, result.output
    return result.output


def test_check_filter_error(workdir):
    """A filter given the wrong kind of value is a template problem."""

    use_templates(
        workdir,
        {"email.txt": "Dear {{ statement.name }},\n{{ statement.name | money }}\n"},
    )
    assert "Template email.txt line 2: Unknown format code" in check_output(workdir)


def test_check_imported_template_error(workdir):
    """Errors in an imported template name that template."""

    use_templates(
        workdir,
        {
            "email.txt": '{% import "parts.txt" as parts %}\n{{ parts.hello() }}\n',
            "parts.txt": "{% macro hello() %}\n\nHi {{ nobody.name }}\n{% endmacro %}\n",
        },
    )
    assert "Template parts.txt line 3: 'nobody' is undefined" in check_output(workdir)


def test_check_template_encoding(workdir):
    """A template that is not UTF-8 is a template problem."""

    use_templates(workdir, {"email.txt": b"Caf\xe9 {{ statement.name }}\n"})
    assert "Template email.txt: 'utf-8' codec can't decode" in check_output(workdir)
