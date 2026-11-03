#!/usr/bin/env python3
"""Skapar kalkylarket för Slack Workflow Builder från begrepp.json.

    python3 scripts/exportera_slack.py --befintligt dagens-begrepp-slack.xlsx --ut nytt.xlsx

Arket får samma kolumner som tidigare: Nr, Id, Område, Rubrik, Brödtext, Exempeltyp,
Exempel, Kärnan, Termer, Läs vidare och Postad. Med --befintligt läses värdet i Postad
från det gamla arket för varje id, så att kön i Slack inte börjar om. Nya begrepp får
"nej". Skriptet använder bara Pythons standardbibliotek.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

KOLUMNER = ["Nr", "Id", "Område", "Rubrik", "Brödtext", "Exempeltyp", "Exempel", "Kärnan",
            "Termer", "Läs vidare", "Postad"]
BREDDER = [6, 14, 24, 30, 70, 18, 60, 45, 35, 40, 9]
EXEMPELTYP = {"verkligt": "Verkligt exempel", "illustrativt": "Illustrativt exempel"}
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def rader(fil: dict, postad: dict[str, str]) -> list[list[str]]:
    """En rad per begrepp i kalenderordning. Postad hämtas från det befintliga arket per id."""
    begrepp = sorted(fil["begrepp"], key=lambda b: b.get("datum", ""))
    return [[str(nr), b["id"], b["omrade"], b["rubrik"], b["brodtext"],
             EXEMPELTYP.get(b.get("exempel_typ", ""), ""), b["exempel"], b["karnan"],
             ", ".join(b["termer"]), ", ".join(b["las_vidare"]), postad.get(b["id"], "nej")]
            for nr, b in enumerate(begrepp, start=1)]


# MARK: - Läsa ett befintligt ark

def las_postad(sokvag: str) -> dict[str, str]:
    """Id -> värdet i Postad, från fliken Begrepp i ett befintligt ark."""
    with zipfile.ZipFile(sokvag) as z:
        delade = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(M + "si"):
                delade.append("".join(t.text or "" for t in si.iter(M + "t")))
        blad = _bladfil(z, "Begrepp")
        tabell = []
        for rad in ET.fromstring(z.read(blad)).iter(M + "row"):
            celler = {}
            for c in rad.iter(M + "c"):
                kolumn = "".join(ch for ch in c.get("r", "") if ch.isalpha())
                v = c.find(M + "v")
                if c.get("t") == "s" and v is not None:
                    celler[kolumn] = delade[int(v.text)]
                elif c.get("t") == "inlineStr":
                    celler[kolumn] = "".join(t.text or "" for t in c.iter(M + "t"))
                else:
                    celler[kolumn] = v.text if v is not None else ""
            tabell.append(celler)
    if not tabell:
        return {}
    rubriker = {namn: kolumn for kolumn, namn in tabell[0].items()}
    if "Id" not in rubriker or "Postad" not in rubriker:
        raise SystemExit("Det befintliga arket saknar kolumnerna Id och Postad.")
    return {r[rubriker["Id"]]: r.get(rubriker["Postad"], "nej") or "nej"
            for r in tabell[1:] if r.get(rubriker["Id"])}


def _bladfil(z: zipfile.ZipFile, namn: str) -> str:
    """Sökvägen till ett blad med ett visst namn, annars det första bladet."""
    arbetsbok = ET.fromstring(z.read("xl/workbook.xml"))
    relationer = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    blad = list(arbetsbok.iter(M + "sheet"))
    valt = next((b for b in blad if b.get("name") == namn), blad[0])
    mal = relationer[valt.get(R + "id")].lstrip("/")
    return mal if mal.startswith("xl/") else "xl/" + mal


# MARK: - Skriva ett nytt ark

def skriv_xlsx(sokvag: str, tabell: list[list[str]], instruktion: list[str]) -> None:
    def kolumnnamn(index: int) -> str:
        namn = ""
        index += 1
        while index:
            index, rest = divmod(index - 1, 26)
            namn = chr(65 + rest) + namn
        return namn

    def blad(rader: list[list[str]], bredder: list[int] | None, rubrikrad: bool) -> str:
        xml_rader = []
        for r, rad in enumerate(rader, start=1):
            celler = "".join(
                f'<c r="{kolumnnamn(k)}{r}" t="inlineStr"{" s=\"1\"" if rubrikrad and r == 1 else ""}>'
                f'<is><t xml:space="preserve">{escape(varde)}</t></is></c>'
                for k, varde in enumerate(rad))
            xml_rader.append(f'<row r="{r}">{celler}</row>')
        kolumner = ""
        if bredder:
            kolumner = "<cols>" + "".join(
                f'<col min="{i}" max="{i}" width="{b}" customWidth="1"/>' for i, b in enumerate(bredder, start=1)
            ) + "</cols>"
        las = ('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
               'state="frozen"/></sheetView></sheetViews>') if rubrikrad else ""
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'{las}{kolumner}<sheetData>{"".join(xml_rader)}</sheetData></worksheet>')

    filer = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            '<sheet name="Begrepp" sheetId="1" r:id="rId1"/><sheet name="Instruktion" sheetId="2" r:id="rId2"/>'
            '</sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/></Relationships>',
        "xl/styles.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
            '</styleSheet>',
        "xl/worksheets/sheet1.xml": blad([KOLUMNER] + tabell, BREDDER, rubrikrad=True),
        "xl/worksheets/sheet2.xml": blad([[rad] for rad in instruktion], [100], rubrikrad=False),
    }
    with zipfile.ZipFile(sokvag, "w", zipfile.ZIP_DEFLATED) as z:
        for namn, innehall in filer.items():
            z.writestr(namn, innehall)


def instruktion(fil: dict, antal: int, overforda: bool, idag: dt.date) -> list[str]:
    kalla = (f"Källa: begrepp.json, schema {fil.get('schema_version')}, innehållsversion "
             f"{fil.get('innehallsversion')}, exporterad {idag.isoformat()}.")
    if overforda:
        kalla += " Postad är överförd från föregående version per id."
    return [
        "Dagens begrepp: kalkylark för Slack Workflow Builder",
        "",
        f"Fliken Begrepp innehåller {antal} begrepp i den ordning de ska postas.",
        "Kolumnen Postad styr kön: arbetsflödet hämtar första raden där Postad är nej och sätter den "
        "till ja efter postning.",
        "Ändra inga kolumnrubriker, eftersom arbetsflödet hittar fälten via rubrikerna.",
        "För att börja om från början: sätt alla värden i Postad till nej.",
        kalla,
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skapar kalkylarket för Slack Workflow Builder.")
    parser.add_argument("--fil", default="begrepp.json", help="innehållsfilen (standard: begrepp.json)")
    parser.add_argument("--befintligt", metavar="XLSX", help="befintligt ark att hämta Postad från")
    parser.add_argument("--ut", required=True, metavar="XLSX", help="det nya arket")
    args = parser.parse_args(argv)

    with open(args.fil, encoding="utf-8") as f:
        fil = json.load(f)
    postad = las_postad(args.befintligt) if args.befintligt else {}
    tabell = rader(fil, postad)
    skriv_xlsx(args.ut, tabell, instruktion(fil, len(tabell), bool(args.befintligt), dt.date.today()))

    antal_postade = sum(1 for rad in tabell if rad[-1] == "ja")
    print(f"Skrev {args.ut}: {len(tabell)} begrepp, varav {antal_postade} redan postade.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
