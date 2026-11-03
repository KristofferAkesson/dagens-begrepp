"""Tester för validera.py och exportera_slack.py. Körs med:

    python3 -m unittest discover scripts
"""

import copy
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import exportera_slack  # noqa: E402
from validera import validera  # noqa: E402

IDAG = dt.date(2026, 11, 5)


def begrepp(nr: int, datum: str) -> dict:
    return {"id": f"2026-q4-{nr:03d}", "datum": datum, "omrade": "Strategi och affär", "rubrik": f"Rubrik {nr}",
            "brodtext": "Brödtext.", "exempel": "Exempel.", "exempel_typ": "illustrativt", "karnan": "Kärnan.",
            "termer": ["term"], "las_vidare": ["sökord"], "period": "Månad 1", "granskad": "2026-10-17"}


def fil(antal: int = 5, start: dt.date = dt.date(2026, 11, 3)) -> dict:
    return {"app": "Dagens begrepp", "schema_version": 4, "innehallsversion": "2026-11-03",
            "begrepp": [begrepp(i + 1, (start + dt.timedelta(days=i)).isoformat()) for i in range(antal)]}


class ValideraTests(unittest.TestCase):
    def assertFel(self, data, text, foregaende=None):
        fel = validera(data, foregaende, IDAG)
        self.assertTrue(any(text in f for f in fel), f"Väntade fel med {text!r}, fick {fel}")

    def test_giltig_fil_godkanns(self):
        self.assertEqual(validera(fil(), None, IDAG), [])

    def test_medfoljande_fil_godkanns(self):
        import json
        sokvag = os.path.join(os.path.dirname(__file__), "..", "begrepp.json")
        with open(sokvag, encoding="utf-8") as f:
            self.assertEqual(validera(json.load(f), None, IDAG), [])

    def test_fel_schemaversion(self):
        data = fil()
        data["schema_version"] = 3
        self.assertFel(data, "schema_version ska vara 4")

    def test_saknad_innehallsversion(self):
        data = fil()
        del data["innehallsversion"]
        self.assertFel(data, "innehallsversion")

    def test_innehallsversion_med_lopnummer(self):
        for version in ["2026-11-03.2", "2026-11-03.9"]:
            data = fil()
            data["innehallsversion"] = version
            self.assertEqual(validera(data, None, IDAG), [], version)
        for version in ["2026-11-03.1", "2026-11-03.10", "2026-11-03b", "3 november"]:
            data = fil()
            data["innehallsversion"] = version
            self.assertFel(data, "innehallsversion ska vara")

    def test_samma_id(self):
        data = fil()
        data["begrepp"][2]["id"] = data["begrepp"][0]["id"]
        self.assertFel(data, "samma id som begrepp 1")

    def test_samma_datum(self):
        data = fil()
        data["begrepp"][1]["datum"] = data["begrepp"][0]["datum"]
        self.assertFel(data, "samma datum som begrepp 1")

    def test_tomt_och_saknat_falt(self):
        data = fil()
        data["begrepp"][0]["karnan"] = "  "
        del data["begrepp"][1]["rubrik"]
        data["begrepp"][2]["termer"] = []
        self.assertFel(data, "\"karnan\" saknas eller är tomt")
        self.assertFel(data, "\"rubrik\" saknas eller är tomt")
        self.assertFel(data, "\"termer\" ska vara en lista")

    def test_okand_exempeltyp(self):
        data = fil()
        data["begrepp"][0]["exempel_typ"] = "påhittat"
        self.assertFel(data, "exempel_typ ska vara verkligt eller illustrativt")

    def test_ogiltigt_datum(self):
        data = fil()
        data["begrepp"][0]["datum"] = "2026-02-30"
        self.assertFel(data, "inte ett giltigt datum")

    def test_lucka_i_datum(self):
        data = fil()
        data["begrepp"][3]["datum"] = "2026-11-08"
        data["begrepp"][4]["datum"] = "2026-11-09"
        self.assertFel(data, "lucka i kalendariet, 2026-11-06 saknar begrepp")

    def test_fel_ordning(self):
        data = fil()
        data["begrepp"][1], data["begrepp"][2] = data["begrepp"][2], data["begrepp"][1]
        self.assertFel(data, "fel ordning")

    def test_tankstreck(self):
        for text in ["Det är viktigt – men svårt.", "Det är viktigt — men svårt.", "Det är viktigt - men svårt.",
                     "Ett ord–ord."]:
            data = fil()
            data["begrepp"][0]["brodtext"] = text
            self.assertFel(data, "tankstreck i \"brodtext\"")

    def test_intervall_och_bindestreck_ar_tillatna(self):
        data = fil()
        data["begrepp"][0]["brodtext"] = "Svar 0–6 och 9–10 i B2B-försäljning."
        self.assertEqual(validera(data, None, IDAG), [])

    # Jämförelse med föregående version

    def test_visat_begrepp_far_inte_tas_bort(self):
        gammal = fil()
        ny = copy.deepcopy(gammal)
        del ny["begrepp"][1]
        for b, d in zip(ny["begrepp"][1:], ["2026-11-04", "2026-11-05", "2026-11-06"]):
            b["datum"] = d
        ny["innehallsversion"] = "2026-11-04"
        self.assertFel(ny, "2026-q4-002 (2026-11-04) har redan visats och får inte tas bort", gammal)

    def test_visat_begrepp_far_inte_byta_id(self):
        gammal = fil()
        ny = copy.deepcopy(gammal)
        ny["begrepp"][0]["id"] = "2026-q4-999"
        ny["innehallsversion"] = "2026-11-04"
        self.assertFel(ny, "2026-q4-001 (2026-11-03) har redan visats", gammal)

    def test_visat_begrepp_far_inte_byta_datum(self):
        gammal = fil()
        ny = copy.deepcopy(gammal)
        ny["begrepp"][0]["id"], ny["begrepp"][1]["id"] = ny["begrepp"][1]["id"], ny["begrepp"][0]["id"]
        ny["innehallsversion"] = "2026-11-04"
        self.assertFel(ny, "får inte byta datum", gammal)

    def test_dagens_begrepp_raknas_som_visat(self):
        gammal = fil()
        ny = copy.deepcopy(gammal)
        ny["begrepp"][2]["id"] = "2026-q4-ny"  # 2026-11-05 är idag
        ny["innehallsversion"] = "2026-11-04"
        self.assertFel(ny, "2026-q4-003", gammal)

    def test_textrattelse_i_visat_begrepp_ar_tillaten(self):
        gammal = fil()
        ny = copy.deepcopy(gammal)
        ny["begrepp"][0]["brodtext"] = "Rättad brödtext."
        ny["innehallsversion"] = "2026-11-04"
        self.assertEqual(validera(ny, gammal, IDAG), [])

    def test_framtida_begrepp_far_bytas_ut_och_tas_bort(self):
        gammal = fil()
        ny = copy.deepcopy(gammal)
        ny["begrepp"][3]["id"] = "2026-q4-ersattare"
        del ny["begrepp"][4]
        ny["innehallsversion"] = "2026-11-04"
        self.assertEqual(validera(ny, gammal, IDAG), [])

    def test_nya_begrepp_sist_ar_tillatna(self):
        gammal = fil()
        ny = fil(antal=7)
        ny["innehallsversion"] = "2026-11-04"
        self.assertEqual(validera(ny, gammal, IDAG), [])

    def test_andrat_innehall_kraver_ny_innehallsversion(self):
        gammal = fil()
        ny = copy.deepcopy(gammal)
        ny["begrepp"][4]["rubrik"] = "Ny rubrik"
        self.assertFel(ny, "innehallsversion är oförändrad", gammal)

    def test_oforandrad_fil_ar_godkand(self):
        self.assertEqual(validera(fil(), fil(), IDAG), [])


