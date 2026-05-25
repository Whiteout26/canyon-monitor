"""
Canyon Fahrrad Verfügbarkeits-Monitor
Überwacht mehrere Modelle gleichzeitig und sendet bei jedem verfügbaren
Rad eine E-Mail + Telegram-Nachricht.
"""

import os
import sys
import smtplib
import urllib.request
import urllib.error
import urllib.parse
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ─────────────────────────────────────────────
# FAHRRAD-LISTE – hier weitere Räder ergänzen
# ─────────────────────────────────────────────

BIKES = [
    {
        "name": "Endurace CF SLX 8 Di2",
        "color": "Atlantic Blue",
        "size": "L",
        "url": (
            "https://www.canyon.com/de-de/rennrad/endurance-rennrad/endurace/cf-slx/"
            "endurace-cf-slx-8-di2/4432.html"
            "?dwvar_4432_pv_rahmenfarbe=R130_P03"
        ),
    },
    {
        "name": "Endurace CF SLX 9 Di2",
        "color": "Colorflow",
        "size": "L",
        "url": (
            "https://www.canyon.com/de-de/rennrad/endurance-rennrad/endurace/cf-slx/"
            "endurace-cf-slx-9-di2/4537.html"
            "?dwvar_4537_pv_rahmenfarbe=R130_P04"
            "&dwvar_4537_pv_rahmengroesse=L"
        ),
    },
    {
        "name": "Aeroad CF SLX 8 AXS",
        "color": "Kaze",
        "size": "L",
        "url": (
            "https://www.canyon.com/de-de/rennrad/aero-rennrad/aeroad/cf-slx/"
            "aeroad-cf-slx-8-axs/4550.html"
            "?dwvar_4550_pv_rahmenfarbe=R107_P04"
            "&dwvar_4550_pv_rahmengroesse=L"
        ),
    },
    {
        "name": "Aeroad CF SLX 8 AXS",
        "color": "Midnight Blaze",
        "size": "L",
        "url": (
            "https://www.canyon.com/de-de/rennrad/aero-rennrad/aeroad/cf-slx/"
            "aeroad-cf-slx-8-axs/4550.html"
            "?dwvar_4550_pv_rahmenfarbe=R107_P05"
            "&dwvar_4550_pv_rahmengroesse=L"
        ),
    },
    # Weiteres Rad ergänzen:
    # {
    #     "name": "Modellname",
    #     "color": "Farbe",
    #     "size": "M",
    #     "url": "https://www.canyon.com/...",
    # },
]

# ─────────────────────────────────────────────
# E-MAIL EINSTELLUNGEN (via GitHub Secrets)
# ─────────────────────────────────────────────

SMTP_SERVER   = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
NOTIFY_EMAIL  = os.environ.get("NOTIFY_EMAIL", "")

# ─────────────────────────────────────────────
# TELEGRAM EINSTELLUNGEN (via GitHub Secrets)
# ─────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")  # von @BotFather
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")    # deine Chat-ID

# Tagestest- oder manueller Test-Modus (gesetzt via Workflow)
FORCE_NOTIFY = os.environ.get("FORCE_NOTIFY", "false").lower() == "true"
DAILY_TEST   = os.environ.get("FORCE_NOTIFY", "false").lower() == "true" and \
               os.environ.get("GITHUB_EVENT_NAME", "") == "schedule"

# ─────────────────────────────────────────────
# VERFÜGBARKEIT PRÜFEN
# ─────────────────────────────────────────────

UNAVAILABLE_SIGNALS = [
    '"isOrderable":false',
    '"orderable":false',
    '"availability":{"available":false',
    'addToCart" disabled',
    '"soldOut":true',
    "Derzeit nicht verfügbar",
    "Ausverkauft",
    "Nicht auf Lager",
]

AVAILABLE_SIGNALS = [
    '"isOrderable":true',
    '"orderable":true',
    '"availability":{"available":true',
    '"inStock":true',
    'In den Warenkorb',
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
    "Referer": "https://www.canyon.com/",
}


