# Dagens begrepp: innehåll

Här finns allt innehåll till appen Dagens begrepp för Mac och iPhone. Filen `begrepp.json` är originalet. Apparna hämtar den härifrån, så en ändring som har gått igenom valideringen når alla användare inom några minuter, utan att apparna behöver uppdateras.

Appens kod ligger i ett eget repo.

## Filer

| Fil | Innehåll |
| --- | --- |
| `begrepp.json` | Alla begrepp, ett per dag, i datumordning. |
| `scripts/validera.py` | Kontrollerar filen. Körs automatiskt vid varje ändring. |
| `scripts/posta_slack.py` | Postar dagens begrepp i Slack-kanalen. Körs klockan 09.30 varje dag av GitHub. |
| `scripts/exportera_slack.py` | Skapar kalkylarket för det äldre Slack-flödet i Workflow Builder. |
| `scripts/test_skript.py` | Tester för de två skripten. |
| `.github/workflows/validera.yml` | Kör testerna och valideringen på GitHub. |
| `.github/workflows/slack.yml` | Postar dagens begrepp i Slack klockan 09.30 och håller sig självt aktivt. |

## Så fungerar kalendariet

Varje begrepp har ett `datum`. Begreppet med dagens datum är dagens begrepp, för alla användare samtidigt. Kalendariet startade 2026-11-03 och har ett begrepp för varje dag, även helger.

Ett begrepp ser ut så här:

```json
{
  "id": "2026-q4-001",
  "datum": "2026-11-03",
  "omrade": "Varumärke och tillväxt",
  "rubrik": "Mental availability",
  "brodtext": "…",
  "exempel": "…",
  "exempel_typ": "illustrativt",
  "karnan": "…",
  "termer": ["…"],
  "las_vidare": ["…"],
  "period": "Månad 1",
  "granskad": "2026-10-17"
}
```

Överst i filen finns `schema_version` (alltid 4) och `innehallsversion`, ett datum som ändras vid varje publicering. Publiceras filen flera gånger samma dag läggs ett löpnummer till: `2026-11-03.2`, `2026-11-03.3` och så vidare upp till `.9`. Apparna använder versionen för att avgöra vilken fil som är nyast.

## Regler

Valideringen stoppar en ändring om något av följande gäller:

1. Filen är inte giltig JSON eller följer inte schema 4.
2. Två begrepp har samma id eller samma datum.
3. Ett fält saknas eller är tomt. `exempel_typ` måste vara `verkligt` eller `illustrativt`.
4. Datumen har luckor eller ligger i fel ordning.
5. Ett begrepp vars datum har kommit har tagits bort eller fått nytt id eller nytt datum. Det gäller även dagens begrepp. Rättelser av texten är tillåtna.
6. Innehållet har ändrats men `innehallsversion` är densamma som förut.
7. En text innehåller tankstreck som delar upp meningar (KAN:s skrivregler). Tankstreck i intervall, som 0–6, är tillåtna.

Begrepp med datum i framtiden får bytas ut eller tas bort fritt, eftersom ingen har sett dem än. Tänk då på att datumen fortfarande ska följa på varandra utan luckor.

## Lägga till nya begrepp

1. Lägg de nya begreppen sist i `begrepp.json`, med datum som fortsätter dagen efter det sista befintliga.
2. Ändra `innehallsversion` till dagens datum, eller lägg till ett löpnummer om filen redan har publicerats i dag.
3. Spara ändringen i repot, via GitHubs webbgränssnitt, GitHub Desktop eller Claude Code. Gör det gärna som en pull request.
4. Valideringen körs automatiskt. Är den grön kan ändringen gå in i `main`, och då når innehållet apparna inom några minuter.
5. Slack följer med automatiskt: kanalen får varje dags begrepp från samma fil.

Rätta en text på samma sätt: ändra texten, uppdatera `innehallsversion` och spara.

## Köra skripten själv

Skripten behöver bara Python 3.9 eller senare, inga andra paket.

Validera filen:

```sh
python3 scripts/validera.py begrepp.json
```

Validera och jämför med versionen på `main`, som GitHub gör:

```sh
git fetch
python3 scripts/validera.py begrepp.json --foregaende origin/main
```

Kör testerna för skripten:

```sh
python3 -m unittest discover scripts
```

## Slack

