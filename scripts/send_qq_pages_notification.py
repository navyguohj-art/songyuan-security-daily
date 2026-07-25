#!/usr/bin/env python3
"""Send a GitHub Pages publication notice through QQ SMTP."""

from __future__ import annotations

import datetime as dt
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse


BEIJING_TZ = dt.timezone(dt.timedelta(hours=8))


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Required environment variable is missing: {name}")
    return value


def main() -> None:
    sender = required_env("QQ_SMTP_USER")
    auth_code = required_env("QQ_SMTP_AUTH_CODE")
    pages_url = required_env("PAGES_URL")

    if not sender.lower().endswith("@qq.com"):
        raise SystemExit("QQ_SMTP_USER must be a QQ email address")
    parsed_url = urlparse(pages_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc.endswith("github.io"):
        raise SystemExit("PAGES_URL must be an HTTPS GitHub Pages URL")

    report_date = dt.datetime.now(BEIJING_TZ).date().isoformat()
    message = EmailMessage()
    message["From"] = sender
    message["To"] = sender
    message["Subject"] = f"松原安全每日看板已更新（{report_date}）"
    message.set_content(
        "\n".join(
            [
                f"松原安全每日信息看板已完成 {report_date} 更新并发布。",
                "",
                f"最新站点：{pages_url}",
                "",
                "本邮件由 GitHub Actions 在 GitHub Pages 发布成功后自动发送。",
            ]
        )
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.qq.com", 465, context=context, timeout=30) as client:
        client.login(sender, auth_code)
        client.send_message(message)

    print("QQ publication notification sent successfully")


if __name__ == "__main__":
    main()