class ExporteraSlackTests(unittest.TestCase):
    def test_postad_overfors_per_id_och_nya_far_nej(self):
        with tempfile.TemporaryDirectory() as mapp:
            gammalt = os.path.join(mapp, "gammalt.xlsx")
            nytt = os.path.join(mapp, "nytt.xlsx")
            tabell = exportera_slack.rader(fil(3), {})
            tabell[0][-1] = "ja"
            exportera_slack.skriv_xlsx(gammalt, tabell, ["Instruktion"])

            data = fil(5)
            data["begrepp"][1]["id"] = "2026-q4-ersattare"
            exportera_slack.main(["--fil", self._skriv(mapp, data), "--befintligt", gammalt, "--ut", nytt])

            postad = exportera_slack.las_postad(nytt)
            self.assertEqual(postad, {"2026-q4-001": "ja", "2026-q4-ersattare": "nej", "2026-q4-003": "nej",
                                      "2026-q4-004": "nej", "2026-q4-005": "nej"})

    def test_samma_kolumner_som_tidigare(self):
        rad = exportera_slack.rader(fil(1), {})[0]
        self.assertEqual(len(rad), len(exportera_slack.KOLUMNER))
        self.assertEqual(rad[0], "1")
        self.assertEqual(rad[5], "Illustrativt exempel")
        self.assertEqual(rad[-1], "nej")

    @staticmethod
    def _skriv(mapp: str, data: dict) -> str:
        import json
        sokvag = os.path.join(mapp, "begrepp.json")
        with open(sokvag, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return sokvag


if __name__ == "__main__":
    unittest.main()
