"""Extraktion aus den HTML-Exposés (Standort A/B) in Richtung Zielschema.

Zwei getrennte Bereiche pro Objekt, auch getrennt im Output:

- Pflichtfelder laut immobilien_schema.json: objekt_id, quelle, vermarktungsart,
  objekttyp, adresse (plz, ort), wohnflaeche_qm, zimmer. Diese muessen belastbar
  sein (siehe Aufgabenstellung) und bestimmen, ob ein Objekt in ergebnis/ oder
  ergebnis/zu_pruefen/ landet.
- Zusatzfelder: nicht global 'required', aber fuer eine SQL-Migration mit
  hohem Geschaeftswert eingeschaetzt (Preise, Baujahr, Energieausweis, Zustand,
  Heizungsart, Verfuegbarkeit, Provisionsfrei). Fehlen hier fuehrt nur zu einer
  Warnung, nie zur Verschiebung nach zu_pruefen/.

Strategie fuer die Pflichtfelder (siehe README fuer Details/Begruendung):
- Titel (<h1>) ist die einzige Quelle, die in allen 50 Dateien vorkommt und
  strikt einheitlich formatiert ist ("<N>-Zimmer-<Typ> in <Ort> zu <Art>").
  Er dient als Primaerquelle fuer zimmer/vermarktungsart/objekttyp.
- Tabelle "Eckdaten" und Freitext dienen zur Bestaetigung/als Fallback und
  werden bei Abweichung als Warnung protokolliert statt still ueberschrieben.

Strategie fuer die Zusatzfelder:
- zustand/heizungsart sehen wie Freitext aus, sind in den Daten aber ein
  geschlossenes Vokabular aus wenigen Phrasen -> Dictionary-Mapping statt LLM.
- Preisfelder folgen festen Satzschablonen und lassen sich arithmetisch
  cross-validieren (Kaltmiete + Nebenkosten == Warmmiete).
- Ein Satz wie "Der Preis von X EUR ist nach Absprache verhandelbar" wird
  absichtlich NICHT geparst: der Betrag passt in der Stichprobe zu keinem der
  anderen Felder (vermutlicher Stoersatz).
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

# ============================================================
# Pflichtfelder
# ============================================================

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
# vermutlich ein bewusst eingebauter Stoersatz. Siehe Notizen zu Teil 2.
ZIMMER_TEXT_PATTERNS = [
    re.compile(r"Aufgeteilt in ([\d,]+)\s*Zimmer"),
    re.compile(r"\bZimmer:\s*([\d,]+)\."),
]


def _dezimal(text: str) -> float:
    """dt. Zahl ('4,5' / '129,00' / 'ca. 197') -> float.

    Kein Tausendertrenner in diesem Wertebereich (Flaeche/Zimmer/Baujahr),
    daher reicht einfaches Ersetzen von Komma durch Punkt. Fuer Geldbetraege
    (die einen Tausenderpunkt haben koennen) siehe _euro().
    """
    text = text.replace("ca.", "").strip()
    match = re.search(r"\d+(?:,\d+)?", text)
    if not match:
        raise ValueError(f"Keine Zahl gefunden in: {text!r}")
    return float(match.group(0).replace(",", "."))


def _euro(text: str) -> float:
    """dt. Geldbetrag ('893000 EUR' / '1.466.000 €' / '244.000,00 EUR' /
    'VB 843.000 €') -> float. Anders als _dezimal() muss hier ein
    Tausenderpunkt von einem Dezimalkomma unterschieden werden.
    """
    text = text.replace("VB", "").strip()
    match = re.search(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?", text)
    if not match:
        raise ValueError(f"Kein Geldbetrag gefunden in: {text!r}")
    zahl = match.group(0)
    if "." in zahl and "," in zahl:
        zahl = zahl.replace(".", "").replace(",", ".")
    elif "." in zahl:
        zahl = zahl.replace(".", "")
    else:
        zahl = zahl.replace(",", ".")
    return float(zahl)


@dataclass
class Pflichtfelder:
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


def _parse_html(pfad: Path) -> tuple[BeautifulSoup, dict, str]:
    html = pfad.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    tabelle = {}
    for tr in soup.select("table.eckdaten tr"):
        th, td = tr.find("th"), tr.find("td")
        if th and td:
            tabelle[th.get_text(strip=True)] = td.get_text(" ", strip=True)
    beschreibung_text = " ".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
    return soup, tabelle, beschreibung_text


def extrahiere_pflichtfelder(pfad: Path, soup: BeautifulSoup, tabelle: dict, beschreibung_text: str) -> Pflichtfelder:
    erg = Pflichtfelder()
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

    if "Wohnflaeche" in tabelle:
        try:
            erg.wohnflaeche_qm = _dezimal(tabelle["Wohnflaeche"])
        except ValueError:
            erg.warnungen.append(f"Wohnflaeche nicht parsbar: {tabelle['Wohnflaeche']!r}")
    else:
        erg.warnungen.append("Wohnflaeche fehlt in der Eckdaten-Tabelle")

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


# ============================================================
# Zusatzfelder (nicht 'required', aber fuer SQL-Migration priorisiert)
# ============================================================

# zustand/heizungsart: geschlossenes Vokabular, keine echte Textvarianz.
# Werte je einmal aus der Tabellenspalte und einmal aus dem identischen
# Freitextbaustein beobachtet ("Zustand ist als X zu bezeichnen." /
# "Beheizt wird ueber X.") -> ein gemeinsames Mapping deckt beide Quellen ab.
ZUSTAND_MAP = {
    "erstbezug": "erstbezug",
    "neubau, erstbezug": "erstbezug",
    "wie neu": "neuwertig",
    "neuwertig": "neuwertig",
    "gepflegt": "gepflegt",
    "gepflegter zustand": "gepflegt",
    "guter zustand": "gepflegt",
    "kernsaniert": "saniert",
    "saniert": "saniert",
    "vollstaendig modernisiert": "saniert",
    "modernisierungsstau": "renovierungsbeduerftig",
    "renovierungsbeduerftig": "renovierungsbeduerftig",
}

HEIZUNG_MAP = {
    "gas-brennwertheizung": "gas",
    "gas-etagenheizung": "gas",
    "gasheizung": "gas",
    "gaszentralheizung": "gas",
    "oelheizung": "oel",
    "oel-zentralheizung": "oel",
    "fernwaerme": "fernwaerme",
    "fernwaermeanschluss": "fernwaerme",
    "erdwaermepumpe": "waermepumpe",
    "luft-waerme-pumpe": "waermepumpe",
    "elektroheizung": "elektro",
    "pelletheizung": "pellets",
    "holzpelletkessel": "pellets",
    "blockheizkraftwerk": "sonstige",
    "nachtspeicheroefen": "sonstige",
    "kachelofen mit zusatzheizung": "sonstige",
}

MONAT_MAP = {
    "januar": 1, "februar": 2, "maerz": 3, "märz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
}

ZUSTAND_FREITEXT_RE = re.compile(r"Zustand ist als ([^.]*?) zu bezeichnen")
HEIZUNG_FREITEXT_RE = re.compile(r"Beheizt wird ueber ([^.]*)\.")

# zwei Formulierungen fuer Baujahr beobachtet: "Baujahr 1972." (bzw. Tabelle)
# und "... stammt aus dem Jahr 1972 und wurde 2013 umfassend kernsaniert."
# Die vage Formulierung "Anfang der 2000er Jahre" wird bewusst NICHT erfasst:
# in mindestens einem Fall widerspricht sie einer bereits vorhandenen exakten
# Tabellenangabe -> ungenaue Quelle, hat gegenueber exakten Quellen nie Vorrang.
BAUJAHR_FREITEXT_PATTERNS = [
    re.compile(r"Baujahr:?\s*(\d{4})"),
    re.compile(r"stammt aus dem Jahr (\d{4})"),
]
SANIERUNG_FREITEXT_PATTERNS = [
    re.compile(r"Zuletzt saniert wurde (\d{4})"),
    re.compile(r"wurde (\d{4}) umfassend \w*saniert"),
]

# deckt alle drei beobachteten Formate ab:
#  "Verbrauchsausweis, 197,0 kWh/(m²·a), Effizienzklasse F"
#  "Bedarfsausweis, 128,3 kWh/(m²·a), Effizienzklasse D"      (auch in Fusszeile)
#  "Energiekennwert 179,8 kWh, Klasse F"                       (kein Typ angegeben)
ENERGIE_RE = re.compile(
    r"(?:(?P<typ>Verbrauchsausweis|Bedarfsausweis),\s*)?"
    r"(?:Energiekennwert\s*)?"
    r"(?P<kwh>[\d,]+)\s*kWh(?:/\(m²·a\))?,?\s*"
    r"(?:Effizienzklasse|Klasse)\s*(?P<klasse>[A-H]\+?)"
)
ENERGIE_TYP_MAP = {"Verbrauchsausweis": "verbrauch", "Bedarfsausweis": "bedarf"}

DATUM_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DATUM_MONATSNAME_RE = re.compile(r"(\d{1,2})\.\s*([A-Za-zäöü]+)\s+(\d{4})")
DATUM_DE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")
VERFUEGBAR_TABELLE = "Bezugsfrei ab"
# Muster explizit auf die drei bekannten Datumsformen begrenzt, damit der
# interne Punkt in "01. Oktober" nicht faelschlich als Satzende gelesen wird.
VERFUEGBAR_FREITEXT_RE = re.compile(
    r"Bezugsfertig ab (\d{4}-\d{2}-\d{2}|\d{1,2}\.\s*[A-Za-zäöü]+\s+\d{4}|\d{1,2}\.\d{1,2}\.\d{2,4})"
)
PROVISIONSFREI_RE = re.compile(r"[Pp]rovisionsfrei")

KALTMIETE_NK_RE = re.compile(r"Die Kaltmiete betraegt ([\d.,]+)\s*€,\s*hinzu kommen ([\d.,]+)\s*EUR Nebenkosten")
NK_WARM_RE = re.compile(r"Zzgl\.\s*([\d.,]+)\s*EUR Nebenkosten \(Warmmiete ([\d.,]+)\s*€\)")
HAUSGELD_FREITEXT_RE = re.compile(r"Das monatliche Hausgeld liegt bei ([\d.,]+)\s*EUR")
KAUTION_FREITEXT_RE = re.compile(r"Die Kaution betraegt ([\d.,]+)\s*€")

TABELLE_GELD_FELDER = {
    "Kaufpreis": "kaufpreis_eur",
    "Hausgeld": "hausgeld_eur",
    "Kaltmiete": "kaltmiete_eur",
    "Nebenkosten": "nebenkosten_eur",
    "Warmmiete": "warmmiete_eur",
    "Kaution": "kaution_eur",
}


def _datum(text: str) -> Optional[str]:
    """Normalisiert diverse Datumsformate auf YYYY-MM-DD.

    Zweistellige Jahre werden als 20XX interpretiert (plausibel im Kontext
    der Daten: alle beobachteten Bezugstermine liegen 2026/2027).
    """
    m = DATUM_ISO_RE.search(text)
    if m:
        return m.group(0)
    m = DATUM_MONATSNAME_RE.search(text)
    if m:
        tag, monat_name, jahr = m.groups()
        monat = MONAT_MAP.get(monat_name.lower())
        if monat:
            return f"{jahr}-{monat:02d}-{int(tag):02d}"
    m = DATUM_DE_RE.search(text)
    if m:
        tag, monat, jahr = m.groups()
        jahr = f"20{jahr}" if len(jahr) == 2 else jahr
        return f"{jahr}-{int(monat):02d}-{int(tag):02d}"
    return None


@dataclass
class Zusatzfelder:
    baujahr: Optional[int] = None
    letzte_sanierung: Optional[int] = None
    zustand: Optional[str] = None
    heizungsart: Optional[str] = None
    energieausweis: Optional[dict] = None
    verfuegbar_ab: Optional[str] = None
    provisionsfrei: Optional[bool] = None
    kaltmiete_eur: Optional[float] = None
    nebenkosten_eur: Optional[float] = None
    warmmiete_eur: Optional[float] = None
    kaution_eur: Optional[float] = None
    kaufpreis_eur: Optional[float] = None
    hausgeld_eur: Optional[float] = None
    warnungen: list = field(default_factory=list)


def extrahiere_zusatzfelder(tabelle: dict, beschreibung_text: str) -> Zusatzfelder:
    z = Zusatzfelder()

    zustand_roh = tabelle.get("Zustand")
    if not zustand_roh:
        m = ZUSTAND_FREITEXT_RE.search(beschreibung_text)
        zustand_roh = m.group(1) if m else None
    if zustand_roh:
        z.zustand = ZUSTAND_MAP.get(zustand_roh.strip().lower())
        if z.zustand is None:
            z.zustand = "sonstige"
            z.warnungen.append(f"unbekannter Zustandswert: {zustand_roh!r} -> 'sonstige'")

    heizung_roh = tabelle.get("Heizung")
    if not heizung_roh:
        m = HEIZUNG_FREITEXT_RE.search(beschreibung_text)
        heizung_roh = m.group(1) if m else None
    if heizung_roh:
        z.heizungsart = HEIZUNG_MAP.get(heizung_roh.strip().lower())
        if z.heizungsart is None:
            z.heizungsart = "sonstige"
            z.warnungen.append(f"unbekannter Heizungswert: {heizung_roh!r} -> 'sonstige'")

    baujahr_roh = tabelle.get("Baujahr")
    if baujahr_roh:
        try:
            z.baujahr = int(_dezimal(baujahr_roh))
        except ValueError:
            pass
    else:
        for pattern in BAUJAHR_FREITEXT_PATTERNS:
            m = pattern.search(beschreibung_text)
            if m:
                z.baujahr = int(m.group(1))
                break

    for pattern in SANIERUNG_FREITEXT_PATTERNS:
        m = pattern.search(beschreibung_text)
        if m:
            z.letzte_sanierung = int(m.group(1))
            break

    energie_text = tabelle.get("Energieausweis", "") + " " + beschreibung_text
    m = ENERGIE_RE.search(energie_text)
    if m:
        z.energieausweis = {
            "typ": ENERGIE_TYP_MAP.get(m.group("typ")),
            "kennwert_kwh": _dezimal(m.group("kwh")),
            "effizienzklasse": m.group("klasse"),
        }

    verfuegbar_roh = tabelle.get(VERFUEGBAR_TABELLE)
    if verfuegbar_roh:
        z.verfuegbar_ab = _datum(verfuegbar_roh)
    else:
        m = VERFUEGBAR_FREITEXT_RE.search(beschreibung_text)
        if m:
            z.verfuegbar_ab = _datum(m.group(1))
    if verfuegbar_roh and z.verfuegbar_ab is None:
        z.warnungen.append(f"Datum nicht parsbar: {verfuegbar_roh!r}")

    # Nur positive Erwaehnung beobachtet -> True. Fehlen der Erwaehnung ist
    # keine Aussage (bleibt None), siehe Notizen zu Teil 2.
    if PROVISIONSFREI_RE.search(beschreibung_text):
        z.provisionsfrei = True

    for spalte, feld in TABELLE_GELD_FELDER.items():
        if spalte in tabelle:
            try:
                setattr(z, feld, _euro(tabelle[spalte]))
            except ValueError:
                z.warnungen.append(f"{spalte} nicht parsbar: {tabelle[spalte]!r}")

    # Tabellen-Header "Miete" (ohne "Kalt"/"Warm") entspricht laut Cross-Check
    # (Kaltmiete + Nebenkosten aus Freitext) der Warmmiete; kommt nur vor,
    # wenn "Kaltmiete" nicht separat in der Tabelle steht.
    if "Miete" in tabelle and z.warmmiete_eur is None:
        try:
            z.warmmiete_eur = _euro(tabelle["Miete"])
        except ValueError:
            z.warnungen.append(f"Miete nicht parsbar: {tabelle['Miete']!r}")

    m = KALTMIETE_NK_RE.search(beschreibung_text)
    if m:
        if z.kaltmiete_eur is None:
            z.kaltmiete_eur = _euro(m.group(1))
        if z.nebenkosten_eur is None:
            z.nebenkosten_eur = _euro(m.group(2))

    m = NK_WARM_RE.search(beschreibung_text)
    if m:
        if z.nebenkosten_eur is None:
            z.nebenkosten_eur = _euro(m.group(1))
        if z.warmmiete_eur is None:
            z.warmmiete_eur = _euro(m.group(2))

    if z.hausgeld_eur is None:
        m = HAUSGELD_FREITEXT_RE.search(beschreibung_text)
        if m:
            z.hausgeld_eur = _euro(m.group(1))

    if z.kaution_eur is None:
        m = KAUTION_FREITEXT_RE.search(beschreibung_text)
        if m:
            z.kaution_eur = _euro(m.group(1))

    if z.kaltmiete_eur is not None and z.nebenkosten_eur is not None and z.warmmiete_eur is not None:
        if abs((z.kaltmiete_eur + z.nebenkosten_eur) - z.warmmiete_eur) > 0.5:
            z.warnungen.append(
                f"Mietbetraege inkonsistent: {z.kaltmiete_eur} + {z.nebenkosten_eur} != {z.warmmiete_eur}"
            )

    # Satz "Der Preis von X EUR ist nach Absprache verhandelbar" wird
    # absichtlich NICHT geparst, siehe Moduldoc.

    return z


# ============================================================
# Ablauf
# ============================================================

def main() -> int:
    out_dir = ROOT / "ergebnis"
    review_dir = out_dir / "zu_pruefen"
    out_dir.mkdir(exist_ok=True)
    review_dir.mkdir(exist_ok=True)

    ergebnisse = []
    fehlerhaft = []
    gesehene_ids: dict[str, str] = {}

    for pfad in sorted(DATEN_DIR.glob("standort_*/*.html")):
        soup, tabelle, beschreibung_text = _parse_html(pfad)
        pflicht = extrahiere_pflichtfelder(pfad, soup, tabelle, beschreibung_text)
        zusatz = extrahiere_zusatzfelder(tabelle, beschreibung_text)

        # Einzigartigkeit der objekt_id: Duplikate werden wie andere
        # Auffaelligkeiten als Warnung behandelt (Pipeline laeuft weiter),
        # bekommen aber einen abweichenden Dateinamen, damit die zuerst
        # gesehene Datei nicht durch die zweite ueberschrieben wird.
        dateiname = pflicht.objekt_id or pfad.stem
        if pflicht.objekt_id:
            if pflicht.objekt_id in gesehene_ids:
                pflicht.warnungen.append(
                    f"doppelte objekt_id: bereits vergeben an {gesehene_ids[pflicht.objekt_id]}"
                )
                dateiname = f"{pflicht.objekt_id}__DUPLIKAT__{pfad.stem}"
            else:
                gesehene_ids[pflicht.objekt_id] = pfad.name

        fehlend = pflicht.fehlende_pflichtfelder()
        pflicht_dict = asdict(pflicht)
        pflicht_dict.pop("objekt_id")
        if fehlend:
            pflicht_dict["fehlende_pflichtfelder"] = fehlend

        datensatz = {
            "objekt_id": pflicht.objekt_id,
            "datei": pfad.name,
            "pflichtfelder": pflicht_dict,
            "zusatzfelder": asdict(zusatz),
        }
        if fehlend:
            fehlerhaft.append(datensatz)
        ergebnisse.append(datensatz)

        ziel = review_dir if fehlend else out_dir
        (ziel / f"{dateiname}.json").write_text(
            json.dumps(datensatz, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    mit_warnung = [
        e for e in ergebnisse if e["pflichtfelder"]["warnungen"] or e["zusatzfelder"]["warnungen"]
    ]

    report = {
        "anzahl_objekte": len(ergebnisse),
        "anzahl_fehlerhaft": len(fehlerhaft),
        "anzahl_mit_warnung": len(mit_warnung),
        "fehlerhaft": [
            {"objekt_id": e["objekt_id"], "datei": e["datei"], "fehlende_pflichtfelder": e["pflichtfelder"]["fehlende_pflichtfelder"]}
            for e in fehlerhaft
        ],
        "warnungen": [
            {
                "objekt_id": e["objekt_id"],
                "datei": e["datei"],
                "warnungen_pflichtfelder": e["pflichtfelder"]["warnungen"],
                "warnungen_zusatzfelder": e["zusatzfelder"]["warnungen"],
            }
            for e in mit_warnung
        ],
    }
    (out_dir / "_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"{len(ergebnisse)} Objekte verarbeitet.")
    print(f"{len(fehlerhaft)} mit fehlenden Pflichtfeldern -> ergebnis/zu_pruefen/, siehe ergebnis/_report.json")
    print(f"{len(mit_warnung)} mit Warnungen (Pflicht- oder Zusatzfelder):")
    for e in mit_warnung:
        alle = e["pflichtfelder"]["warnungen"] + e["zusatzfelder"]["warnungen"]
        print(f"  - {e['datei']}: {alle}")

    return 1 if fehlerhaft else 0


if __name__ == "__main__":
    sys.exit(main())
