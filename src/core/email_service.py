"""SMTP-based email delivery (stdlib only — smtplib + email.mime).

Falls back to logging the message when SMTP is not configured, so password
reset works out of the box in local/dev environments without any setup.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config.models import EmailConfig
from .logging_config import get_logger

logger = get_logger(__name__)


class EmailService:
    def __init__(self, config: EmailConfig):
        self.config = config

    @property
    def _is_configured(self) -> bool:
        return bool(self.config.enabled and self.config.smtp_host)

    def send(self, to_email: str, subject: str, text_body: str, html_body: str = "") -> bool:
        """Send an email. Returns True on success (or on log-only fallback)."""
        if not self._is_configured:
            logger.info(f"[EMAIL:log-only] To: {to_email} | Subject: {subject}\n{text_body}")
            return True

        password = os.environ.get(self.config.smtp_password_env, "")
        if not password:
            logger.warning(
                f"Email delivery skipped — {self.config.smtp_password_env} env var not set. "
                f"Logging instead: To: {to_email} | Subject: {subject}"
            )
            logger.info(f"[EMAIL:log-only] {text_body}")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_address}>"
            msg["To"] = to_email
            msg.attach(MIMEText(text_body, "plain"))
            if html_body:
                msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=10) as server:
                if self.config.use_tls:
                    server.starttls()
                if self.config.smtp_username:
                    server.login(self.config.smtp_username, password)
                server.sendmail(self.config.from_address, [to_email], msg.as_string())

            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def send_password_reset_email(self, to_email: str, reset_link: str) -> bool:
        subject = "Reset your RAGenie password"
        text_body = (
            f"We received a request to reset your RAGenie password.\n\n"
            f"Reset your password using this link (expires in "
            f"{self.config.reset_token_expire_minutes} minutes):\n{reset_link}\n\n"
            f"If you didn't request this, you can safely ignore this email."
        )
        html_body = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
          <h2>Reset your RAGenie password</h2>
          <p>We received a request to reset your password. This link expires in
          {self.config.reset_token_expire_minutes} minutes.</p>
          <p><a href="{reset_link}" style="background:#3b82f6;color:#fff;padding:10px 20px;
          border-radius:8px;text-decoration:none;display:inline-block">Reset Password</a></p>
          <p style="color:#888;font-size:12px">If you didn't request this, you can safely ignore
          this email.</p>
        </div>
        """
        return self.send(to_email, subject, text_body, html_body)
