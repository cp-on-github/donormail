import base64
import datetime
import mimetypes
import re
import traceback
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from io import BytesIO
from pathlib import Path

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateError,
    TemplateNotFound,
    TemplateSyntaxError,
    select_autoescape,
)
from xhtml2pdf import pisa

PACKAGE_TEMPLATES = Path(__file__).parent / "templates"

# template mistakes, including filters given the wrong kind of value and
# template files that are not valid text
TEMPLATE_ERRORS = (TemplateError, TypeError, ValueError)


class RenderError(Exception):
    def __init__(self, problem, donor=None):
        """Create an error for a problem, and the donor it happened for."""

        super().__init__(f"{problem}, for {donor}" if donor else problem)
        self.problem = problem
        self.donor = donor


class Renderer:
    def __init__(self, config, letter, today=None):
        """Create a renderer for one letter."""

        self.config = config
        self.letter = letter
        self.today = today or datetime.date.today()

        # letters carry the logo as data, since xhtml2pdf may refuse to read
        # files outside the working directory
        logo = config.org["logo"]
        self.letter_org = {**config.org, "logo": _data_uri(logo) if logo else ""}

        # user templates override package templates with the same name
        loaders = [FileSystemLoader(PACKAGE_TEMPLATES)]
        if config.templates:
            loaders.insert(0, FileSystemLoader(config.templates))

        self.env = Environment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(["html"], default_for_string=False),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["money"] = money
        self.env.filters["longdate"] = longdate
        self.env.filters["shortdate"] = shortdate
        self.env.filters["series"] = series

    def _context(self, statement, org=None):
        """Build template variables for a statement."""

        return {
            "org": org or self.config.org,
            "letter": self.letter,
            "statement": statement,
            "today": self.today,
        }

    def _render(self, name, statement, org=None):
        """Render a named template for a statement."""

        try:
            template = self.env.get_template(name)
            return template.render(self._context(statement, org))
        except TEMPLATE_ERRORS as e:
            raise RenderError(_describe(name, e), statement.name) from e

    def _subject(self, statement):
        """Render the email subject for a statement."""

        try:
            template = self.env.from_string(self.letter.subject)
            return template.render(self._context(statement))
        except TEMPLATE_ERRORS as e:
            raise RenderError(_describe("subject", e), statement.name) from e

    def verify(self, statement):
        """Render every template a statement uses, without making the PDF."""

        if statement.method == "mail" or self.letter.attach:
            self._render(self.letter.template, statement, self.letter_org)
        if statement.method == "email":
            self._subject(statement)
            self._render(self.letter.email_text, statement)
            self._render(self.letter.email_html, statement)

    def pdf(self, statement):
        """Render the letter as PDF bytes."""

        html = self._render(self.letter.template, statement, self.letter_org)
        buffer = BytesIO()
        result = pisa.CreatePDF(html, dest=buffer)

        # pisa reports failures on the status object it returns
        if getattr(result, "err", 0):
            raise RenderError("Cannot generate PDF", statement.name)
        return buffer.getvalue()

    def email(self, statement, pdf=None):
        """Render the email message, attaching the PDF if given."""

        sender = self.config.email
        subject = self._subject(statement)

        message = EmailMessage()
        message["From"] = formataddr((sender["name"], sender["address"]))
        message["To"] = formataddr((statement.name, statement.contact.email))
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain=sender["address"].split("@")[-1])
        if sender["reply_to"]:
            message["Reply-To"] = sender["reply_to"]
        if sender["bcc"]:
            message["Bcc"] = sender["bcc"]

        # plain text with an html alternative
        message.set_content(self._render(self.letter.email_text, statement))
        html = self._render(self.letter.email_html, statement)
        message.add_alternative(html, subtype="html")

        # the logo travels inside the email, so it shows when remote images are blocked
        logo = self.config.org["logo"]
        part = message.get_body(preferencelist=("html",))
        if logo and part is not None and "cid:logo" in html:
            maintype, subtype = _image_type(logo).split("/")
            part.add_related(
                logo.read_bytes(), maintype=maintype, subtype=subtype, cid="<logo>"
            )

        if pdf is not None:
            message.add_attachment(
                pdf,
                maintype="application",
                subtype="pdf",
                filename=f"{self.filename(statement)}.pdf",
            )
        return message

    def filename(self, statement):
        """Build a file name stem for a statement."""

        return slug(f"{self.letter.label}_{self.config.org['name']}_{statement.name}")


def _describe(name, error):
    """Explain a template error with its template file and line."""

    if isinstance(error, TemplateNotFound):
        return f"Template not found: {error.name}"

    # Jinja reports template lines as traceback frames, which may be in a
    # template the named one imports
    line = None
    if isinstance(error, TemplateSyntaxError):
        name = error.name or name
        line = error.lineno
    else:
        frames = traceback.extract_tb(error.__traceback__)
        frames = [f for f in frames if _is_template(f.filename)]
        if frames:
            line = frames[-1].lineno
            if frames[-1].filename != "<template>":
                name = Path(frames[-1].filename).name

    where = f"{name} line {line}" if line else name
    message = getattr(error, "message", None) or error
    return f"Template {where}: {message}"


def _image_type(path):
    """Guess an image's media type from its file name, PNG if unknown."""

    return mimetypes.guess_type(path.name)[0] or "image/png"


def _data_uri(path):
    """Encode an image file as a data: address."""

    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{_image_type(path)};base64,{data}"


def _is_template(filename):
    """Check if a traceback file is a template, not Python code."""

    if filename == "<template>":
        return True
    return not filename.endswith(".py") and not filename.startswith("<")


def slug(value):
    """Replace runs of unsafe file name characters with underscores."""

    return re.sub(r"[^A-Za-z0-9-]+", "_", value).strip("_")


def money(value):
    """Format an amount with thousands separators and cents."""

    return f"{value:,.2f}"


def longdate(value):
    """Format a date like January 5, 2025."""

    return f"{value:%B} {value.day}, {value.year}"


def shortdate(value):
    """Format a date like 1/5/2025."""

    return f"{value.month}/{value.day}/{value.year}"


def series(values):
    """Join values like A, B, and C."""

    values = list(values)
    if len(values) < 3:
        return " and ".join(values)
    return f"{', '.join(values[:-1])}, and {values[-1]}"
