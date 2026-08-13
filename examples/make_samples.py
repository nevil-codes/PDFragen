"""Generate the sample German PDFs used for the demo.

The generated PDFs are committed alongside this script so reviewers can try the
app immediately; regenerate them with:

    python examples/make_samples.py
"""

from __future__ import annotations

from pathlib import Path

# Helvetica's built-in encoding (WinAnsi) covers German umlauts, so the text
# below can use them directly.
PAGE_WIDTH, PAGE_HEIGHT = 595, 842  # A4 in points


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _content_stream(lines: list[tuple[str, int, bool]]) -> str:
    """Build a PDF text stream from (text, size, bold) lines."""
    ops = ["BT", "50 780 Td"]
    current = None
    for text, size, bold in lines:
        font = "/F2" if bold else "/F1"
        spec = (font, size)
        if spec != current:
            ops.append(f"{font} {size} Tf {int(size * 1.6)} TL")
            current = spec
        ops.append(f"({_escape(text)}) Tj T*")
    ops.append("ET")
    return "\n".join(ops)


def _build_pdf(pages: list[list[tuple[str, int, bool]]]) -> bytes:
    """Assemble a minimal multi-page PDF with Helvetica regular + bold."""
    streams = [_content_stream(page) for page in pages]

    objects: list[str] = []
    page_obj_start = 3
    content_obj_start = page_obj_start + len(pages)
    font_regular = content_obj_start + len(pages)
    font_bold = font_regular + 1

    kids = " ".join(f"{page_obj_start + i} 0 R" for i in range(len(pages)))
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")

    for i in range(len(pages)):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R >> >> "
            f"/Contents {content_obj_start + i} 0 R >>"
        )

    for stream in streams:
        encoded = stream.encode("latin-1")
        objects.append(f"<< /Length {len(encoded)} >>\nstream\n{stream}\nendstream")

    objects.append(
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    objects.append(
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )

    out = "%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out.encode("latin-1")))
        out += f"{i} 0 obj\n{body}\nendobj\n"

    xref_at = len(out.encode("latin-1"))
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    )
    return out.encode("latin-1")


R, B = False, True

AUSLAENDERBEHOERDE = [
    [
        ("Ausländerbehörde der Stadt Musterstadt", 14, B),
        ("Sachgebiet Aufenthaltsrecht - Zimmer 312", 10, R),
        ("Rathausplatz 1, 12345 Musterstadt", 10, R),
        ("", 10, R),
        ("Musterstadt, den 3. August 2026", 10, R),
        ("", 10, R),
        ("Aktenzeichen: AZ-2026-04871", 11, B),
        ("", 10, R),
        ("Betreff: Verlängerung der Aufenthaltserlaubnis zum Zweck", 12, B),
        ("des Studiums (§ 16b AufenthG)", 12, B),
        ("", 10, R),
        ("Sehr geehrte Frau Sharma,", 11, R),
        ("", 10, R),
        ("Ihre derzeitige Aufenthaltserlaubnis läuft am 31. Oktober 2026 ab.", 11, R),
        ("Um Ihren Aufenthalt fortzusetzen, müssen Sie die Verlängerung", 11, R),
        ("spätestens acht Wochen vor Ablauf, also bis zum 5. September 2026,", 11, R),
        ("bei unserer Behörde beantragen.", 11, R),
        ("", 10, R),
        ("Erforderliche Unterlagen", 12, B),
        ("", 10, R),
        ("1. Gültiger Reisepass (mindestens noch 12 Monate gültig)", 11, R),
        ("2. Aktuelle Immatrikulationsbescheinigung der Hochschule", 11, R),
        ("3. Nachweis über ausreichenden Krankenversicherungsschutz", 11, R),
        ("4. Nachweis der Sicherung des Lebensunterhalts:", 11, R),
        ("   Sperrkonto mit mindestens 11.904 Euro oder eine", 11, R),
        ("   Verpflichtungserklärung nach § 68 AufenthG", 11, R),
        ("5. Ein aktuelles biometrisches Passfoto", 11, R),
        ("6. Nachweis über ausreichenden Wohnraum (Mietvertrag)", 11, R),
        ("", 10, R),
        ("Die Bearbeitungsgebühr beträgt 96,00 Euro und ist bei", 11, R),
        ("Antragstellung zu entrichten.", 11, R),
    ],
    [
        ("Terminvereinbarung", 12, B),
        ("", 10, R),
        ("Eine persönliche Vorsprache ist zwingend erforderlich. Termine", 11, R),
        ("vereinbaren Sie ausschließlich online über das Terminportal", 11, R),
        ("der Stadt Musterstadt. Eine Vorsprache ohne Termin ist nicht", 11, R),
        ("möglich.", 11, R),
        ("", 10, R),
        ("Wichtiger Hinweis", 12, B),
        ("", 10, R),
        ("Sollten Sie den Antrag nicht fristgerecht stellen, erlischt Ihr", 11, R),
        ("rechtmäßiger Aufenthalt mit Ablauf der Erlaubnis. Ein verspäteter", 11, R),
        ("Antrag kann zur Ablehnung führen.", 11, R),
        ("", 10, R),
        ("Beschäftigung neben dem Studium", 12, B),
        ("", 10, R),
        ("Als Studierende dürfen Sie 140 ganze oder 280 halbe Tage pro", 11, R),
        ("Jahr arbeiten. Eine Tätigkeit als studentische Hilfskraft an", 11, R),
        ("Ihrer Hochschule ist davon nicht erfasst und unbeschränkt", 11, R),
        ("zulässig, muss uns aber angezeigt werden.", 11, R),
        ("", 10, R),
        ("Bei Rückfragen erreichen Sie uns montags bis donnerstags", 11, R),
        ("von 8:00 bis 12:00 Uhr unter der Telefonnummer 0123 / 456-312.", 11, R),
        ("", 10, R),
        ("Mit freundlichen Grüßen", 11, R),
        ("", 10, R),
        ("i. A. Michaela Brandt", 11, R),
        ("Sachbearbeiterin", 10, R),
    ],
]

