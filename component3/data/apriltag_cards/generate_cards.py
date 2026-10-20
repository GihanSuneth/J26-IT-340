"""Generate and self-verify printable demo-store AprilTag 36h11 cards."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import zlib

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from component3.backend.comp3_reco_navigation.navigation.apriltag import (  # noqa: E402
    detect_apriltags_frame,
)


CARDS = {200: "CP200 - Entrance", 201: "CP201 - Central cross-aisle", 202: "CP202 - Checkout", 42: "UNKNOWN TAG - negative test"}
MM_TO_PT = 72.0 / 25.4


def make_card(tag_id: int, pixels_per_mm: int = 10) -> np.ndarray:
    """Return a 200 mm card plus a separate 20 mm label strip."""
    card_px = 200 * pixels_per_mm
    marker_px = 160 * pixels_per_mm
    label_px = 20 * pixels_per_mm
    image = np.full((card_px + label_px, card_px), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    marker = cv2.aruco.generateImageMarker(dictionary, tag_id, marker_px)
    margin = 20 * pixels_per_mm
    image[margin:margin + marker_px, margin:margin + marker_px] = marker
    label = f"AprilTag 36h11 ID {tag_id} | {CARDS[tag_id]}"
    scale = max(0.45, pixels_per_mm / 10)
    thickness = max(1, pixels_per_mm // 5)
    size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    x = max(5, (card_px - size[0]) // 2)
    y = card_px + (label_px + size[1]) // 2
    cv2.putText(image, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, 0, thickness, cv2.LINE_AA)
    return image


def write_grayscale_pdf(path: Path, image: np.ndarray, width_mm: float, height_mm: float) -> None:
    """Write one dependency-free raster PDF at exact physical dimensions."""
    height_px, width_px = image.shape
    compressed = zlib.compress(image.tobytes(), 9)
    width_pt, height_pt = width_mm * MM_TO_PT, height_mm * MM_TO_PT
    content = f"q {width_pt:.4f} 0 0 {height_pt:.4f} 0 0 cm /Im0 Do Q".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width_pt:.4f} {height_pt:.4f}] /Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>".encode(),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        (
            f"<< /Type /XObject /Subtype /Image /Width {width_px} /Height {height_px} "
            f"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\nstream\n"
        ).encode() + compressed + b"\nendstream",
    ]
    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(document)


def make_sheet(cards: dict[int, np.ndarray]) -> np.ndarray:
    """Arrange four 200x220 mm cards on an A2 portrait sheet."""
    ppm = 5
    sheet = np.full((594 * ppm, 420 * ppm), 255, dtype=np.uint8)
    for index, tag_id in enumerate(CARDS):
        card = cv2.resize(cards[tag_id], (200 * ppm, 220 * ppm), interpolation=cv2.INTER_NEAREST)
        row, col = divmod(index, 2)
        x = (10 + 200 * col) * ppm
        y = (67 + 230 * row) * ppm
        sheet[y:y + 220 * ppm, x:x + 200 * ppm] = card
        cv2.rectangle(sheet, (x, y), (x + 200 * ppm - 1, y + 200 * ppm - 1), 0, 2)
    return sheet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "generated")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cards: dict[int, np.ndarray] = {}
    for tag_id in CARDS:
        card = make_card(tag_id)
        detected = [item.marker_id for item in detect_apriltags_frame(card)]
        if detected != [tag_id]:
            raise RuntimeError(f"Generated ID {tag_id} failed self-verification: {detected}")
        cards[tag_id] = card
        stem = f"apriltag_36h11_id_{tag_id}"
        if not cv2.imwrite(str(args.output / f"{stem}.png"), card):
            raise RuntimeError(f"Could not write {stem}.png")
        write_grayscale_pdf(args.output / f"{stem}.pdf", card, 200, 220)
        print(f"verified {stem}: detected ID {tag_id}")
    sheet = make_sheet(cards)
    write_grayscale_pdf(args.output / "apriltag_36h11_printable_sheet_A2.pdf", sheet, 420, 594)
    print("generated A2 printable sheet; print all PDFs at 100% / Actual Size")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
