"""
email_notify.py
===============
Utility to send email alerts to a mobile phone (SMS gateway) or email addresses.
Uses SMTP and credentials stored in `secrets.json` (or encrypted via DPAPI).

Features:
- Multiple recipients (broadcast)
- File attachments
- HTML and Plain Text support
- Async non-blocking execution (fire-and-forget)
- Automatic retry logic for SMTP transient errors

Required keys in secrets.json:
- `email_user`: The sender email address (e.g., "your.email@gmail.com")
- `email_password`: The App Password for the sender email
- `email_to` (Optional): The default destination email/SMS gateway or list of emails
- `email_smtp_server` (Optional): Default is "smtp.gmail.com"
- `email_smtp_port` (Optional): Default is 587
"""
import smtplib
import logging
import mimetypes
import time
from pathlib import Path
from email.message import EmailMessage
from typing import Optional, Union, List
from concurrent.futures import ThreadPoolExecutor
from scripts.streaming.credentials_manager import get_secret

log = logging.getLogger(__name__)

# Single background thread for non-blocking email sending
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="EmailNotifier")

def _send_email_sync(
    subject: str,
    body: str,
    to_email: Optional[Union[str, List[str]]] = None,
    smtp_server: Optional[str] = None,
    smtp_port: Optional[int] = None,
    is_html: bool = False,
    file_paths: Optional[List[Union[str, Path]]] = None
) -> bool:
    """Synchronous internal worker that actually sends the email."""
    sender_user = get_secret("email_user")
    sender_pass = get_secret("email_password")

    if not sender_user or not sender_pass:
        log.error("Missing 'email_user' or 'email_password' in secrets.")
        return False

    # Resolve destinations
    dest_raw = to_email or get_secret("email_to")
    if not dest_raw:
        log.error("No destination email provided. Pass `to_email` or set `email_to` in secrets.")
        return False

    if isinstance(dest_raw, str):
        # Handle comma-separated strings if present in secrets
        destinations = [d.strip() for d in dest_raw.split(',')]
    else:
        destinations = dest_raw

    server = smtp_server or get_secret("email_smtp_server") or "smtp.gmail.com"
    port = smtp_port or int(get_secret("email_smtp_port") or 587)

    # Build the message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_user
    msg["To"] = ", ".join(destinations)

    if is_html:
        # Plain text fallback plus HTML
        msg.set_content("Please enable HTML to view this email.")
        msg.add_alternative(body, subtype='html')
    else:
        msg.set_content(body)

    # Attachments
    if file_paths:
        for fpath in file_paths:
            path_obj = Path(fpath)
            if not path_obj.exists():
                log.warning(f"Attachment not found: {path_obj}")
                continue
            
            ctype, encoding = mimetypes.guess_type(str(path_obj))
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)

            try:
                with open(path_obj, 'rb') as f:
                    msg.add_attachment(
                        f.read(),
                        maintype=maintype,
                        subtype=subtype,
                        filename=path_obj.name
                    )
            except Exception as e:
                log.error(f"Failed to attach {path_obj.name}: {e}")

    # Send with retry logic
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with smtplib.SMTP(server, port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(sender_user, sender_pass)
                smtp.send_message(msg)
                log.info(f"Email alert successfully sent to {len(destinations)} recipient(s).")
                return True
        except Exception as e:
            if attempt < max_retries:
                log.warning(f"SMTP error (attempt {attempt}/{max_retries}), retrying in 3s... ({e})")
                time.sleep(3)
            else:
                log.error(f"Failed to send email alert after {max_retries} attempts: {e}")
                return False
    return False


def send_email(
    subject: str,
    body: str,
    to_email: Optional[Union[str, List[str]]] = None,
    smtp_server: Optional[str] = None,
    smtp_port: Optional[int] = None,
    is_html: bool = False,
    file_paths: Optional[List[Union[str, Path]]] = None,
    blocking: bool = False
) -> bool:
    """
    Sends an email alert (asynchronously by default).

    Parameters
    ----------
    subject : str
        The subject of the email.
    body : str
        The main text body (or HTML) of the email.
    to_email : str or List[str], optional
        The destination email(s) or SMS gateway address(es). 
        If None, reads `email_to` from secrets.
    smtp_server : str, optional
        The SMTP server to use. Defaults to `email_smtp_server` secret or `smtp.gmail.com`.
    smtp_port : int, optional
        The SMTP port. Defaults to `email_smtp_port` secret or 587.
    is_html : bool, optional
        If True, the body is treated as HTML.
    file_paths : List[str | Path], optional
        List of absolute or relative file paths to attach to the email.
    blocking : bool, optional
        If True, waits for the email to send before returning. Defaults to False (fire-and-forget).

    Returns
    -------
    bool
        True if the email was successfully sent (if blocking=True). 
        If blocking=False, always returns True immediately.
    """
    if blocking:
        return _send_email_sync(
            subject, body, to_email, smtp_server, smtp_port, is_html, file_paths
        )
    else:
        # Fire and forget
        _executor.submit(
            _send_email_sync,
            subject, body, to_email, smtp_server, smtp_port, is_html, file_paths
        )
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Quick test if run standalone (blocking to see output)
    send_email(
        subject="Test Alert", 
        body="This is a test notification from tvDownloadOHLC.",
        blocking=True
    )
