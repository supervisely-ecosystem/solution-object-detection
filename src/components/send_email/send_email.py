import mimetypes
import os
import smtplib
from typing import Optional

from supervisely.app.widgets import Button, Container, Field, Input, TextArea, Widget

SMTP_PROVIDERS = {
    "gmail.com": ("smtp.gmail.com", 587),
    "outlook.com": ("smtp.office365.com", 587),
    "hotmail.com": ("smtp.office365.com", 587),
    "live.com": ("smtp.office365.com", 587),
    "yahoo.com": ("smtp.mail.yahoo.com", 587),
    "icloud.com": ("smtp.mail.me.com", 587),
}


class SendEmail(Widget):
    class EmailCredentials:
        def __init__(
            self,
            username: str,
            password: str,
            host: Optional[str] = None,
            port: Optional[int] = None,
        ):
            if (not username or not password) or (username.strip() == "" or password.strip() == ""):
                raise ValueError("Username and password must be provided.")
            self.username = username
            self.password = password

            domain = self.get_domain()
            _host, _port = SMTP_PROVIDERS.get(domain, (None, None))
            self.host = host or _host
            self.port = port or _port
            if not self.host or not self.port:
                raise ValueError(
                    f"No SMTP settings found for domain '{domain}'. "
                    "Please pass smtp_host and smtp_port explicitly."
                )

        def get_domain(self) -> str:
            """
            Extracts the email domain from the username.
            """
            return self.username.split("@")[-1].lower()

    def __init__(
        self, default_subject: str = None, default_body: str = None, widget_id: str = None
    ):
        self._default_subject = default_subject
        self._default_body = default_body

        target_addresses_widget = Input(
            minlength=1,
            maxlength=100,
            placeholder="user1@example.com, user2@example.com",
            size="small",
            type="textarea",
        )
        # @TODO: Maybe add icons
        target_addresses_field = Field(
            target_addresses_widget,
            "Target email addresses",
            "Enter email addresses to separated by commas",
        )
        self._target_addresses_input = target_addresses_widget

        subject_widget = Input(
            "", 0, 300, placeholder="Enter email subject here...", type="textarea"
        )
        subject_input_field = Field(
            subject_widget, "Email Subject", "Configure the subject of the email notification."
        )
        self._subject_input = subject_widget

        body_widget = TextArea(placeholder="Enter email body here...", rows=10, autosize=False)
        body_input_field = Field(
            body_widget,
            "Email Body",
            "Configure the body of the email notification.",
        )
        self._body_input = body_widget

        self.apply_button = Button("Apply")

        self._content = Container(
            [target_addresses_field, subject_input_field, body_input_field, self.apply_button]
        )
        super().__init__(widget_id=widget_id, file_path=__file__)

    def get_target_addresses(self):
        """
        Returns a list of email addresses to send the notification to.
        If no addresses are provided, returns None.
        """
        value = self._target_addresses_input.get_value()
        if not value:
            return None
        return self._target_addresses_input.get_value().split(",")

    def get_subject(self):
        """
        Returns the subject of the email notification.
        If no subject is provided, returns an empty string.
        """
        return self._subject_input.get_value()

    def get_body(self):
        """
        Returns the body of the email notification.
        If no body is provided, returns an empty string.
        """
        return self._body_input.get_value()

    def get_json_data(self):
        return {}

    def get_json_state(self):
        return {}

    def send_email(self, credentials: EmailCredentials, attachments: Optional[list] = None):
        """
        Send an email via SMTP. If smtp_host/port are not provided,
        they will be inferred from the username's email domain using SMTP_PROVIDERS.
        """

        from email.message import EmailMessage

        from supervisely import logger

        msg = EmailMessage()
        msg["Subject"] = self.get_subject() or self._default_subject
        msg["From"] = credentials.username
        msg["To"] = self.get_target_addresses() or [credentials.username]

        body = self.get_body() or self._default_body
        msg.set_content(body)

        for path in attachments or []:
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Attachment not found: {path}")
            ctype, encoding = mimetypes.guess_type(path)
            maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
            with open(path, "rb") as fp:
                msg.add_attachment(
                    fp.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path)
                )

        with smtplib.SMTP(self.creds.host, self.creds.port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            try:
                server.login(self.creds.username, self.creds.password)
            except smtplib.SMTPAuthenticationError as e:
                logger.error("Failed to auxthenticate with the provided email credentials.")
                raise e
            except (smtplib.SMTPException, smtplib.SMTPServerDisconnected) as e:
                logger.error(f"Failed to login to SMTP: {e}", exc_info=False)
                raise e
            server.send_message(msg)
            logger.info(f"Email sent to {self.to_addrs}")
