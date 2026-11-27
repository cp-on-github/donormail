import csv
from email import message_from_bytes, policy

import pytest
from click.testing import CliRunner

from donormail import mailer
from donormail.cli import donormail


def make(*args):
    """Run make with the example configuration."""

    result = CliRunner().invoke(donormail, ["make", "basic/config.toml", *args])
    assert result.exit_code == 0, result.output
    return result


def read_email(path):
    """Parse an email file."""

    return message_from_bytes(path.read_bytes(), policy=policy.default)


def test_make_writes_acknowledgements(workdir):
    """Make writes emails, mail PDFs, and a report."""

    result = make()
    folder = workdir / "basic/output/annual"

    # donors with email get an email, with address only get a mail PDF
    emails = sorted(p.name for p in (folder / "email").iterdir())
    mail = sorted(p.name for p in (folder / "mail").iterdir())
    assert emails == [
        "2025_Anytown_Charity_John_Appleseed.eml",
        "2025_Anytown_Charity_John_Smith.eml",
    ]
    assert mail == [
        "2025_Anytown_Charity_John_Doe.pdf",
        "2025_Anytown_Charity_Main_Street_Grocery.pdf",
    ]
    assert (folder / "mail" / mail[0]).read_bytes().startswith(b"%PDF")

    # report includes every donor from contacts and gifts
    with (folder / "report.csv").open() as f:
        rows = {row["Name"]: row for row in csv.DictReader(f)}
    assert list(rows) == [
        "John Appleseed",
        "John Doe",
        "John Smith",
        "Jane Smith",
        "Main Street Grocery",
        "Mary Major",
    ]
    assert rows["John Appleseed"]["Total"] == "150.00"
    assert rows["John Appleseed"]["Max"] == "50.00"

    # unreachable donors are reported without a letter
    assert rows["Jane Smith"]["Contact"] == "True"
    assert rows["Jane Smith"]["Method"] == "none"
    assert rows["Mary Major"]["Contact"] == "False"
    assert rows["Mary Major"]["Method"] == "none"

    assert "[$    150.00] [$     50.00] John Appleseed" in result.output


def test_email_content(workdir):
    """Emails have headers, text and html parts, and the PDF attached."""

    make()
    path = workdir / "basic/output/annual/email/2025_Anytown_Charity_John_Appleseed.eml"
    message = read_email(path)

    assert message["From"] == '"I. M. Treasurer" <treasurer@example.org>'
    assert message["To"] == "John Appleseed <john.appleseed@example.com>"
    assert message["Subject"] == "2025 Anytown Charity Contributions"
    assert message["Date"]
    assert message["Message-ID"].endswith("@example.org>")

    text = message.get_body(preferencelist=("plain",))
    html = message.get_body(preferencelist=("html",))
    assert text is not None
    assert html is not None
    assert "Dear John Appleseed," in text.get_content()
    assert "<p>Dear John Appleseed,</p>" in html.get_content()

    attachments = list(message.iter_attachments())
    assert [a.get_filename() for a in attachments] == [
        "2025_Anytown_Charity_John_Appleseed.pdf"
    ]

    # the logo is inside the email, not attached
    logo = next(p for p in message.walk() if p["Content-ID"] == "<logo>")
    assert logo.get_content_type() == "image/png"
    assert logo.get_content() == (workdir / "basic/logo.png").read_bytes()
    assert 'src="cid:logo"' in html.get_content()


def test_names_are_escaped(workdir):
    """Names with html characters are escaped in html but not in text."""

    with (workdir / "basic/contacts.csv").open("a") as f:
        f.write("Smith & <Sons>,sons@example.com,,,,,\n")
    with (workdir / "basic/gifts.csv").open("a") as f:
        f.write("6/1/2025,40,Smith & <Sons>,Check,10,Food\n")

    make()
    path = workdir / "basic/output/annual/email/2025_Anytown_Charity_Smith_Sons.eml"
    message = read_email(path)
    html = message.get_body(preferencelist=("html",))
    text = message.get_body(preferencelist=("plain",))
    assert html is not None
    assert text is not None
    assert "Dear Smith &amp; &lt;Sons&gt;," in html.get_content()
    assert "Dear Smith & <Sons>," in text.get_content()


def test_template_override(workdir):
    """Templates in the configured folder replace package templates."""

    templates = workdir / "basic/templates"
    templates.mkdir()
    (templates / "email.txt").write_text("Hi {{ statement.name }}!\n")
    config = workdir / "basic/config.toml"
    config.write_text('templates = "templates"\n' + config.read_text())

    make()
    path = workdir / "basic/output/annual/email/2025_Anytown_Charity_John_Smith.eml"
    text = read_email(path).get_body(preferencelist=("plain",))
    assert text is not None
    assert text.get_content() == "Hi John Smith!\n"


def test_make_reports_errors(workdir):
    """Configuration errors exit with a readable message."""

    config = workdir / "basic/config.toml"
    config.write_text(config.read_text().replace("[org]", "[orgs]"))

    result = CliRunner().invoke(donormail, ["make", "basic/config.toml"])
    assert result.exit_code == 1
    assert "Error: Unknown settings: orgs" in result.output


@pytest.fixture
def sent(monkeypatch):
    """Replace SMTP with a fake that records recipients."""

    recipients = []

    class FakeSMTP:
        def __init__(self, host, port):
            """Accept connection settings."""

        def __enter__(self):
            """Open the fake connection."""

            return self

        def __exit__(self, *args):
            """Close the fake connection."""

        def send_message(self, message):
            """Record a message recipient."""

            recipients.append(message["To"])

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    return recipients


def test_send(workdir, sent):
    """Send delivers pending emails up to the limit and moves them to sent."""

    make()
    config = workdir / "basic/config.toml"
    config.write_text(config.read_text().replace("limit = 50", "limit = 1"))

    result = CliRunner().invoke(donormail, ["send", "basic/config.toml"])
    assert result.exit_code == 0, result.output
    assert sent == ["John Appleseed <john.appleseed@example.com>"]
    assert "Emails remaining:  1" in result.output

    result = CliRunner().invoke(donormail, ["send", "basic/config.toml"])
    assert sent[-1] == "John Smith <john.smith@example.com>"
    assert "Emails remaining:  0" in result.output

    sent = sorted(p.name for p in (workdir / "basic/output/annual/sent").iterdir())
    assert len(sent) == 2


def test_send_again_after_force(workdir, sent):
    """Emails rewritten with --force replace their copies in sent."""

    make()
    assert CliRunner().invoke(donormail, ["send", "basic/config.toml"]).exit_code == 0
    make("--force")

    result = CliRunner().invoke(donormail, ["send", "basic/config.toml"])
    assert result.exit_code == 0, result.output
    assert len(sent) == 4
    folder = workdir / "basic/output/annual"
    assert list((folder / "email").iterdir()) == []
    assert len(list((folder / "sent").iterdir())) == 2
