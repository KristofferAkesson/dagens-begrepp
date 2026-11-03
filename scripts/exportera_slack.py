#!/usr/bin/env python3
"""Skapar kalkylarket för Slack Workflow Builder från begrepp.json.

Användning:
  python3 scripts/exportera_slack.py begrepp.json
  python3 scripts/exportera_slack.py begrepp.json --befintlig nuvarande-ark.xlsx

Med --befintlig behålls värdet i kolumnen Postad för begrepp som redan
finns i arket, så att kön i Slack fortsätter där den var.
Kräver openpyxl: pip install openpyxl
"""
import argparse
import json

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

KOLUMNER = ["Nr", "Id", "Område", "Rubrik", "Brödtext", "Exempeltyp", "Exempel",
            "Kärnan", "Termer", "Läs vidare", "Postad"]
BREDDER = [6, 14, 24, 30, 70, 18, 60, 45, 35, 40, 9]


def postad_fran(sokvag):
    ws = load_workbook(sokvag)["Begrepp"]
    rubriker = [c.value for c in ws[1]]
    i_id, i_postad = rubriker.index("Id"), rubriker.index("Postad")
    return {rad[i_id]: rad[i_postad] for rad in ws.iter_rows(min_row=2, values_only=True) if rad[i_id]}


def main():
    parser = argparse.ArgumentParser(description="Exporterar begrepp.json till kalkylark för Slack.")
    parser.add_argument("fil", help="Sökväg till begrepp.json")
    parser.add_argument("--befintlig", help="Nuvarande ark, för att behålla kolumnen Postad")
    parser.add_argument("--ut", default="dagens-begrepp-slack.xlsx", help="Filnamn för det nya arket")
    args = parser.parse_args()

    with open(args.fil, encoding="utf-8") as f:
        doc = json.load(f)
    postad = postad_fran(args.befintlig) if args.befintlig else {}

    wb = Workbook()
    ws = wb.active
    ws.title = "Begrepp"
    ws.append(KOLUMNER)
    for nr, b in enumerate(doc["begrepp"], 1):
        ws.append([
            nr, b["id"], b["omrade"], b["rubrik"], b["brodtext"],
            "Verkligt exempel" if b["exempel_typ"] == "verkligt" else "Illustrativt exempel",
            b["exempel"], b["karnan"], ", ".join(b["termer"]), ", ".join(b["las_vidare"]),
            postad.get(b["id"], "nej"),
        ])

    for i, bredd in enumerate(BREDDER, 1):
        ws.column_dimensions[get_column_letter(i)].width = bredd
    for rad in ws.iter_rows():
        for cell in rad:
            cell.font = Font(name="Arial", size=10, bold=(cell.row == 1))
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="DDE3EA")
    ws.freeze_panes = "A2"

    info = wb.create_sheet("Instruktion")
    for text in [
        "Dagens begrepp: kalkylark för Slack Workflow Builder",
        "",
        "Fliken Begrepp innehåller begreppen i den ordning de ska postas.",
        "Kolumnen Postad styr kön: arbetsflödet hämtar första raden där Postad är nej och sätter den till ja efter postning.",
        "Ändra inga kolumnrubriker, eftersom arbetsflödet hittar fälten via rubrikerna.",
        "För att börja om från början: sätt alla värden i Postad till nej.",
        f"Källa: begrepp.json, innehållsversion {doc.get('innehallsversion', 'okänd')}.",
    ]:
        info.append([text])
    info.column_dimensions["A"].width = 110
    for rad in info.iter_rows():
        for cell in rad:
            cell.font = Font(name="Arial", size=10, bold=(cell.row == 1))

    wb.save(args.ut)
    print(f"Skapade {args.ut} med {len(doc['begrepp'])} begrepp.")


if __name__ == "__main__":
    main()
