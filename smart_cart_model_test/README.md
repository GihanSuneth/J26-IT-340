# Smart Shopping Cart YOLOv11 Model Test

## Folder structure
- `models/best.pt` — put your trained model here (not included in this ZIP).
- `test_images/` — put sample product photos here.
- `results/` — prediction images are saved here.
- `predict_image.py` — predicts on one image or a folder.
- `webcam.py` — live webcam detection; press `q` to quit.
- `evaluate_test.py` — evaluates on a labelled dataset test split.
- `requirements.txt` — Python dependencies.

## 1. Add your model
Copy your downloaded `best.pt` into `models/` and ensure the path is exactly `models/best.pt`. This ZIP does not include the weights because you have not uploaded `best.pt` to this chat.

## 2. Install
Use Python 3.10 or 3.11 if possible. Open a terminal in this folder:

```bash
python -m venv .venv
```
Windows:
```bash
.venv\\Scripts\\activate
```
macOS/Linux:
```bash
source .venv/bin/activate
```
Then:
```bash
pip install -r requirements.txt
```

## 3. Test one image
Put an image in `test_images/`, e.g. `phone.jpg`:
```bash
python predict_image.py --source test_images/phone.jpg
```
Predictions are saved under `results/predictions/`.

Test a folder:
```bash
python predict_image.py --source test_images
```

## 4. Test live webcam
```bash
python webcam.py
```
If your camera is not camera 0, try:
```bash
python webcam.py --camera 1
```

## 5. Evaluate test metrics (requires exported dataset and its data.yaml)
```bash
python evaluate_test.py --data path/to/data.yaml --split test
```

Your model should use the classes it was trained with: bag, bangle, chain, earrings, key, phone, ring, sunglasses, wallet, watch (verify these against your exported `data.yaml`). Object detection does not determine exact product SKU or price; your application needs a product database and logic to avoid counting the same item in every camera frame.
