# Canyon Verfügbarkeits-Monitor

GitHub Actions Workflow, der alle 10 Minuten Canyon-Produktseiten prüft und per E-Mail + Telegram benachrichtigt, sobald ein Rad verfügbar ist.

## Projektstruktur

```
canyon-monitor/
├── .github/
│   └── workflows/
│       └── monitor.yml        # GitHub Actions Workflow
├── scripts/
│   └── check_availability.py  # Monitor-Skript
└── README.md
```

## Setup

### 1. Repository auf GitHub erstellen

```bash
git init
git add .
git commit -m "Initial commit"
gh repo create canyon-monitor --public --push
```

### 2. GitHub Secrets konfigurieren

Unter **Settings → Secrets and variables → Actions** folgende Secrets anlegen:

| Secret              | Beschreibung                              | Beispiel              |
|---------------------|-------------------------------------------|-----------------------|
| `SMTP_SERVER`       | SMTP-Server                               | `smtp.gmail.com`      |
| `SMTP_PORT`         | SMTP-Port                                 | `587`                 |
| `SMTP_USER`         | Absender-E-Mail-Adresse                   | `deine@gmail.com`     |
| `SMTP_PASSWORD`     | App-Passwort (nicht das normale Passwort) | `xxxx xxxx xxxx xxxx` |
| `NOTIFY_EMAIL`      | Empfänger-E-Mail-Adresse                  | `deine@gmail.com`     |
| `TELEGRAM_BOT_TOKEN`| Bot-Token von @BotFather (optional)       | `123456:ABC...`       |
| `TELEGRAM_CHAT_ID`  | Deine Telegram Chat-ID (optional)         | `987654321`           |

### 3. Gmail App-Passwort erstellen

1. Google-Konto → Sicherheit → 2-Faktor-Authentifizierung aktivieren
2. Google-Konto → Sicherheit → App-Passwörter → „Mail" + „Windows-Computer"
3. Generierten 16-stelligen Code als `SMTP_PASSWORD` eintragen

### 4. Telegram Bot einrichten (optional)

1. [@BotFather](https://t.me/BotFather) öffnen → `/newbot` → Token kopieren → als `TELEGRAM_BOT_TOKEN` eintragen
2. [@userinfobot](https://t.me/userinfobot) schreiben → Chat-ID kopieren → als `TELEGRAM_CHAT_ID` eintragen
3. Einmal eine Nachricht an deinen Bot schicken (sonst kann er dir nicht schreiben)

## Räder konfigurieren

In `scripts/check_availability.py` die `BIKES`-Liste anpassen:

```python
BIKES = [
    {
        "name": "Modellname",
        "color": "Farbe",
        "size": "L",       # Gewünschte Größe
        "url": "https://www.canyon.com/...",
    },
]
```

## Manueller Test

Im GitHub-Repository unter **Actions → Canyon Verfügbarkeits-Monitor → Run workflow** den Workflow manuell starten. Mit der Option „Test-E-Mail senden" wird eine Benachrichtigung gesendet, auch wenn das Rad nicht verfügbar ist.

## Funktionsweise

1. Der Workflow läuft alle 10 Minuten auf GitHub-Servern (kostenlos im Free-Tier)
2. Das Python-Skript lädt die Canyon-Produktseiten und analysiert den HTML-Quellcode
3. Bei Verfügbarkeit werden E-Mail und Telegram-Nachricht mit direktem Kauflink gesendet
4. Keine externen Python-Pakete nötig – nur die Python-Standardbibliothek
