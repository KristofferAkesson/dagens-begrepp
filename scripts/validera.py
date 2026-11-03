#!/usr/bin/env python3
"""Validerar begrepp.json enligt innehållsschema 4.

Användning:
  python3 scripts/validera.py begrepp.json
  python3 scripts/validera.py begrepp.json --jamfor forra-versionen.json

Med --jamfor kontrolleras också att begrepp som redan har visats
varken har tagits bort eller fått nytt datum, och att
innehallsversion har ändrats när innehållet har ändrats.
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

OBLIGATORISKA = ["id", "datum", "omrade", "rubrik", "brodtext", "exempel",
                 "exempel_typ", "karnan", "termer", "las_vidare", "granskad"]
TEXTFALT = ["id", "omrade", "rubrik", "brodtext", "exempel", "karnan"]
SKRIVREGELFALT = ["rubrik", "brodtext", "exempel", "karnan"]
EXEMPELTYPER = {"verkligt", "illustrativt"}
# Långt tankstreck, eller kort tankstreck med mellanslag runt (delar upp en mening).
# Kort tankstreck utan mellanslag, som i 0–6, är tillåtet.
TANKSTRECK = re.compile(r"—|\s–\s")


def las(sokvag):
    with open(sokvag, encoding="utf-8") as f:
        return json.load(f)


def till_datum(varde):
    try:
        return date.fromisoformat(varde)
    except (TypeError, ValueError):
        return None


def validera(doc, forra=None, idag=None):
    fel = []
    idag = idag or datetime.now(ZoneInfo("Europe/Stockholm")).date()

    if not isinstance(doc, dict):
        return ["Filen ska innehålla ett JSON-objekt på toppnivå."]
    if doc.get("schema_version") != 4:
        fel.append(f"schema_version ska vara 4, men är {doc.get('schema_version')!r}.")
    for falt in ("app", "innehallsversion"):
        varde = doc.get(falt)
        if not isinstance(varde, str) or not varde.strip():
            fel.append(f"Fältet {falt} saknas eller är tomt.")

    begrepp = doc.get("begrepp")
    if not isinstance(begrepp, list) or not begrepp:
        fel.append("Listan begrepp saknas eller är tom.")
        return fel

    sedda_id = set()
    sedda_datum = set()
    foregaende = None

    for nr, b in enumerate(begrepp, 1):
        if not isinstance(b, dict):
            fel.append(f"Begrepp {nr} är inte ett objekt.")
            continue
        namn = f"Begrepp {nr} ({b.get('id', 'utan id')})"

        for falt in OBLIGATORISKA:
            if falt not in b:
                fel.append(f"{namn}: fältet {falt} saknas.")
        for falt in TEXTFALT:
            if falt in b and (not isinstance(b[falt], str) or not b[falt].strip()):
                fel.append(f"{namn}: fältet {falt} är tomt.")
        for falt in ("termer", "las_vidare"):
            if falt in b and not (isinstance(b[falt], list) and all(isinstance(x, str) for x in b[falt])):
                fel.append(f"{namn}: fältet {falt} ska vara en lista med text.")
        if "exempel_typ" in b and b["exempel_typ"] not in EXEMPELTYPER:
            fel.append(f"{namn}: exempel_typ ska vara verkligt eller illustrativt.")
        if "granskad" in b and till_datum(b["granskad"]) is None:
            fel.append(f"{namn}: granskad är inget giltigt datum.")

        bid = b.get("id")
        if bid in sedda_id:
            fel.append(f"{namn}: id:t används redan av ett annat begrepp.")
        sedda_id.add(bid)

        d = till_datum(b.get("datum"))
        if d is None:
            fel.append(f"{namn}: datum saknas eller är ogiltigt (ska vara ÅÅÅÅ-MM-DD).")
        else:
            if d in sedda_datum:
                fel.append(f"{namn}: datumet {d} används redan av ett annat begrepp.")
            sedda_datum.add(d)
            if foregaende is not None:
                if d <= foregaende:
                    fel.append(f"{namn}: datumet {d} ligger inte efter föregående begrepp ({foregaende}).")
                elif d != foregaende + timedelta(days=1):
                    fel.append(f"{namn}: lucka i kalendariet mellan {foregaende} och {d}.")
            foregaende = d

        for falt in SKRIVREGELFALT:
            if isinstance(b.get(falt), str) and TANKSTRECK.search(b[falt]):
                fel.append(f"{namn}: {falt} innehåller tankstreck som delar upp en mening (KAN:s skrivregler).")

    if forra is not None:
        fel += jamfor(doc, forra, idag)
    return fel


def jamfor(doc, forra, idag):
    fel = []
    nya = {b.get("id"): b for b in doc.get("begrepp", []) if isinstance(b, dict)}
    for b in forra.get("begrepp", []):
        if not isinstance(b, dict):
            continue
        d = till_datum(b.get("datum"))
        if d is None or d > idag:
            continue  # Ännu inte visat, får ändras fritt.
        bid = b.get("id")
        if bid not in nya:
            fel.append(f"{bid} har redan visats ({d}) och får inte tas bort.")
        elif nya[bid].get("datum") != b.get("datum"):
            fel.append(f"{bid} har redan visats ({d}) och får inte byta datum.")
    if forra.get("begrepp") != doc.get("begrepp") and forra.get("innehallsversion") == doc.get("innehallsversion"):
        fel.append("Innehållet har ändrats men innehallsversion är densamma. Uppdatera innehallsversion.")
    return fel


def main():
    parser = argparse.ArgumentParser(description="Validerar begrepp.json.")
    parser.add_argument("fil", help="Sökväg till begrepp.json")
    parser.add_argument("--jamfor", help="Föregående version att jämföra med")
    parser.add_argument("--idag", help="Datum att räkna från, ÅÅÅÅ-MM-DD (för test)")
    args = parser.parse_args()

    try:
        doc = las(args.fil)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Kunde inte läsa {args.fil}: {e}")
        sys.exit(1)
    forra = None
    if args.jamfor:
        try:
            forra = las(args.jamfor)
        except (OSError, json.JSONDecodeError):
            print("Föregående version kunde inte läsas och jämförs därför inte.")

    fel = validera(doc, forra, till_datum(args.idag) if args.idag else None)
    if fel:
        print(f"Valideringen hittade {len(fel)} fel:")
        for f in fel:
            print(f"  • {f}")
        sys.exit(1)
    b = doc["begrepp"]
    print(f"Godkänd: {len(b)} begrepp, från {b[0]['datum']} till {b[-1]['datum']}.")


if __name__ == "__main__":
    main()
