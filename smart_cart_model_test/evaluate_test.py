import argparse
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "models" / "best.pt"

def main():
    parser = argparse.ArgumentParser(description="Evaluate on a labelled YOLO dataset split.")
    parser.add_argument("--data", required=True, help="Path to dataset data.yaml")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="Path to best.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    if not Path(args.model).exists():
        raise FileNotFoundError(f"Model not found: {args.model}")
    if not Path(args.data).exists():
        raise FileNotFoundError(f"Dataset YAML not found: {args.data}")

    model = YOLO(args.model)
    metrics = model.val(data=args.data, split=args.split, imgsz=args.imgsz)
    print(f"Metrics for split={args.split}")
    print(f"Precision: {metrics.box.mp:.4f}")
    print(f"Recall:    {metrics.box.mr:.4f}")
    print(f"mAP50:     {metrics.box.map50:.4f}")
    print(f"mAP50-95:  {metrics.box.map:.4f}")

if __name__ == "__main__":
    main()
