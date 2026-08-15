# formigas

Vorab-Aufgabe "Datenkonsolidierung Immobilienbestand": Migration der
HTML-Exposés aus `daten/` in das Zielschema `immobilien_schema.json`.
Aufgabenstellung in [aufgabe.md](aufgabe.md).

## Setup

Voraussetzung: Python 3.9+ (getestet mit 3.13). Am einfachsten per
Doppelklick auf `run.command` (macOS, Finder) — legt bei Bedarf ein `venv`
an, installiert `requirements.txt` und startet die Extraktion. Alternativ im
Terminal:

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

## Aufbau

```
.
├── aufgabe.md               Aufgabenstellung
├── immobilien_schema.json   Zielschema (JSON Schema, Draft 2020-12)
├── daten/
│   ├── standort_a/          25 HTML-Exposés, Standort A
│   └── standort_b/          25 HTML-Exposés, Standort B
├── src/
│   └── extract_required.py  Extraktions-Pipeline (Pflicht- + Zusatzfelder)
├── ergebnis/                 generiert beim Ausführen, nicht Teil des Repo-Inputs
│   ├── <objekt_id>.json     ein JSON je valides Objekt
│   ├── zu_pruefen/          Objekte mit fehlenden Pflichtfeldern
│   └── _report.json         Zusammenfassung des letzten Laufs
├── notizen/                  Notizen zu Vorgehen/Entscheidungen/Teil 2 (LaTeX)
├── images/                   Screenshots, u.a. KI-Ausschnitte
├── run.command                Start per Doppelklick
├── requirements.txt           Python-Abhängigkeiten
└── venv/                      lokal, nicht versioniert (siehe .gitignore)
```

## Abhängigkeiten

Siehe `requirements.txt`, per `pip install -r requirements.txt`:

- **`beautifulsoup4`** — HTML-Parsing der Exposés (Tabelle, Titel, Adresse,
  Freitext).
- **`jsonschema`** — validiert jedes Objekt zusätzlich gegen
  `immobilien_schema.json` (Draft 2020-12), inkl. Wertebereichen/Enums und der
  bedingten `allOf`/`if-then`-Regel (Preisfelder je nach `vermarktungsart`).
  Ersetzt nicht `Pflichtfelder.fehlende_pflichtfelder()` (die Ordner-Trennung
  `ergebnis/` vs. `zu_pruefen/` hängt weiterhin daran), sondern ergänzt sie um
  Fehler, die die eigene Logik nicht abdeckt — Ergebnis steht pro Objekt unter
  `schema_validierung`, siehe `ergebnis/_report.json` für die Übersicht.

Keine weiteren Systemabhängigkeiten (kein LLM-Zugang nötig für die aktuell
implementierten Felder, siehe Notizen zur Feldauswahl-Begründung).