def check_bike(bike: dict) -> tuple[bool, str]:
    """Prüft ein einzelnes Fahrrad auf Verfügbarkeit."""
    req = urllib.request.Request(bike["url"], headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace").lower()
    except urllib.error.HTTPError as e:
        return False, f"HTTP-Fehler {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Verbindungsfehler: {e.reason}"

    size = bike["size"]
    size_available   = f'data-size="{size}" dataavailable="true"'.lower()
    size_unavailable = f'data-size="{size}" dataavailable="false"'.lower()

    found_available   = any(s.lower() in html for s in AVAILABLE_SIGNALS)   or size_available   in html
    found_unavailable = any(s.lower() in html for s in UNAVAILABLE_SIGNALS) or size_unavailable in html

    if found_available and not found_unavailable:
        return True, "Verfügbar (positives Signal gefunden)"
    if found_unavailable:
        return False, "Nicht verfügbar"
    return False, "Status unklar – Seite möglicherweise geändert"


# ─────────────────────────────────────────────
# E-MAIL VERSENDEN
# ─────────────────────────────────────────────

def send_email(bike: dict, status_text: str):
    """Sendet eine HTML-E-Mail für ein bestimmtes Fahrrad."""
    if not all([SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL]):
        print("  ⚠  E-Mail-Zugangsdaten fehlen – übersprungen.")
        return

    prefix     = "📋 Täglicher Statusbericht" if DAILY_TEST else "🚴 Verfügbar"
    subject    = f"{prefix}: Canyon {bike['name']} ({bike['color']}, {bike['size']})"
    headline   = "📋 Täglicher Statusbericht" if DAILY_TEST else "🚴 Dein Canyon-Bike ist verfügbar!"
    note       = "<p style='font-size:13px;color:#e8401c;'><b>ℹ️ Dies ist dein automatischer Tagesbericht – kein echtes Verfügbarkeitssignal.</b></p>" if DAILY_TEST else ""

    html_body = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto;padding:20px;">
      <h2 style="color:#e8401c;">{headline}</h2>
      {note}
      <table style="width:100%;border-collapse:collapse;margin:16px 0;">
        <tr>
          <td style="padding:8px 0;color:#666;font-size:14px;width:120px;">Modell</td>
          <td style="padding:8px 0;font-size:14px;font-weight:bold;">Canyon {bike['name']}</td>
        </tr>
        <tr style="background:#f9f9f9;">
          <td style="padding:8px 6px;color:#666;font-size:14px;">Farbe</td>
          <td style="padding:8px 6px;font-size:14px;">{bike['color']}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#666;font-size:14px;">Größe</td>
          <td style="padding:8px 0;font-size:14px;">{bike['size']}</td>
        </tr>
      </table>
      <p style="font-size:13px;color:#888;">
        Status: {status_text}<br>
        Geprüft am: {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')} UTC
      </p>
      <a href="{bike['url']}"
         style="display:inline-block;margin-top:16px;padding:14px 28px;
                background:#e8401c;color:#fff;text-decoration:none;
                border-radius:6px;font-weight:bold;font-size:16px;">
        Jetzt kaufen →
      </a>
      <hr style="margin-top:32px;border:none;border-top:1px solid #eee;">
      <p style="font-size:11px;color:#aaa;">
        Canyon Monitor · GitHub Actions · Automatische Benachrichtigung
      </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())
        print("  ✅ E-Mail gesendet!")
    except smtplib.SMTPException as e:
        print(f"  ❌ E-Mail-Fehler: {e}")


# ─────────────────────────────────────────────
# TELEGRAM VERSENDEN
# ─────────────────────────────────────────────

def send_telegram(bike: dict):
    """Sendet eine Telegram-Nachricht mit Kauflink."""
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("  ⚠  Telegram-Zugangsdaten fehlen – übersprungen.")
        return

    timestamp = datetime.now().strftime("%d.%m.%Y um %H:%M") + " UTC"

    # Sonderzeichen für MarkdownV2 escapen
    def esc(text: str) -> str:
        for ch in r"_*[]()~`>#+-=|{}.!":
            text = text.replace(ch, f"\\{ch}")
        return text

    text = (
        f"🚴 *Canyon {esc(bike['name'])}* ist verfügbar\\!\n\n"
        f"🎨 Farbe: {esc(bike['color'])}\n"
        f"📐 Größe: {esc(bike['size'])}\n"
        f"🕐 {esc(timestamp)}\n\n"
        f"[🛒 Jetzt kaufen]({bike['url']})"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": False,
    }

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        if result.get("ok"):
            print("  ✅ Telegram-Nachricht gesendet!")
        else:
            print(f"  ❌ Telegram-Fehler: {result.get('description', 'Unbekannter Fehler')}")
    except urllib.error.URLError as e:
        print(f"  ❌ Telegram-Verbindungsfehler: {e.reason}")


# ─────────────────────────────────────────────
# HAUPTPROGRAMM
# ─────────────────────────────────────────────

def main():
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    print(f"[{timestamp}] Canyon-Monitor startet – {len(BIKES)} Rad/Räder werden geprüft\n")

    if DAILY_TEST:
        print("📋 TÄGLICHER STATUSBERICHT – Benachrichtigungen werden unabhängig vom Status gesendet!\n")
    elif FORCE_NOTIFY:
        print("⚠  FORCE_NOTIFY aktiv – Benachrichtigungen werden unabhängig vom Status gesendet!\n")

    any_available = False

    for bike in BIKES:
        label = f"Canyon {bike['name']} | {bike['color']} | Gr. {bike['size']}"
        print(f"🔍 {label}")

        available, status = check_bike(bike)

        if available or FORCE_NOTIFY:
            if available:
                print(f"  ✅ VERFÜGBAR – {status}")
            else:
                print(f"  ⚠  Nicht verfügbar, aber FORCE_NOTIFY aktiv – sende trotzdem.")
            send_email(bike, status)
            send_telegram(bike)
            any_available = True
        else:
            print(f"  ❌ nicht verfügbar – {status}")

        print()

    if any_available:
        print("🎉 Mindestens ein Rad ist verfügbar – Benachrichtigungen verschickt!")
    else:
        print("😴 Kein Rad verfügbar – nächste Prüfung in 10 Minuten.")

    sys.exit(0)


if __name__ == "__main__":
    main()
