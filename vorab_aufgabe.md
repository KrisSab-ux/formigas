# Vorab-Aufgabe: Datenkonsolidierung Immobilienbestand

## Ausgangslage

Ein mittelständisches Immobilienunternehmen betreibt seit Jahren mehrere Standorte. Die Objektdaten werden dort unterschiedlich gepflegt: Jeder Standort hat über die Zeit eigene Gewohnheiten entwickelt, welche Angaben wo eingetragen werden und welche im Beschreibungstext landen. Ein einheitliches Datenmodell gibt es nicht.

Das Unternehmen möchte auf eine gemeinsame Datenplattform wechseln. Voraussetzung dafür ist, dass der Bestand in ein einheitliches, maschinenlesbares Format überführt wird. Der Bestand wächst laufend, der Prozess soll also wiederholbar sein und nicht von Hand durchgeführt werden.

Wir sind mit der Machbarkeitsprüfung beauftragt. Du bekommst einen repräsentativen Ausschnitt des Bestands.

---

## Teil 1 — Migration (ca. 60 %)

Überführe die bereitgestellten Objektdaten in das beiliegende Zielschema (`immobilien_schema.json`).

Ergebnis ist eine Sammlung von JSON-Objekten, eines pro Immobilie, sowie der Code, der sie erzeugt hat.

**Zum Umfang:** Das Schema ist bewusst umfangreicher, als in der vorgesehenen Zeit sauber umsetzbar ist. Wir bewerten nicht, wie viele Felder du abdeckst, sondern welche du auswählst und warum. Eine begründet unvollständige Lösung ist besser als eine vollständige ohne Begründung. Die als Pflichtfelder markierten Angaben sollten allerdings belastbar sein.

**Zum Schema:** Das ist ein aktueller Entwurf und nicht in Stein gemeißelt. Wenn du an Grenzen stößt, darfst du davon abweichen — dokumentiere die Abweichung dann bitte kurz.

---

## Teil 2 — Qualitätsaussage (ca. 40 %)

Liefere eine belastbare Aussage darüber, wie gut deine Migration funktioniert.

Wir erwarten keine perfekte Pipeline. Wir erwarten, dass du weißt, wo sie steht. Beschreibe, wie du zu deiner Einschätzung gekommen bist — und wie sicher du dir dabei bist.

Dieser Teil ist bewusst offen gehalten. Auch eine Aussage der Form „so genau kann ich das mit meinem Vorgehen nicht sagen, weil …" ist eine gute Antwort, wenn sie begründet ist.

---

## Was du bekommst

- `daten/` — der Ausschnitt aus dem Bestand
- `immobilien_schema.json` — das Zielschema, JSON Schema (Draft 2020-12), mit Feldbeschreibungen
- Zugang zu einem LLM (separat per Mail). Du kannst stattdessen auch eigene Zugänge oder lokale Modelle nutzen — sag uns nur kurz, was du verwendet hast.

Ein Hinweis der Vollständigkeit halber: Wenn du unseren Zugang nutzt, sind die darüber laufenden Anfragen für uns technisch einsehbar. Wir werten sie nicht systematisch aus — falls uns etwas auffällt, sprechen wir es im Gespräch an.

## Was du vorab abgibst


| Artefakt       | Grenze                                                                                                                                                                                           |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Code           | Als Repository (Zip oder Link), mit README, festgelegten Abhängigkeiten und einem Befehl zum Starten.                                                                              |
| Ergebnisdaten  | Die erzeugten JSON-Objekte, entweder als eine Datei (Liste von Objekten) oder als ein Verzeichnis mit einer`.json` je Objekt. Jedes Objekt enthält seine `objekt_id` aus der Quelle.            |
| Notizen        | **ca. eine Seite, Stichpunkte genügen.** Zu den vier Punkten unten. Damit wir uns auf das Gespräch vorbereiten können — es ist keine Präsentationsunterlage und muss nicht vorzeigbar sein. |
| KI-Ausschnitte | Zwei Stellen (s. u.). Zählen nicht gegen den Umfang der Notizen.                                                                                                                                |

Mehr brauchen wir vorher nicht. Was du dir für die Vorstellung am Termin zurechtlegst, bleibt bei dir — Folien oder Ähnliches musst du uns nicht vorab schicken.

Alles Technische (Setup, Aufbau, Abhängigkeiten) gehört ins README und zählt nicht dazu.

Die vier Punkte, die uns am meisten interessieren:

- Wie bist du vorgegangen?
- Welche Entscheidungen hast du getroffen, bei denen es auch anders gegangen wäre — und warum so?
- Was hast du verworfen?
- Das Ergebnis aus Teil 2: wie gut funktioniert deine Migration, und wie sicher bist du dir?

## Zeitrahmen

Kalkuliert ist **ein Arbeitstag, maximal zwei**. Bitte halte dich daran — auch wenn das heißt, unfertig abzugeben. Das ist ausdrücklich in Ordnung und wir bewerten es nicht negativ.

Abgabe bis **Sonntag, 16.08.26 18:00 Uhr**  an tatjana@formigas.de.

## Nutzung von KI-Assistenten

Der Einsatz von KI-Assistenten ist ausdrücklich erlaubt und erwünscht — wir arbeiten selbst so.

Halte in deinen Notizen kurz fest, welche Werkzeuge du wofür eingesetzt hast. Besonders interessiert uns: **welche Vorschläge hast du verworfen und warum?**

Wähle außerdem zwei Stellen aus, an denen die Zusammenarbeit mit dem Assistenten für dich interessant war — eine, an der sie gut funktioniert hat, und eine, an der du korrigieren oder umsteuern musstest. Zeig uns den jeweiligen Ausschnitt (Screenshot, Copy-Paste oder Link genügt) und ordne in ein bis zwei Sätzen ein, was passiert ist.

Falls du deinen vollständigen Verlauf exportieren kannst und ihn teilen möchtest, nehmen wir ihn gern entgegen — verpflichtend ist das nicht.

---

## Wie es vor Ort weitergeht

Wir schauen uns deine Einsendung vorab an, damit am Termin mehr Zeit für die Diskussion bleibt. Dort stellst du deine Lösung in **max. 15 Minuten** vor — 10 reichen völlig. Das Format ist dir überlassen: Folien sind nicht nötig, gemeinsam in den Code zu schauen ist völlig in Ordnung, und du kannst dich auch an deinen Notizen entlangbewegen. Anschließend diskutieren wir gemeinsam (ca. 40 Minuten). Publikum sind zwei Data Scientists.

Uns interessieren die Ergebnisse. Mindestens genauso interessieren uns dein Vorgehen, deine Entscheidungen und die Alternativen, gegen die du dich entschieden hast.

## Zu den Daten und deinen Ergebnissen

Die bereitgestellten Daten sind synthetisch erzeugt und enthalten keine realen Personen- oder Objektdaten.

Deine Einsendung nutzen wir ausschließlich zur Bewertung im Rahmen dieses Bewerbungsverfahrens. Sie wird nicht produktiv verwendet und nach Abschluss des Verfahrens gelöscht. Die Rechte an deiner Arbeit bleiben bei dir.

## Fragen

Wenn etwas unklar ist, frag uns: tatjana@formigas.de. Nachfragen sind ausdrücklich erwünscht und kein Minuspunkt.

Wo eine Angabe in den Daten mehrdeutig ist, ist das kein Versehen im Aufgabentext — triff eine Entscheidung und halte sie fest.
