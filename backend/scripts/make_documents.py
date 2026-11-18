"""Render synthetic claim documents for each case from its ground truth.

Every image carries a SYNTHETIC watermark. The layouts are invented for the demo and do
not copy any official SHA form.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

DATA_DIR = Path(__file__).parents[2] / "data" / "synthetic"
WIDTH, HEIGHT = 1240, 1754
INK = (20, 28, 48)
FACILITY_NAMES = {2: "Mwangaza Dispensary", 3: "Tumaini Health Centre", 4: "Upendo County Hospital"}


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), (250, 248, 242))
    draw = ImageDraw.Draw(image)
    draw.text((WIDTH - 470, 40), "SYNTHETIC - DEMO ONLY", fill=(190, 60, 50), font=font(34))
    return image, draw


def claim_form(case: dict, signed: bool) -> Image.Image:
    image, draw = page()
    fields = case["fields"]
    draw.text((80, 120), FACILITY_NAMES[case["facility_level"]], fill=INK, font=font(48))
    draw.text(
        (80, 185),
        f"Level {case['facility_level']} facility  |  {case['facility_id']}",
        fill=INK,
        font=font(30),
    )
    draw.text((80, 280), "PATIENT CLAIM SUMMARY", fill=INK, font=font(40))
    rows = [
        ("Patient name", fields["patient_name"].replace(" [demo]", "")),
        ("Patient number", case["patient_ref"]),
        ("Visit type", case["documents_service_type"].title()),
        ("Date of admission / visit", fields["admission_date"]),
        ("Date of discharge", fields["discharge_date"]),
        ("Diagnosis", fields["diagnosis"]),
        ("Rendering physician", "Dr. Amani Otieno"),
        ("Physician registration no.", case["practitioner_id"]),
    ]
    y = 380
    for label, value in rows:
        draw.text((80, y), f"{label}:", fill=INK, font=font(30))
        draw.text((520, y), value, fill=INK, font=font(34))
        draw.line((520, y + 44, WIDTH - 80, y + 44), fill=(180, 175, 165), width=2)
        y += 95
    draw.text((80, 1180), "HOSPITAL DECLARATION", fill=INK, font=font(34))
    draw.text(
        (80, 1235),
        "The information above and any attachments are true, accurate and complete.",
        fill=INK,
        font=font(26),
    )
    draw.text((80, 1360), "Signature:", fill=INK, font=font(30))
    draw.line((260, 1410, 700, 1410), fill=INK, width=3)
    if signed:
        draw.text((280, 1340), "M. Wanjala", fill=(30, 50, 140), font=font(56))
    draw.text((780, 1290), "Facility stamp:", fill=INK, font=font(26))
    draw.ellipse((800, 1330, 1080, 1520), outline=(150, 40, 60), width=5)
    stamp = FACILITY_NAMES[case["facility_level"]].split()[0].upper()
    draw.text((940, 1395), stamp, fill=(150, 40, 60), font=font(28), anchor="mm")
    draw.text((940, 1445), "SYNTHETIC", fill=(150, 40, 60), font=font(22), anchor="mm")
    return image


def invoice(case: dict) -> Image.Image:
    image, draw = page()
    draw.text((80, 120), FACILITY_NAMES[case["facility_level"]], fill=INK, font=font(48))
    draw.text((80, 230), "INVOICE", fill=INK, font=font(44))
    patient = case["fields"]["patient_name"].replace(" [demo]", "")
    draw.text((80, 310), f"Patient: {patient}  ({case['patient_ref']})", fill=INK, font=font(30))
    total = sum(amount for _, amount in case["invoice_items"])
    lines = case["invoice_items"] if case["invoice_itemised"] else [["Medical services", total]]
    codes = case.get("invoice_codes") if case["invoice_itemised"] else None
    if codes:
        draw.text((80, 400), "Tariff code", fill=INK, font=font(24))
        draw.text((380, 400), "Service", fill=INK, font=font(24))
    y = 450
    for number, (description, amount) in enumerate(lines):
        if codes:  # synthetic codes, never real SHA tariff codes
            draw.text((80, y), codes[number], fill=INK, font=font(30))
        draw.text((380 if codes else 80, y), description, fill=INK, font=font(34))
        draw.text((900, y), f"KSh {amount:,}", fill=INK, font=font(34))
        y += 80
    draw.line((80, y + 10, WIDTH - 80, y + 10), fill=INK, width=3)
    draw.text((80, y + 40), "TOTAL", fill=INK, font=font(38))
    draw.text((900, y + 40), f"KSh {total:,}", fill=INK, font=font(38))
    return image


def summary(case: dict, signed: bool) -> Image.Image:
    """A discharge summary, or a case summary for an outpatient visit."""
    image, draw = page()
    fields = case["fields"]
    outpatient = case["documents_service_type"] == "outpatient"
    draw.text((80, 120), FACILITY_NAMES[case["facility_level"]], fill=INK, font=font(48))
    draw.text(
        (80, 230), "CASE SUMMARY" if outpatient else "DISCHARGE SUMMARY", fill=INK, font=font(44)
    )
    rows = [
        ("Patient name", fields["patient_name"].replace(" [demo]", "")),
        ("Patient number", case["patient_ref"]),
        ("Date of admission / visit", fields["admission_date"]),
        ("Date of discharge", fields["discharge_date"]),
        ("Diagnosis", fields["diagnosis"]),
    ]
    y = 340
    for label, value in rows:
        draw.text((80, y), f"{label}:", fill=INK, font=font(30))
        draw.text((520, y), value, fill=INK, font=font(34))
        draw.line((520, y + 44, WIDTH - 80, y + 44), fill=(180, 175, 165), width=2)
        y += 95
    draw.text((80, 1300), "Treating clinician signature:", fill=INK, font=font(30))
    draw.line((560, 1360, 1040, 1360), fill=INK, width=3)
    if signed:
        draw.text((580, 1290), "A. Otieno", fill=(30, 50, 140), font=font(56))
    return image


def save(image: Image.Image, path: Path, force: bool) -> None:
    """Write a document unless it exists; recorded model responses depend on the pixels."""
    if force or not path.exists():
        image.save(path)
        print("rendered", path.relative_to(DATA_DIR))


def main() -> None:
    force = "--force" in sys.argv
    for path in sorted(DATA_DIR.glob("*/ground_truth.json")):
        case = json.loads(path.read_text())
        folder = path.parent
        form = claim_form(case, case["form_signed"])
        if case.get("form_blurred"):
            form = form.filter(ImageFilter.GaussianBlur(radius=9))
        save(form, folder / "claim_form.png", force)
        save(invoice(case), folder / "invoice.png", force)
        if not case["form_signed"]:
            save(claim_form(case, True), folder / "claim_form_signed.png", force)
        if case.get("has_summary", True):
            name = (
                "case_summary.png"
                if case["documents_service_type"] == "outpatient"
                else ("discharge_summary.png")
            )
            save(summary(case, case.get("summary_signed", True)), folder / name, force)


if __name__ == "__main__":
    main()
