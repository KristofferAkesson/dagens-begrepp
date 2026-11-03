# Dagens begrepp: innehåll

Det här repot innehåller allt innehåll till appen Dagens begrepp. Apparna för Mac och iPhone hämtar filen `begrepp.json` härifrån, så en ändring som slås ihop till `main` når alla användare inom några minuter.

## Innehåll i repot

- `begrepp.json` är originalet för alla begrepp. Varje begrepp har ett datum då det är dagens begrepp.
- `scripts/validera.py` kontrollerar att filen följer reglerna nedan.
- `scripts/exportera_slack.py` skapar kalkylarket som Slack-flödet hämtar begreppen från.
- `.github/workflows/validera.yml` kör valideringen automatiskt vid varje ändring.

## Regler för innehållet

Valideringen stoppar en ändring om någon av reglerna bryts:

- Filen följer schema 4 och alla obligatoriska fält finns.
- Varje begrepp har ett eget id och ett eget datum.
- Kalendariet har ett begrepp per dag, utan luckor.
- `exempel_typ` är `verkligt` eller `illustrativt`.
- Ett begrepp som redan har visats tas aldrig bort och byter aldrig datum. Texten får rättas.
- `innehallsversion` uppdateras varje gång innehållet ändras.
- Inga tankstreck delar upp meningar, enligt KAN:s skrivregler.

Begrepp med framtida datum får bytas ut fritt, eftersom ingen har sett dem. Om ett sådant begrepp tas bort behöver datumen för de följande begreppen flyttas så att det inte blir en lucka.

## Lägga till nya begrepp

1. Lägg de nya begreppen sist i `begrepp.json`, med datum som fortsätter dagen efter det sista befintliga.
2. Uppdatera `innehallsversion` till dagens datum.
3. Spara ändringen i en ny gren och öppna en pull request. I GitHubs webbgränssnitt väljer du "Create a new branch and start a pull request".
4. Vänta tills kontrollen `validera` är grön. Är den röd står felen i loggen under fliken Actions.
5. Slå ihop pull requesten till `main`.

## Köra valideringen på egen dator

```
python3 scripts/validera.py begrepp.json
```

För att också kontrollera att inga visade begrepp har ändrats, jämför med föregående version:

```
git show main:begrepp.json > /tmp/forra.json
python3 scripts/validera.py begrepp.json --jamfor /tmp/forra.json
```

## Uppdatera kalkylarket för Slack

Exporten behövs bara när begrepp har lagts till eller ändrats. Ladda ner det nuvarande arket från Google Sheets som xlsx och kör:

```
pip install openpyxl
python3 scripts/exportera_slack.py begrepp.json --befintlig nuvarande-ark.xlsx
```

Det nya arket behåller värdena i kolumnen Postad, så kön i Slack fortsätter där den var. Importera filen till Google Sheets och ersätt fliken Begrepp.

## Ansvar

Innehållet faktagranskas varje halvår, med extra fokus på regelverk och AI eftersom de områdena förändras snabbast. Fältet `granskad` visar när ett begrepp senast kontrollerades.
