"""Generate self-decoding cards for the practical or full dense demo layout."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from component3.backend.comp3_reco_navigation.navigation.apriltag import detect_apriltags_frame  # noqa: E402
from component3.data.apriltag_cards.generate_cards import write_grayscale_pdf  # noqa: E402


LAYOUT = ROOT / "component3/data/demo_store/v2/dense_apriltag_layout.json"


def make_card(tag: dict[str, object], ppm: int = 8) -> np.ndarray:
    width, height, marker = 90 * ppm, 100 * ppm, 70 * ppm
    image = np.full((height, width), 255, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    code = cv2.aruco.generateImageMarker(dictionary, int(tag["tag_id"]), marker)
    margin = 10 * ppm
    image[margin:margin + marker, margin:margin + marker] = code
    anchor = tag["anchor"]
    place = anchor.get("node_id") or f"{anchor['source']}–{anchor['target']}"
    label = f"ID {tag['tag_id']} | {place} | {tag['purpose']}"
    cv2.putText(image, label, (3 * ppm, 94 * ppm), cv2.FONT_HERSHEY_SIMPLEX,
                0.38 * ppm / 8, 0, max(1, ppm // 4), cv2.LINE_AA)
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", choices=("practical", "all"), default="practical")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent / "generated_dense_practical")
    args = parser.parse_args()
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    selected = set(layout["practical_subset_tag_ids"])
    tags = [tag for tag in layout["tags"]
            if args.subset == "all" or tag["tag_id"] in selected]
    args.output.mkdir(parents=True, exist_ok=True)
    cards = []
    for tag in tags:
        card = make_card(tag)
        detected = [item.marker_id for item in detect_apriltags_frame(card)]
        if detected != [tag["tag_id"]]:
            raise RuntimeError(f"ID {tag['tag_id']} decode check failed: {detected}")
        cards.append(card)
        stem = f"apriltag_36h11_id_{tag['tag_id']}_90mm"
        if not cv2.imwrite(str(args.output / f"{stem}.png"), card):
            raise RuntimeError(f"Could not write {stem}.png")
        write_grayscale_pdf(args.output / f"{stem}.pdf", card, 90, 100)
    columns = 3
    rows = (len(cards) + columns - 1) // columns
    sheet = np.full((rows * 100 * 4, columns * 90 * 4), 255, dtype=np.uint8)
    for index, card in enumerate(cards):
        small = cv2.resize(card, (90 * 4, 100 * 4), interpolation=cv2.INTER_NEAREST)
        row, column = divmod(index, columns)
        sheet[row * 400:(row + 1) * 400, column * 360:(column + 1) * 360] = small
    if not cv2.imwrite(str(args.output / "printable_sheet.png"), sheet):
        raise RuntimeError("Could not write printable sheet")
    write_grayscale_pdf(args.output / "printable_sheet.pdf", sheet, columns * 90, rows * 100)
    manifest = {"layout_id": layout["layout_id"], "subset": args.subset,
                "card_size_mm": [90, 100], "tag_ids": [tag["tag_id"] for tag in tags],
                "decode_verified": True, "print_instruction": "Print at 100% / Actual Size."}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with (args.output / "placement_sheet.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "tag_id", "x_m", "y_m", "orientation_deg", "anchor_type",
            "anchor", "purpose", "print_file",
        ))
        writer.writeheader()
        for tag in tags:
            anchor = tag["anchor"]
            anchor_label = anchor.get("node_id") or (
                f"{anchor['source']}->{anchor['target']} @ {anchor['offset_m']} m"
            )
            writer.writerow({
                "tag_id": tag["tag_id"], "x_m": tag["x_m"], "y_m": tag["y_m"],
                "orientation_deg": tag["orientation_deg"], "anchor_type": anchor["type"],
                "anchor": anchor_label, "purpose": tag["purpose"],
                "print_file": f"apriltag_36h11_id_{tag['tag_id']}_90mm.pdf",
            })
    print(f"generated and decoded {len(tags)} {args.subset} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
