# formigas
skill-check aufgabe

## Ausführen

Am einfachsten per Doppelklick auf `run.command` (macOS, Finder) — legt bei
Bedarf ein `venv` an, installiert `requirements.txt` und startet die
Extraktion. Alternativ im Terminal:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 src/extract_required.py
```

Ergebnis landet in `ergebnis/` (valide Objekte) bzw. `ergebnis/zu_pruefen/`
(Objekte mit fehlenden Pflichtfeldern), plus `ergebnis/_report.json` als
Zusammenfassung. Exit-Code ist `1`, wenn mindestens ein Objekt fehlende
Pflichtfelder hat — für CI-Anbindung gedacht.