VORLESUNG = [
    [
        ("Einführung in das Maschinelle Lernen", 15, B),
        ("Vorlesung 4: Regularisierung und Überanpassung", 12, B),
        ("Prof. Dr. Andreas Weber - Wintersemester 2026/27", 10, R),
        ("", 10, R),
        ("1. Das Problem der Überanpassung", 12, B),
        ("", 10, R),
        ("Ein Modell ist überangepasst (englisch: overfitting), wenn es die", 11, R),
        ("Trainingsdaten sehr gut abbildet, auf neuen Daten jedoch schlecht", 11, R),
        ("abschneidet. Das Modell hat dann nicht die zugrundeliegende", 11, R),
        ("Struktur gelernt, sondern das Rauschen der Trainingsmenge", 11, R),
        ("auswendig gelernt.", 11, R),
        ("", 10, R),
        ("Typische Anzeichen sind ein sehr geringer Trainingsfehler bei", 11, R),
        ("gleichzeitig hohem Validierungsfehler. Die Differenz zwischen", 11, R),
        ("beiden nennt man die Generalisierungslücke.", 11, R),
        ("", 10, R),
        ("2. Der Bias-Varianz-Kompromiss", 12, B),
        ("", 10, R),
        ("Der erwartete Fehler eines Modells lässt sich zerlegen in:", 11, R),
        ("", 10, R),
        ("  Gesamtfehler = Verzerrung^2 + Varianz + irreduzibles Rauschen", 11, R),
        ("", 10, R),
        ("Ein zu einfaches Modell hat eine hohe Verzerrung (Unteranpassung),", 11, R),
        ("ein zu komplexes Modell eine hohe Varianz (Überanpassung). Ziel", 11, R),
        ("ist es, die Summe beider Terme zu minimieren.", 11, R),
    ],
    [
        ("3. Regularisierungsverfahren", 12, B),
        ("", 10, R),
        ("L2-Regularisierung (Ridge)", 11, B),
        ("Addiert die quadrierte Summe der Gewichte zur Verlustfunktion.", 11, R),
        ("Dies bestraft große Gewichte und führt zu glatteren Modellen.", 11, R),
        ("Der Hyperparameter Lambda steuert die Stärke der Bestrafung.", 11, R),
        ("", 10, R),
        ("L1-Regularisierung (Lasso)", 11, B),
        ("Addiert die Summe der Betragswerte der Gewichte. Im Unterschied", 11, R),
        ("zur L2-Regularisierung werden hier einzelne Gewichte exakt auf", 11, R),
        ("null gesetzt, wodurch eine automatische Merkmalsauswahl", 11, R),
        ("stattfindet.", 11, R),
        ("", 10, R),
        ("Dropout", 11, B),
        ("Während des Trainings werden zufällig ausgewählte Neuronen", 11, R),
        ("deaktiviert, üblicherweise mit einer Wahrscheinlichkeit zwischen", 11, R),
        ("0,2 und 0,5. Dadurch kann sich das Netz nicht auf einzelne", 11, R),
        ("Neuronen verlassen. Beim Testen ist Dropout abgeschaltet.", 11, R),
        ("", 10, R),
        ("Frühes Abbrechen (Early Stopping)", 11, B),
        ("Das Training wird beendet, sobald der Validierungsfehler über", 11, R),
        ("mehrere Epochen hinweg nicht mehr sinkt. Die Anzahl der", 11, R),
        ("Epochen, die abgewartet wird, heißt Geduld (patience).", 11, R),
        ("", 10, R),
        ("4. Prüfungsrelevante Hinweise", 12, B),
        ("", 10, R),
        ("Die Herleitung der Bias-Varianz-Zerlegung ist klausurrelevant.", 11, R),
        ("Übungsblatt 4 ist bis zum 15. Dezember 2026 abzugeben.", 11, R),
    ],
]


def main() -> None:
    out_dir = Path(__file__).parent
    samples = {
        "auslaenderbehoerde_verlaengerung.pdf": AUSLAENDERBEHOERDE,
        "vorlesung_maschinelles_lernen.pdf": VORLESUNG,
    }
    for name, pages in samples.items():
        (out_dir / name).write_bytes(_build_pdf(pages))
        print(f"wrote {name} ({len(pages)} pages)")


if __name__ == "__main__":
    main()
