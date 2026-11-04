#!/usr/bin/env python3
"""Postar dagens begrepp i Slack-kanalen.

Körs varje morgon av GitHub Actions (.github/workflows/slack.yml). Dagens begrepp är det med
dagens datum i svensk tid, samma regel som i apparna, så Slack och apparna visar samma begrepp
samma dag. Finns inget begrepp med dagens datum postas ingenting.

    python3 scripts/posta_slack.py --prova                 visa meddelandet utan att posta
    python3 scripts/posta_slack.py --datum 2026-11-10 --prova
    SLACK_WEBHOOK_URL=… python3 scripts/posta_slack.py     posta

Webbadressen till kanalen läses från miljövariabeln SLACK_WEBHOOK_URL, som i GitHub ligger som
hemlighet i repot. Skriptet använder bara Pythons standardbibliotek.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from zoneinfo import ZoneInfo

TIDSZON = ZoneInfo("Europe/Stockholm")
EXEMPELTYP = {"verkligt": "Verkligt exempel", "illustrativt": "Illustrativt exempel"}
MANADER = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september",
           "oktober", "november", "december"]
VECKODAGAR = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]


def dagens_begrepp(fil: dict, idag: dt.date) -> dict | None:
    """Begreppet med dagens datum, annars None. Till skillnad från apparna postas inget äldre
    begrepp en dag som saknar eget, så att samma begrepp inte postas två gånger."""
    return next((b for b in fil.get("begrepp", []) if b.get("datum") == idag.isoformat()), None)


def _escape(text: str) -> str:
    """Slack tolkar &, < och > i mrkdwn."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def meddelande(b: dict, idag: dt.date) -> dict:
    """Ett Slack-meddelande med samma delar som korten i appen."""
    datum = f"{VECKODAGAR[idag.weekday()]} {idag.day} {MANADER[idag.month - 1]}"
    block: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": b["rubrik"][:150]}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"{_escape(b['omrade'])} · {datum}"}]},
        {"type": "section", "text": {"type": "mrkdwn", "text": _escape(b["brodtext"])}},
        {"type": "section", "text": {"type": "mrkdwn",
                                     "text": f"*{EXEMPELTYP.get(b.get('exempel_typ', ''), 'Exempel')}*\n{_escape(b['exempel'])}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Kärnan:* {_escape(b['karnan'])}"}},
    ]
    detaljer = []
    if b.get("termer"):
        detaljer.append(f"*Nyckelord:* {_escape(', '.join(b['termer']))}")
    if b.get("las_vidare"):
        detaljer.append(f"*Läs vidare:* {_escape(', '.join(b['las_vidare']))}")
    if detaljer:
        block.append({"type": "context", "elements": [{"type": "mrkdwn", "text": t} for t in detaljer]})
    # `text` visas i notiser och där block inte kan visas.
    return {"text": f"Dagens begrepp: {b['rubrik']}", "blocks": block}


def posta(webhook: str, data: dict) -> None:
    begaran = urllib.request.Request(webhook, data=json.dumps(data).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(begaran, timeout=30) as svar:
        if svar.status != 200:
            raise RuntimeError(f"Slack svarade med felkod {svar.status}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Postar dagens begrepp i Slack.")
    parser.add_argument("--fil", default="begrepp.json")
    parser.add_argument("--datum", metavar="ÅÅÅÅ-MM-DD", help="annan dag än i dag, för att prova")
    parser.add_argument("--prova", action="store_true", help="skriv ut meddelandet i stället för att posta")
    args = parser.parse_args(argv)

    idag = dt.date.fromisoformat(args.datum) if args.datum else dt.datetime.now(TIDSZON).date()
    with open(args.fil, encoding="utf-8") as f:
        fil = json.load(f)

    b = dagens_begrepp(fil, idag)
    if b is None:
        print(f"Inget begrepp har datumet {idag}. Inget postas.")
        return 0

    data = meddelande(b, idag)
    if args.prova:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook:
        print("FEL: SLACK_WEBHOOK_URL saknas. Lägg den som hemlighet i repot.")
        return 1
    posta(webhook, data)
    print(f"Postade {b['id']} ({b['rubrik']}) för {idag}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