Varje dag klockan 09.30 svensk tid, både sommar och vinter, postar GitHub dagens begrepp i Slack-kanalen. Det är begreppet med dagens datum i `begrepp.json`, samma som i apparna, så Slack och apparna visar alltid samma begrepp samma dag. En dag utan begrepp postas ingenting.

### Klockslaget

GitHub anger scheman i UTC och känner inte till sommartid. Arbetsflödet körs därför två gånger varje morgon, 07.30 UTC och 08.30 UTC. Skriptet får veta vilket schema som startade körningen och postar bara när det motsvarar 09.30 i Stockholm den dagen: 07.30 UTC på sommaren och 08.30 UTC på vintern. Den andra körningen avslutas utan att posta. På så sätt postas begreppet en gång per dag, även de dagar klockan ställs om.

GitHub kan starta schemalagda körningar några minuter sent, ibland mer när det är mycket trafik. Skriptet räknar från schemat och inte från när körningen startade, så en sen körning postar ändå rätt begrepp, bara lite senare.

### Arbetsflödet hålls aktivt

GitHub stänger av schemalagda arbetsflöden i publika repon efter 60 dagar utan aktivitet i repot. För att postningen inte ska tystna när ingen har ändrat något på ett tag har arbetsflödet ett tredje schema, den första varje månad klockan 04.00 UTC. Då kör jobbet **hall-aktivt**, som återaktiverar arbetsflödet via GitHubs API. Det är samma metod som det spridda verktyget keepalive-workflow använder för att hålla schemalagda arbetsflöden igång. GitHubs dokumentation beskriver inte uttryckligen att en återaktivering nollställer räkningen, så håll ett öga på fliken Actions de första månaderna. Jobbet behöver ingen hemlighet; det använder repots egen token med behörighet att hantera arbetsflöden.

Skulle arbetsflödet ändå ha stängts av syns det under fliken Actions. Välj **Posta i Slack** och **Enable workflow**.

Meddelandet har rubrik, område och datum, förklaringen, exemplet, Kärnan, nyckelord och läs vidare.

### Inställning, en gång

1. Skapa en inkommande webhook till kanalen i Slack (en Slack-app med Incoming Webhooks). Det kräver behörighet att lägga till appar i arbetsytan.
2. Lägg webbadressen som hemlighet i repot: Settings › Secrets and variables › Actions › New repository secret, med namnet `SLACK_WEBHOOK_URL`.
3. Stäng av det gamla flödet i Workflow Builder, så att begreppet inte postas två gånger.

### Prova

Under fliken Actions, välj **Posta i Slack** och **Run workflow**. En manuell körning postar direkt, oavsett klockslag. Med rutan "Visa meddelandet i loggen utan att posta" ikryssad syns meddelandet bara i loggen. Det går också att välja en annan dag.

På egen dator:

```sh
python3 scripts/posta_slack.py --prova
python3 scripts/posta_slack.py --datum 2026-11-10 --prova
python3 scripts/posta_slack.py --schema "30 8 * * *" --prova
```

Den sista visar vad den schemalagda körningen 08.30 UTC skulle göra i dag.

## Exportera till Slack-arket (äldre flöde)

Behövs bara om kanalen fortfarande använder flödet i Workflow Builder i stället för postningen ovan.

Slack Workflow Builder postar begreppen från ett kalkylark i Google Sheets. Kolumnen Postad håller reda på vilka som redan har postats. Exporten behåller Postad för begrepp som redan finns i arket, så att kön inte börjar om.

1. Ladda ner det nuvarande arket från Google Sheets som xlsx.
2. Kör:

   ```sh
   python3 scripts/exportera_slack.py --befintligt nedladdat.xlsx --ut dagens-begrepp-slack.xlsx
   ```

3. Importera `dagens-begrepp-slack.xlsx` i Google Sheets och ersätt det gamla arket. Ändra inga kolumnrubriker.

Utan `--befintligt` får alla begrepp Postad = nej.

## Skyddsregel på main

Ändringar i `main` ska kräva att valideringen har gått igenom. Det ställs in en gång i GitHub:

1. Settings › Branches › Add branch ruleset (eller Add rule).
2. Gäller grenen `main`.
3. Slå på Require status checks to pass och välj kontrollen **validera**.
4. Slå gärna på Require a pull request before merging.

## Ansvar

Den som ansvarar för innehållet ser till att fakta stämmer. Begrepp om regelverk och AI faktagranskas varje halvår, och datumet för senaste granskningen står i `granskad`.
