"""Odeslání přehledu e-mailem přes SMTP."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config


def send(subject: str, html_body: str) -> None:
    if not config.EMAIL_TO or not config.SMTP_HOST:
        print("E-mail není nakonfigurován (EMAIL_TO / SMTP_HOST chybí).")
        print("--- náhled přehledu ---")
        print(html_body[:1500])
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM
    msg["To"] = ", ".join(config.EMAIL_TO)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
        s.starttls()
        if config.SMTP_USER:
            s.login(config.SMTP_USER, config.SMTP_PASS)
        s.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())
    print(f"Odesláno na: {', '.join(config.EMAIL_TO)}")
