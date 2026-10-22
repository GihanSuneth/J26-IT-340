import argparse
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "models" / "best.pt"
DEFAULT_OUTPUT = ROOT / "results"

def main():
    parser = argparse.ArgumentParser(description="Run YOLO on an image or folder.")
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="Path to best.pt")
    parser.add_argument("--source", required=True, help="Image path or folder path")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}. Copy best.pt to models/best.pt.")
    source = Path(args.source)
    if not source.exists():
        raise FileNotFoundError(f"Image/folder not found: {source}")

    model = YOLO(str(model_path))
    model.predict(source=str(source), conf=args.conf, save=True,
                  project=str(Path(args.output).resolve()), name="predictions", exist_ok=True)
    print(f"Predictions saved to: {Path(args.output).resolve() / 'predictions'}")

if __name__ == "__main__":
    main()
