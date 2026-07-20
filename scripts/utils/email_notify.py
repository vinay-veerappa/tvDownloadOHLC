"""
email_notify.py
===============
Utility to send email alerts to a mobile phone or email address.
Uses SMTP and credentials stored in `secrets.json` (or encrypted via DPAPI).

Required keys in secrets.json:
- `email_user`: The sender email address (e.g., "your.email@gmail.com")
- `email_password`: The App Password for the sender email
- `email_to` (Optional): The default destination email/SMS gateway (e.g., "1234567890@vtext.com")
- `email_smtp_server` (Optional): Default is "smtp.gmail.com"
- `email_smtp_port` (Optional): Default is 587
"""
import smtplib
import logging
from email.message import EmailMessage
from typing import Optional
from scripts.streaming.credentials_manager import get_secret

log = logging.getLogger(__name__)

def send_email(
    subject: str,
    body: str,
    to_email: Optional[str] = None,
    smtp_server: Optional[str] = None,
    smtp_port: Optional[int] = None
) -> bool:
    """
    Sends an email alert.

    Parameters
    ----------
    subject : str
        The subject of the email.
    body : str
        The main text body of the email.
    to_email : str, optional
        The destination email address or SMS gateway address. 
        If None, reads `email_to` from secrets.
    smtp_server : str, optional
        The SMTP server to use. Defaults to `email_smtp_server` secret or `smtp.gmail.com`.
    smtp_port : int, optional
        The SMTP port. Defaults to `email_smtp_port` secret or 587.

    Returns
    -------
    bool
        True if the email was successfully sent, False otherwise.
    """
    sender_user = get_secret("email_user")
    sender_pass = get_secret("email_password")

    if not sender_user or not sender_pass:
        log.error("Missing 'email_user' or 'email_password' in secrets.")
        return False

    dest_email = to_email or get_secret("email_to")
    if not dest_email:
        log.error("No destination email provided. Pass `to_email` or set `email_to` in secrets.")
        return False

    server = smtp_server or get_secret("email_smtp_server") or "smtp.gmail.com"
    port = smtp_port or int(get_secret("email_smtp_port") or 587)

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender_user
    msg["To"] = dest_email

    try:
        with smtplib.SMTP(server, port) as smtp:
            smtp.starttls()
            smtp.login(sender_user, sender_pass)
            smtp.send_message(msg)
            log.info(f"Email alert successfully sent to {dest_email}")
            return True
    except Exception as e:
        log.error(f"Failed to send email alert: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Quick test if run standalone
    send_email("Test Alert", "This is a test notification from tvDownloadOHLC.")
