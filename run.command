#!/bin/bash
# Doppelklick in Finder (oder ./run.command im Terminal) genügt: legt bei
# Bedarf ein venv an, installiert Abhängigkeiten und startet die Extraktion.
cd "$(dirname "$0")" || exit 1

if [ ! -d venv ]; then
    python3 -m venv venv || { echo "Konnte venv nicht anlegen."; read -p "Enter zum Schliessen..." _; exit 1; }
fi
source venv/bin/activate
pip install -q -r requirements.txt || { echo "Konnte Abhaengigkeiten nicht installieren."; read -p "Enter zum Schliessen..." _; exit 1; }

python3 src/extract_required.py
status=$?
# Exit-Code 1 von extract_required.py ist ein bewusstes Signal ("Objekte mit
# fehlenden Pflichtfeldern"), kein Absturz -- Skript zeigt die Zusammenfassung
# trotzdem an, statt hier abzubrechen.

echo
read -p "Fertig. Enter zum Schliessen..." _
exit $status
