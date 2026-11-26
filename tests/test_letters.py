from email import message_from_bytes, policy
from io import BytesIO

from click.testing import CliRunner
from pypdf import PdfReader

from donormail.cli import donormail


def make(letter):
    """Run make with the QuickBooks example configuration."""

    result = CliRunner().invoke(
        donormail, ["make", "quickbooks/config.toml", "--letter", letter]
    )
    assert result.exit_code == 0, result.output
    return result


def read_email(path):
    """Parse an email file."""

    return message_from_bytes(path.read_bytes(), policy=policy.default)


def pdf_text(data):
    """Extract text from PDF bytes with whitespace collapsed."""

    pages = PdfReader(BytesIO(data)).pages
    return [" ".join(page.extract_text().split()) for page in pages]


def attachment(message):
    """Get the first attachment bytes."""

    return next(message.iter_attachments()).get_content()


def test_annual_letter_sections(workdir):
    """Annual letters show each kind of gift with third parties on the last page."""

    make("annual")
    folder = workdir / "quickbooks/output/annual"

    message = read_email(folder / "email/2025_Anytown_Charity_Jane_Doe.eml")
    text = message.get_body(preferencelist=("plain",))
    assert text is not None
    assert "2025 tax-deductible contributions total $130.00" in text.get_content()
    summary, details, last = pdf_text(attachment(message))
    assert "Dear Jane," in summary
    assert "Your gifts supported Education and Events." in summary
    assert "Your tax-deductible contributions in 2025 $130.00" in summary
    assert "This is the $200.00 you contributed, less $70.00 that is not" in summary
    assert "No other goods or services were provided" in summary
    assert (
        "Gifts you made through Workplace Giving, totaling $500.00, are not included"
        in summary
    )
    assert "Contributions with goods or services received" in details
    assert "$75.00 $45.00 $30.00" in details
    assert "Workplace Giving" not in details
    assert "not a tax receipt" in last
    assert "Workplace Giving $500.00" in last

    # donors without goods or services get the plain statement
    message = read_email(folder / "email/2025_Anytown_Charity_ANONYMOUS_Pat_Kim.eml")
    summary, details = pdf_text(attachment(message))
    assert "No goods or services were provided in exchange" in summary
    assert "8/1/2025 Housing $50.00" in details

    # third-party only donors get just the third-party page
    message = read_email(folder / "email/2025_Anytown_Charity_Sam_Lee.eml")
    text = message.get_body(preferencelist=("plain",))
    assert text is not None
    assert "Your gifts through Family Donor Fund are listed" in text.get_content()
    assert "tax-deductible" not in text.get_content()
    (page,) = pdf_text(attachment(message))
    assert "Family Donor Fund provides your tax receipt" in page
    assert "this letter is not a tax receipt" in page
    assert "Dear Sam Lee," in page
    assert "Total tax-deductible" not in page

    # in-kind gifts are described without a value
    summary, details = pdf_text(
        (folder / "mail/2025_Anytown_Charity_Acme_Corp.pdf").read_bytes()
    )
    assert "We gratefully received the non-cash gift" in summary
    assert "tax-deductible contributions" not in summary
    assert "does not assign a value" in summary
    assert "Two laptops" in details
    assert "$250.00" not in summary + details


def test_event_email(workdir):
    """Event emails list payments, value received, and the disclosure."""

    make("welcome")
    folder = workdir / "quickbooks/output/welcome/email"
    assert sorted(p.name for p in folder.iterdir()) == [
        "Welcome_Home_Anytown_Charity_Jane_Doe.eml"
    ]

    message = read_email(folder / "Welcome_Home_Anytown_Charity_Jane_Doe.eml")
    assert message["Subject"] == "Thank you for attending Welcome Home"
    assert list(message.iter_attachments()) == []
    assert any(p["Content-ID"] == "<logo>" for p in message.walk())

    text = message.get_body(preferencelist=("plain",))
    assert text is not None
    content = text.get_content()
    assert "Dear Jane," in content
    assert "Events: T-Shirt" in content
    assert "Value received:  $45.00" in content
    assert "Total deductible: $30.00" in content
    assert "limited to the excess of the amount paid" in content


def test_letter_without_programs(workdir):
    """Details tables keep their layout when gifts have no program."""

    basic = workdir / "basic"
    (basic / "gifts.csv").write_text(
        "Date,Donor,Amount,Project,Item,Value,Description\n"
        "3/1/2025,John Doe,20,,,,\n"
        "3/28/2025,John Doe,110,,,1380,3 Bridal dresses\n"
    )

    result = CliRunner().invoke(donormail, ["make", "basic/config.toml"])
    assert result.exit_code == 0, result.output
    pdf = (basic / "output/annual/mail/2025_Anytown_Charity_John_Doe.pdf").read_bytes()
    _, details = pdf_text(pdf)
    assert "Program" not in details
    assert "Date Amount 3/1/2025 $20.00" in details
    assert "Date Item Paid Value received Deductible" in details
    assert "3/28/2025 3 Bridal dresses $110.00 $1,380.00 $0.00" in details


def test_letter_logo_from_another_folder(workdir, monkeypatch):
    """The logo is in the letter when make runs outside the config folder."""

    elsewhere = workdir / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    config = workdir / "basic/config.toml"

    result = CliRunner().invoke(donormail, ["make", str(config)])
    assert result.exit_code == 0, result.output
    pdf = workdir / "basic/output/annual/mail/2025_Anytown_Charity_John_Doe.pdf"
    assert len(PdfReader(pdf).pages[0].images) == 1
