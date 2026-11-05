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
import posta_slack  # noqa: E402
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


class PostaSlackTests(unittest.TestCase):
    def test_dagens_begrepp_efter_datum(self):
        data = fil(5)
        self.assertEqual(posta_slack.dagens_begrepp(data, dt.date(2026, 11, 5))["id"], "2026-q4-003")

    def test_inget_begrepp_en_dag_utan_datum(self):
        self.assertIsNone(posta_slack.dagens_begrepp(fil(5), dt.date(2026, 11, 20)))
        self.assertIsNone(posta_slack.dagens_begrepp(fil(5), dt.date(2026, 11, 2)))

    def test_meddelandet_har_kortens_delar(self):
        b = begrepp(1, "2026-11-03")
        b["brodtext"] = "Pris & värde <i> fokus."
        data = posta_slack.meddelande(b, dt.date(2026, 11, 3))
        text = json_text(data)
        self.assertEqual(data["text"], "Dagens begrepp: Rubrik 1")
        self.assertEqual(data["blocks"][0]["text"]["text"], "Rubrik 1")
        self.assertIn("Strategi och affär · Tisdag 3 november", text)
        self.assertIn("Pris &amp; värde &lt;i&gt; fokus.", text)
        self.assertIn("*Illustrativt exempel*", text)
        self.assertIn("*Kärnan:* Kärnan.", text)
        self.assertIn("*Nyckelord:* term", text)
        self.assertIn("*Läs vidare:* <https://www.google.com/search?q=s%C3%B6kord|sökord>", text)

    def test_las_vidare_blir_google_sokningar(self):
        self.assertEqual(posta_slack.sokning("Byron Sharp How Brands Grow"),
                         "<https://www.google.com/search?q=Byron+Sharp+How+Brands+Grow|Byron Sharp How Brands Grow>")
        # Tecken som Slack tolkar escapas i texten och kodas i adressen.
        self.assertEqual(posta_slack.sokning("A&B <test>"),
                         "<https://www.google.com/search?q=A%26B+%3Ctest%3E|A&amp;B &lt;test&gt;>")

    def test_prova_postar_inte(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as mapp:
            sokvag = ExporteraSlackTests._skriv(mapp, fil(3))
            utdata = io.StringIO()
            with contextlib.redirect_stdout(utdata):
                kod = posta_slack.main(["--fil", sokvag, "--datum", "2026-11-04", "--prova"])
            self.assertEqual(kod, 0)
            self.assertIn("Rubrik 2", utdata.getvalue())

    def test_utan_webhook_ar_det_ett_fel(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as mapp:
            sokvag = ExporteraSlackTests._skriv(mapp, fil(3))
            gammal = os.environ.pop("SLACK_WEBHOOK_URL", None)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(posta_slack.main(["--fil", sokvag, "--datum", "2026-11-04"]), 1)
            finally:
                if gammal is not None:
                    os.environ["SLACK_WEBHOOK_URL"] = gammal


class PostningstidTests(unittest.TestCase):
    """Två scheman i UTC, "30 7 * * *" och "30 8 * * *", men postning bara 09.30 svensk tid."""
    SOMMAR = "30 7 * * *"
    VINTER = "30 8 * * *"

    @staticmethod
    def klockan(datum: str, timme: int = 6, minut: int = 0) -> dt.datetime:
        return dt.datetime.fromisoformat(datum).replace(hour=timme, minute=minut, tzinfo=dt.timezone.utc)

    def test_sommartid_postar_0730_utc(self):
        nu = self.klockan("2027-07-01")
        self.assertTrue(posta_slack.ska_posta(self.SOMMAR, nu))
        self.assertFalse(posta_slack.ska_posta(self.VINTER, nu))
        self.assertEqual(posta_slack.schemalagd_tid(self.SOMMAR, nu).strftime("%H.%M"), "09.30")

    def test_vintertid_postar_0830_utc(self):
        nu = self.klockan("2027-01-15")
        self.assertFalse(posta_slack.ska_posta(self.SOMMAR, nu))
        self.assertTrue(posta_slack.ska_posta(self.VINTER, nu))
        self.assertEqual(posta_slack.schemalagd_tid(self.VINTER, nu).strftime("%H.%M"), "09.30")

    def test_dagen_sommartiden_borjar(self):
        # 28 mars 2027 ställs klockan fram klockan 02.00 svensk tid (01.00 UTC).
        self.assertTrue(posta_slack.ska_posta(self.VINTER, self.klockan("2027-03-27")))
        self.assertTrue(posta_slack.ska_posta(self.SOMMAR, self.klockan("2027-03-28")))
        self.assertFalse(posta_slack.ska_posta(self.VINTER, self.klockan("2027-03-28")))

    def test_dagen_sommartiden_slutar(self):
        # 25 oktober 2026 ställs klockan tillbaka klockan 03.00 svensk tid (01.00 UTC).
        self.assertTrue(posta_slack.ska_posta(self.SOMMAR, self.klockan("2026-10-24")))
        self.assertTrue(posta_slack.ska_posta(self.VINTER, self.klockan("2026-10-25")))
        self.assertFalse(posta_slack.ska_posta(self.SOMMAR, self.klockan("2026-10-25")))

    def test_exakt_en_postning_varje_dag_i_tva_ar(self):
        dag = dt.date(2026, 11, 5)
        while dag < dt.date(2028, 11, 5):
            nu = self.klockan(dag.isoformat())
            antal = sum(posta_slack.ska_posta(schema, nu) for schema in (self.SOMMAR, self.VINTER))
            self.assertEqual(antal, 1, f"{dag}: {antal} postningar")
            dag += dt.timedelta(days=1)

    def test_sen_korning_raknas_fran_schemat(self):
        # GitHub startade sommarkörningen en dryg timme sent; den ska ändå posta, en gång.
        sen = self.klockan("2027-07-01", timme=8, minut=40)
        self.assertTrue(posta_slack.ska_posta(self.SOMMAR, sen))
        self.assertFalse(posta_slack.ska_posta(self.VINTER, sen))

    def test_andra_scheman_postar_inte(self):
        nu = self.klockan("2027-07-01")
        for schema in ["0 4 1 * *", "30 7 * * 1-5", "", "trasigt"]:
            self.assertFalse(posta_slack.ska_posta(schema, nu), schema)

    def test_fel_schema_postar_inget_och_ar_inget_fel(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as mapp:
            sokvag = ExporteraSlackTests._skriv(mapp, fil(5))
            gammal = os.environ.pop("SLACK_WEBHOOK_URL", None)
            utdata = io.StringIO()
            try:
                with contextlib.redirect_stdout(utdata):
                    kod = posta_slack.main(["--fil", sokvag, "--schema", self.SOMMAR],
                                           nu=self.klockan("2026-11-05", timme=7, minut=31))
            finally:
                if gammal is not None:
                    os.environ["SLACK_WEBHOOK_URL"] = gammal
            self.assertEqual(kod, 0)
            self.assertIn("motsvarar 08.30 svensk tid i dag, inte 09.30", utdata.getvalue())

    def test_ratt_schema_valjer_dagens_begrepp_i_svensk_tid(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as mapp:
            sokvag = ExporteraSlackTests._skriv(mapp, fil(5))
            utdata = io.StringIO()
            with contextlib.redirect_stdout(utdata):
                kod = posta_slack.main(["--fil", sokvag, "--schema", self.VINTER, "--prova"],
                                       nu=self.klockan("2026-11-05", timme=8, minut=32))
            self.assertEqual(kod, 0)
            self.assertIn("Rubrik 3", utdata.getvalue())  # 5 november är det tredje begreppet

    def test_manuell_korning_utan_schema_postar_som_forut(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as mapp:
            sokvag = ExporteraSlackTests._skriv(mapp, fil(5))
            utdata = io.StringIO()
            with contextlib.redirect_stdout(utdata):
                kod = posta_slack.main(["--fil", sokvag, "--prova"], nu=self.klockan("2026-11-04", timme=14))
            self.assertEqual(kod, 0)
            self.assertIn("Rubrik 2", utdata.getvalue())


def json_text(data: dict) -> str:
    import json
    return json.dumps(data, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
