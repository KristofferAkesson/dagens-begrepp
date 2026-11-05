#!/usr/bin/env python3
"""Postar dagens begrepp i Slack-kanalen.

Körs av GitHub Actions (.github/workflows/slack.yml) så att begreppet postas klockan 09.30 svensk
tid, både sommar och vinter. Dagens begrepp är det med dagens datum i svensk tid, samma regel som i
apparna, så Slack och apparna visar samma begrepp samma dag. Finns inget begrepp med dagens datum
postas ingenting.

    python3 scripts/posta_slack.py --prova                 visa meddelandet utan att posta
    python3 scripts/posta_slack.py --datum 2026-11-10 --prova
    SLACK_WEBHOOK_URL=… python3 scripts/posta_slack.py     posta
    python3 scripts/posta_slack.py --schema "30 7 * * *"   som den schemalagda körningen

GitHub anger scheman i UTC och känner inte till sommartid. Arbetsflödet schemaläggs därför både
07.30 och 08.30 UTC, och med --schema postar skriptet bara när den schemalagda tiden är 09.30 i
Stockholm den dagen: 07.30 UTC på sommaren och 08.30 UTC på vintern. Så postas begreppet en gång
per dag, även de dagar klockan ställs om.

Webbadressen till kanalen läses från miljövariabeln SLACK_WEBHOOK_URL, som i GitHub ligger som
hemlighet i repot. Skriptet använder bara Pythons standardbibliotek.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TIDSZON = ZoneInfo("Europe/Stockholm")
UTC = dt.timezone.utc
#: Klockslaget då begreppet postas, i svensk tid.
POSTNINGSTID = dt.time(9, 30)
EXEMPELTYP = {"verkligt": "Verkligt exempel", "illustrativt": "Illustrativt exempel"}
MANADER = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september",
           "oktober", "november", "december"]
VECKODAGAR = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]


def schemalagd_tid(schema: str, nu: dt.datetime) -> dt.datetime | None:
    """Tidpunkten i svensk tid då en körning med cron-schemat `schema` (i UTC) var planerad,
    samma UTC-dygn som `nu`. Utgår från schemat och inte från när körningen faktiskt startade,
    eftersom GitHub kan starta schemalagda körningar flera minuter sent. `None` om schemat inte
    är en daglig tid som "30 7 * * *"."""
    delar = schema.split()
    if len(delar) != 5 or not delar[0].isdigit() or not delar[1].isdigit() or delar[2:] != ["*", "*", "*"]:
        return None
    dygn = nu.astimezone(UTC).date()
    planerad = dt.datetime(dygn.year, dygn.month, dygn.day, int(delar[1]), int(delar[0]), tzinfo=UTC)
    return planerad.astimezone(TIDSZON)


def ska_posta(schema: str, nu: dt.datetime) -> bool:
    """`True` om den schemalagda körningen motsvarar 09.30 i Stockholm med dagens tidsskillnad mot
    UTC. Av de två scheman som arbetsflödet har stämmer det för exakt ett varje dag."""
    tid = schemalagd_tid(schema, nu)
    return tid is not None and tid.timetz().replace(tzinfo=None) == POSTNINGSTID


def dagens_begrepp(fil: dict, idag: dt.date) -> dict | None:
    """Begreppet med dagens datum, annars None. Till skillnad från apparna postas inget äldre
    begrepp en dag som saknar eget, så att samma begrepp inte postas två gånger."""
    return next((b for b in fil.get("begrepp", []) if b.get("datum") == idag.isoformat()), None)


def _escape(text: str) -> str:
    """Slack tolkar &, < och > i mrkdwn."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def sokning(fraga: str) -> str:
    """Ett förslag under Läs vidare som Slack-länk till en Google-sökning med förslaget ifyllt."""
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(fraga)
    return f"<{url}|{_escape(fraga)}>"


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
        detaljer.append("*Läs vidare:* " + ", ".join(sokning(fraga) for fraga in b["las_vidare"]))
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


def main(argv: list[str] | None = None, nu: dt.datetime | None = None) -> int:
    """`nu` är klockan i UTC, för tester; standard är nu."""
    parser = argparse.ArgumentParser(description="Postar dagens begrepp i Slack.")
    parser.add_argument("--fil", default="begrepp.json")
    parser.add_argument("--datum", metavar="ÅÅÅÅ-MM-DD", help="annan dag än i dag, för att prova")
    parser.add_argument("--prova", action="store_true", help="skriv ut meddelandet i stället för att posta")
    parser.add_argument("--schema", metavar="CRON",
                        help="schemat som startade körningen (github.event.schedule); postar bara om det är 09.30 svensk tid")
    args = parser.parse_args(argv)

    nu = nu or dt.datetime.now(UTC)
    if args.schema:
        if not ska_posta(args.schema, nu):
            tid = schemalagd_tid(args.schema, nu)
            klockslag = tid.strftime("%H.%M") if tid else "okänd tid"
            print(f"Schemat \"{args.schema}\" motsvarar {klockslag} svensk tid i dag, inte 09.30. Inget postas.")
            return 0
        idag = schemalagd_tid(args.schema, nu).date()
    else:
        idag = nu.astimezone(TIDSZON).date()
    if args.datum:
        idag = dt.date.fromisoformat(args.datum)
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
