#!/usr/bin/env python3
"""Validerar begrepp.json enligt reglerna för Dagens begrepp (schema 4).

Körs av GitHub Actions vid varje push och pull request, och kan köras lokalt:

    python3 scripts/validera.py begrepp.json
    python3 scripts/validera.py begrepp.json --foregaende origin/main

Med --foregaende jämförs filen med versionen i en annan commit, så att begrepp som
redan har visats inte tas bort eller byter id eller datum. Skriptet använder bara
Pythons standardbibliotek.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

SCHEMA = 4
EXEMPELTYPER = {"verkligt", "illustrativt"}
TEXTFALT = ["id", "datum", "omrade", "rubrik", "brodtext", "exempel", "exempel_typ", "karnan",
            "period", "granskad"]
LISTFALT = ["termer", "las_vidare"]
# Datum tolkas i svensk tid, där appen används.
TIDSZON = ZoneInfo("Europe/Stockholm")

# KAN:s skrivregler: inga tankstreck som delar upp meningar. Ett tankstreck mellan siffror
# ("0–6") är ett intervall och är tillåtet.
TANKSTRECK = re.compile(r"—|\s[–-]\s|(?<!\d)–|–(?!\d)")


def las_datum(text: object) -> dt.date | None:
    """Ett datum i formatet ÅÅÅÅ-MM-DD, annars None."""
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def ar_innehallsversion(text: object) -> bool:
    """Ett datum, eventuellt följt av ett löpnummer för fler publiceringar samma dag: 2026-11-03.2."""
    if not isinstance(text, str):
        return False
    traff = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(\.[2-9])?", text)
    return traff is not None and las_datum(traff.group(1)) is not None


def validera(fil: object, foregaende: object | None = None, idag: dt.date | None = None) -> list[str]:
    """Returnerar en lista med fel. En tom lista betyder att filen är godkänd."""
    idag = idag or dt.datetime.now(TIDSZON).date()
    fel: list[str] = []

    if not isinstance(fil, dict):
        return ["Filen ska innehålla ett JSON-objekt."]
    if fil.get("schema_version") != SCHEMA:
        fel.append(f"schema_version ska vara {SCHEMA}, men är {fil.get('schema_version')!r}.")
    if not isinstance(fil.get("app"), str) or not fil["app"].strip():
        fel.append("Fältet \"app\" saknas eller är tomt.")
    if not ar_innehallsversion(fil.get("innehallsversion")):
        fel.append("innehallsversion ska vara ett datum i formatet ÅÅÅÅ-MM-DD, "
                   "eller till exempel ÅÅÅÅ-MM-DD.2 vid fler publiceringar samma dag.")
    begrepp = fil.get("begrepp")
    if not isinstance(begrepp, list) or not begrepp:
        fel.append("Fältet \"begrepp\" ska vara en lista med minst ett begrepp.")
        return fel

    fel += _validera_begrepp(begrepp)
    if isinstance(foregaende, dict):
        fel += _jamfor(fil, foregaende, idag)
    return fel


def _validera_begrepp(begrepp: list) -> list[str]:
    fel: list[str] = []
    sedda_id: dict[str, int] = {}
    sedda_datum: dict[str, int] = {}
    foregaende_datum: dt.date | None = None

    for nr, b in enumerate(begrepp, start=1):
        if not isinstance(b, dict):
            fel.append(f"Begrepp {nr} är inte ett objekt.")
            continue
        namn = f"Begrepp {nr} ({b.get('id', 'utan id')})"

        for falt in TEXTFALT:
            if not isinstance(b.get(falt), str) or not b[falt].strip():
                fel.append(f"{namn}: fältet \"{falt}\" saknas eller är tomt.")
        for falt in LISTFALT:
            varde = b.get(falt)
            if not isinstance(varde, list) or not varde or not all(isinstance(v, str) and v.strip() for v in varde):
                fel.append(f"{namn}: fältet \"{falt}\" ska vara en lista med minst en text.")

        if isinstance(b.get("exempel_typ"), str) and b["exempel_typ"] and b["exempel_typ"] not in EXEMPELTYPER:
            fel.append(f"{namn}: exempel_typ ska vara verkligt eller illustrativt, inte {b['exempel_typ']!r}.")
        if isinstance(b.get("granskad"), str) and b["granskad"] and las_datum(b["granskad"]) is None:
            fel.append(f"{namn}: granskad ska vara ett datum i formatet ÅÅÅÅ-MM-DD.")

        bid = b.get("id")
        if isinstance(bid, str) and bid:
            if bid in sedda_id:
                fel.append(f"{namn}: samma id som begrepp {sedda_id[bid]}.")
            sedda_id.setdefault(bid, nr)

        datum = las_datum(b.get("datum"))
        if isinstance(b.get("datum"), str) and b["datum"] and datum is None:
            fel.append(f"{namn}: datum {b['datum']!r} är inte ett giltigt datum i formatet ÅÅÅÅ-MM-DD.")
        if datum is not None:
            if b["datum"] in sedda_datum:
                fel.append(f"{namn}: samma datum som begrepp {sedda_datum[b['datum']]} ({b['datum']}).")
            sedda_datum.setdefault(b["datum"], nr)
            if foregaende_datum is not None:
                vantat = foregaende_datum + dt.timedelta(days=1)
                if datum < vantat:
                    fel.append(f"{namn}: datum {datum} ligger i fel ordning, efter {foregaende_datum}.")
                elif datum > vantat:
                    fel.append(f"{namn}: lucka i kalendariet, {vantat} saknar begrepp.")
            foregaende_datum = datum

        for falt, varde in b.items():
            texter = varde if isinstance(varde, list) else [varde]
            for text in texter:
                if isinstance(text, str) and (traff := TANKSTRECK.search(text)):
                    utdrag = text[max(traff.start() - 20, 0):traff.end() + 20].replace("\n", " ")
                    fel.append(f"{namn}: tankstreck i \"{falt}\": …{utdrag}…")
    return fel


def _jamfor(fil: dict, foregaende: dict, idag: dt.date) -> list[str]:
    """Begrepp som redan har varit dagens begrepp får inte tas bort eller byta id eller datum."""
    fel: list[str] = []
    nya = [b for b in fil.get("begrepp", []) if isinstance(b, dict)]
    gamla = [b for b in foregaende.get("begrepp", []) if isinstance(b, dict)]
    nya_per_id = {b.get("id"): b for b in nya}
    nya_per_datum = {b.get("datum"): b for b in nya}

    for gammal in gamla:
        datum = las_datum(gammal.get("datum"))
        if datum is None or datum > idag:
            continue  # framtida begrepp får ändras fritt
        gid = gammal.get("id")
        if gid not in nya_per_id:
            fel.append(f"Begreppet {gid} ({datum}) har redan visats och får inte tas bort.")
        elif nya_per_id[gid].get("datum") != gammal.get("datum"):
            fel.append(f"Begreppet {gid} har redan visats och får inte byta datum "
                       f"({gammal.get('datum')} till {nya_per_id[gid].get('datum')}).")
        elif nya_per_datum.get(gammal.get("datum"), {}).get("id") != gid:
            fel.append(f"Datumet {datum} har redan visats med begreppet {gid} och får inte få ett annat id.")

    if fil.get("innehallsversion") == foregaende.get("innehallsversion") and _innehall(fil) != _innehall(foregaende):
        fel.append("Innehållet har ändrats men innehallsversion är oförändrad. Uppdatera innehallsversion.")
    return fel


def _innehall(fil: dict) -> str:
    """Allt utom innehallsversion, i en form som går att jämföra."""
    return json.dumps({k: v for k, v in fil.items() if k != "innehallsversion"}, sort_keys=True, ensure_ascii=False)


def _las_fran_git(ref: str, sokvag: str) -> dict | None:
    """Filen i en annan commit, eller None om den inte finns där (t.ex. i första commiten)."""
    resultat = subprocess.run(["git", "show", f"{ref}:{sokvag}"], capture_output=True, text=True)
    if resultat.returncode != 0:
        return None
    try:
        return json.loads(resultat.stdout)
    except json.JSONDecodeError:
        return None  # den föregående versionen var ogiltig; jämför inte


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validerar begrepp.json.")
    parser.add_argument("fil", nargs="?", default="begrepp.json")
    parser.add_argument("--foregaende", metavar="REF",
                        help="git-referens att jämföra med, t.ex. origin/main eller en commit")
    parser.add_argument("--idag", metavar="ÅÅÅÅ-MM-DD", help="dagens datum, för tester")
    args = parser.parse_args(argv)

    try:
        with open(args.fil, encoding="utf-8") as f:
            fil = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"FEL: {args.fil} är inte giltig JSON: {e}")
        return 1

    foregaende = None
    if args.foregaende:
        foregaende = _las_fran_git(args.foregaende, args.fil)
        if foregaende is None:
            print(f"Ingen tidigare version av {args.fil} i {args.foregaende}; jämförelsen hoppas över.")

    idag = las_datum(args.idag) if args.idag else None
    fel = validera(fil, foregaende, idag)
    if fel:
        print(f"{args.fil} har {len(fel)} fel:")
        for rad in fel:
            print(f"FEL: {rad}")
        return 1
    antal = len(fil["begrepp"])
    print(f"{args.fil} är godkänd: {antal} begrepp från {fil['begrepp'][0]['datum']} till "
          f"{fil['begrepp'][-1]['datum']}, innehållsversion {fil['innehallsversion']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
