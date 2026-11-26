import getpass
import os
import smtplib
from email import message_from_bytes, policy

from donormail.config import ConfigError

PASSWORD_VARIABLE = "DONORMAIL_SMTP_PASSWORD"


class MailError(Exception):
    """Email could not be sent."""


class Mailer:
    def __init__(self, config, folder):
        """Create a mailer for the emails in a letter output folder."""

        self.smtp = config.smtp
        if not self.smtp["host"]:
            raise ConfigError("Missing setting: smtp.host")

        self.email_path = folder / "email"
        self.sent_path = folder / "sent"
        self.sent_path.mkdir(parents=True, exist_ok=True)

    def pending(self):
        """List emails waiting to be sent."""

        if not self.email_path.is_dir():
            return []
        return sorted(self.email_path.glob("*.eml"))

    def batch(self, limit=None):
        """List the pending emails the next send would deliver."""

        return self.pending()[: limit or self.smtp["limit"]]

    def send(self, limit=None):
        """Send pending emails up to the limit, moving each to sent.

        Returns the number sent.
        """

        emails = self.batch(limit)
        if not emails:
            return 0

        # connection failures are reported without a traceback
        try:
            connection = self._connect()
        except OSError as e:
            host = self.smtp["host"]
            raise MailError(f"Unable to connect to {host}: {e}") from e

        with connection:
            for path in emails:
                message = message_from_bytes(path.read_bytes(), policy=policy.default)
                try:
                    connection.send_message(message)
                except smtplib.SMTPException as e:
                    raise MailError(f"Unable to send {path.name}: {e}") from e
                # replace an earlier copy, e.g. after make --force
                path.replace(self.sent_path / path.name)

        return len(emails)

    def _connect(self):
        """Open an SMTP connection and log in if a user is set."""

        host, port = self.smtp["host"], self.smtp["port"]
        security = self.smtp["security"]

        if security == "ssl":
            connection = smtplib.SMTP_SSL(host, port)
        else:
            connection = smtplib.SMTP(host, port)
            if security == "starttls":
                connection.starttls()

        if self.smtp["user"]:
            password = os.environ.get(PASSWORD_VARIABLE) or getpass.getpass(
                prompt="SMTP Password: "
            )
            connection.login(self.smtp["user"], password)

        return connection
