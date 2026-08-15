"""Extraktion der Pflichtfelder aus den HTML-Exposés (Standort A/B) in das Zielschema.

Pflichtfelder laut immobilien_schema.json: objekt_id, quelle, vermarktungsart,
objekttyp, adresse (plz, ort), wohnflaeche_qm, zimmer.

Strategie (siehe README für Details/Begründung):
- Titel (<h1>) ist die einzige Quelle, die in allen 50 Dateien vorkommt und
  strikt einheitlich formatiert ist ("<N>-Zimmer-<Typ> in <Ort> zu <Art>").
  Er dient als Primärquelle für zimmer/vermarktungsart/objekttyp.
- Tabelle "Eckdaten" und Freitext dienen zur Bestätigung/als Fallback und
  werden bei Abweichung als Warnung protokolliert statt still überschrieben.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATEN_DIR = ROOT / "daten"

OBJEKTTYP_MAP = {
    "Wohnung": "wohnung",
    "Haus": "haus",
    "Gewerbeflaeche": "gewerbe",
    "Grundstueck": "grundstueck",
}

TITEL_RE = re.compile(
    r"^(?P<zimmer>[\d,]+)-Zimmer-(?P<typ>[A-Za-zäöüÄÖÜß]+)\s+in\s+.+?\s+zu\s+(?P<art>verkaufen|vermieten)$"
)

ADRESSE_RE = re.compile(
    r"^(?P<strasse>.+?)\s+(?P<hausnummer>\d+[a-zA-Z]?(?:-\d+[a-zA-Z]?)?),\s*"
    r"(?P<plz>\d{5})\s+(?P<ort>[^(]+?)\s*(?:\((?P<stadtteil>[^)]+)\))?$"
)

# "Die X Zimmer verteilen sich auf zwei Ebenen" wird absichtlich NICHT aufgenommen:
# in der Stichprobe nennt dieser Satz durchgehend einen falschen Wert (Titel + 1) —
# vermutlich ein bewusst eingebauter Störsatz. Siehe Notizen zu Teil 2.
ZIMMER_TEXT_PATTERNS = [
    re.compile(r"Aufgeteilt in ([\d,]+)\s*Zimmer"),
    re.compile(r"\bZimmer:\s*([\d,]+)\."),
]


def _dezimal(text: str) -> float:
    """dt. Zahl ('4,5' / '129,00' / 'ca. 197') -> float.

    Kein Tausendertrenner in diesem Wertebereich (Fläche/Zimmer), daher reicht
    einfaches Ersetzen von Komma durch Punkt.
    """
    text = text.replace("ca.", "").strip()
    match = re.search(r"\d+(?:,\d+)?", text)
    if not match:
        raise ValueError(f"Keine Zahl gefunden in: {text!r}")
    return float(match.group(0).replace(",", "."))


@dataclass
class Extraction:
    objekt_id: Optional[str] = None
    quelle: Optional[str] = None
    vermarktungsart: Optional[str] = None
    objekttyp: Optional[str] = None
    adresse: dict = field(default_factory=dict)
    wohnflaeche_qm: Optional[float] = None
    zimmer: Optional[float] = None
    warnungen: list = field(default_factory=list)

    def fehlende_pflichtfelder(self) -> list[str]:
        fehlend = []
        for feld in ("objekt_id", "quelle", "vermarktungsart", "objekttyp", "wohnflaeche_qm", "zimmer"):
            if getattr(self, feld) is None:
                fehlend.append(feld)
        for feld in ("plz", "ort"):
            if not self.adresse.get(feld):
                fehlend.append(f"adresse.{feld}")
        return fehlend


def extrahiere_pflichtfelder(pfad: Path) -> Extraction:
    html = pfad.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    erg = Extraction()
    erg.quelle = pfad.parent.name  # Standortkennung, z.B. "standort_a"

    expose = soup.find("div", class_="expose")
    erg.objekt_id = expose.get("data-objekt-nr") if expose else None

    h1 = soup.find("h1")
    titel_text = h1.get_text(strip=True) if h1 else ""
    m = TITEL_RE.match(titel_text)
    titel_zimmer = None
    if m:
        titel_zimmer = _dezimal(m.group("zimmer"))
        erg.vermarktungsart = "kauf" if m.group("art") == "verkaufen" else "miete"
        erg.objekttyp = OBJEKTTYP_MAP.get(m.group("typ"), "sonstige")
        if m.group("typ") not in OBJEKTTYP_MAP:
            erg.warnungen.append(f"unbekannter Objekttyp im Titel: {m.group('typ')!r} -> 'sonstige'")
    else:
        erg.warnungen.append(f"Titel nicht im erwarteten Format: {titel_text!r}")

    lage = soup.find("p", class_="lage")
    lage_text = lage.get_text(" ", strip=True) if lage else ""
    am = ADRESSE_RE.match(lage_text)
    if am:
        erg.adresse = {
            "strasse": am.group("strasse") or None,
            "hausnummer": am.group("hausnummer") or None,
            "plz": am.group("plz"),
            "ort": am.group("ort").strip(),
            "stadtteil": am.group("stadtteil"),
        }
    else:
        erg.warnungen.append(f"Adresse nicht parsbar: {lage_text!r}")

    tabelle = {}
    for tr in soup.select("table.eckdaten tr"):
        th, td = tr.find("th"), tr.find("td")
        if th and td:
            tabelle[th.get_text(strip=True)] = td.get_text(" ", strip=True)

    if "Wohnflaeche" in tabelle:
        try:
            erg.wohnflaeche_qm = _dezimal(tabelle["Wohnflaeche"])
        except ValueError:
            erg.warnungen.append(f"Wohnflaeche nicht parsbar: {tabelle['Wohnflaeche']!r}")
    else:
        erg.warnungen.append("Wohnflaeche fehlt in der Eckdaten-Tabelle")

    beschreibung_text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
    kandidaten = {}
    if "Zimmer" in tabelle:
        try:
            kandidaten["tabelle"] = _dezimal(tabelle["Zimmer"])
        except ValueError:
            pass
    for pattern in ZIMMER_TEXT_PATTERNS:
        fm = pattern.search(beschreibung_text)
        if fm:
            kandidaten["freitext"] = _dezimal(fm.group(1))
            break

    if titel_zimmer is not None:
        erg.zimmer = titel_zimmer
        abweichler = {q: w for q, w in kandidaten.items() if w != titel_zimmer}
        if abweichler:
            erg.warnungen.append(f"Zimmerzahl-Konflikt: Titel={titel_zimmer}, weitere Quellen={abweichler}")
    elif kandidaten:
        erg.zimmer = kandidaten.get("tabelle", next(iter(kandidaten.values())))
        erg.warnungen.append("Zimmerzahl ohne Titel-Bestätigung übernommen (geringere Konfidenz)")

    return erg


def main() -> int:
    out_dir = ROOT / "ergebnis"
    review_dir = out_dir / "zu_pruefen"
    out_dir.mkdir(exist_ok=True)
    review_dir.mkdir(exist_ok=True)

    ergebnisse = []
    fehlerhaft = []
    for pfad in sorted(DATEN_DIR.glob("standort_*/*.html")):
        erg = extrahiere_pflichtfelder(pfad)
        fehlend = erg.fehlende_pflichtfelder()
        datensatz = asdict(erg)
        datensatz["datei"] = pfad.name
        if fehlend:
            datensatz["fehlende_pflichtfelder"] = fehlend
            fehlerhaft.append(datensatz)
        ergebnisse.append(datensatz)

        # Objekte mit fehlenden Pflichtfeldern landen sichtbar getrennt in
        # ergebnis/zu_pruefen/ statt unmarkiert neben den validen Objekten.
        dateiname = erg.objekt_id or pfad.stem
        ziel = review_dir if fehlend else out_dir
        (ziel / f"{dateiname}.json").write_text(
            json.dumps(datensatz, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    mit_warnung = [e for e in ergebnisse if e["warnungen"]]

    report = {
        "anzahl_objekte": len(ergebnisse),
        "anzahl_fehlerhaft": len(fehlerhaft),
        "anzahl_mit_warnung": len(mit_warnung),
        "fehlerhaft": [
            {"objekt_id": e["objekt_id"], "datei": e["datei"], "fehlende_pflichtfelder": e["fehlende_pflichtfelder"]}
            for e in fehlerhaft
        ],
        "warnungen": [
            {"objekt_id": e["objekt_id"], "datei": e["datei"], "warnungen": e["warnungen"]}
            for e in mit_warnung
        ],
    }
    (out_dir / "_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"{len(ergebnisse)} Objekte verarbeitet.")
    print(f"{len(fehlerhaft)} mit fehlenden Pflichtfeldern -> ergebnis/zu_pruefen/, siehe ergebnis/_report.json")
    print(f"{len(mit_warnung)} mit Warnungen (u.a. Zimmerzahl-Konflikte, Parsing-Auffälligkeiten):")
    for e in mit_warnung:
        print(f"  - {e['datei']}: {e['warnungen']}")

    return 1 if fehlerhaft else 0


if __name__ == "__main__":
    sys.exit(main())
