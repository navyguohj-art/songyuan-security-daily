#!/usr/bin/env python3
"""Send a Sites publication notice through an existing local QQ SMTP config."""

from __future__ import annotations

import argparse
import os
import pathlib
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse


REQUIRED_KEYS = (
    "QQ_SMTP_HOST",
    "QQ_SMTP_PORT",
    "QQ_SMTP_USER",
    "QQ_SMTP_AUTH_CODE",
)


def parse_env_file(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def validate_site_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("site URL must be an absolute HTTPS URL")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-url", required=True, type=validate_site_url)
    parser.add_argument("--report-date", required=True)
    parser.add_argument(
        "--config",
        default=os.environ.get("QQ_SMTP_ENV_FILE"),
        help="Path to an existing local QQ SMTP environment file.",
    )
    args = parser.parse_args()

    if not args.config:
        raise SystemExit("QQ SMTP config path is not configured")

    config_path = pathlib.Path(args.config).expanduser()
    if not config_path.is_file():
        raise SystemExit("QQ SMTP config file was not found")

    config = parse_env_file(config_path)
    missing = [key for key in REQUIRED_KEYS if not config.get(key)]
    if missing:
        raise SystemExit("QQ SMTP config is incomplete")

    sender = config["QQ_SMTP_USER"]
    if not sender.lower().endswith("@qq.com"):
        raise SystemExit("QQ SMTP user must be a QQ email address")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = sender
    message["Subject"] = f"松原安全每日看板已更新（{args.report_date}）"
    message.set_content(
        "\n".join(
            [
                f"松原安全每日信息看板已完成 {args.report_date} 更新并发布。",
                "",
                f"最新站点：{args.site_url}",
                "",
                "本邮件由本机每日自动任务在 Codex Sites 发布成功后发送。",
            ]
        )
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        config["QQ_SMTP_HOST"],
        int(config["QQ_SMTP_PORT"]),
        context=context,
        timeout=30,
    ) as client:
        client.login(sender, config["QQ_SMTP_AUTH_CODE"])
        client.send_message(message)

    print("QQ publication notification sent successfully")


if __name__ == "__main__":
    main()
