from pathlib import Path
from threading import Lock, Thread
import time
import uuid
import cv2
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'product model' / 'test' / 'models' / 'best.pt'
PRICES = ROOT / 'data' / 'product_recognition' / 'product_prices.xlsx'
CONFIDENCE = 0.70
HOLD_SECONDS = 2.5
MISSING_GRACE_SECONDS = 0.35
CAMERA_INDEX = 0

app = FastAPI(title='SmartCart Automatic YOLO API')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://127.0.0.1:5173'], allow_methods=['*'], allow_headers=['*'])
lock = Lock()
products = {}
cart = []
seen_classes = set()
latest_jpeg = None
camera_status = 'starting'

# A class-level hold timer: one unit per class per shopping session.
# If a class briefly disappears, the timer resets after the grace interval.
first_seen = {}
last_seen = {}


def load_products():
    if not PRICES.exists():
        raise RuntimeError(f'Missing price workbook: {PRICES}')
    wb = load_workbook(PRICES, read_only=True, data_only=True)
    try:
        rows = list(wb.active.iter_rows(min_row=2, values_only=True))
    finally:
        wb.close()
    return {str(r[0]): {'class_name':str(r[0]), 'name':str(r[1]), 'price':float(r[2]), 'weight_g':float(r[3])} for r in rows if r[0] is not None}


def cart_snapshot():
    return {'items':[dict(x) for x in cart], 'count':len(cart), 'total':round(sum(x['price'] for x in cart),2)}


def worker():
    global latest_jpeg, camera_status
    try:
        if not MODEL.is_file():
            raise FileNotFoundError(f'Model not found: {MODEL}')
        model = YOLO(str(MODEL))
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            raise RuntimeError('Cannot open USB webcam. Check CAMERA_INDEX and close other camera apps.')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        camera_status = 'running'
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    camera_status = 'camera frame unavailable'
                    time.sleep(0.1)
                    continue
                now = time.monotonic()
                result = model.predict(frame, conf=CONFIDENCE, imgsz=640, iou=0.5, verbose=False)[0]
                present = set()
                for box in result.boxes:
                    cls_id = int(box.cls.item())
                    name = str(model.names[cls_id])
                    if name in products:
                        present.add(name)
                with lock:
                    for name in present:
                        if name in seen_classes:
                            continue
                        if name not in first_seen or now-last_seen.get(name,0) > MISSING_GRACE_SECONDS:
                            first_seen[name] = now
                        last_seen[name] = now
                        if now-first_seen[name] >= HOLD_SECONDS:
                            p = products[name]
                            cart.append({'id':str(uuid.uuid4()), 'class_name':name, 'name':p['name'], 'price':p['price'], 'weight_g':p['weight_g'], 'in_basket':True, 'added_at':time.time()})
                            seen_classes.add(name)
                    for name in list(first_seen):
                        if name not in seen_classes and now-last_seen.get(name,0) > MISSING_GRACE_SECONDS:
                            first_seen.pop(name,None)
                            last_seen.pop(name,None)
                    labels = [(name, max(0,HOLD_SECONDS-(now-first_seen[name]))) for name in present if name not in seen_classes and name in first_seen]
                annotated = result.plot()
                for idx, (name, remain) in enumerate(labels[:6]):
                    cv2.putText(annotated, f'{name[:24]}: {remain:.1f}s', (12,32+idx*26), cv2.FONT_HERSHEY_SIMPLEX,0.58,(0,255,255),2)
                success, jpeg = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY),75])
                if success:
                    with lock:
                        latest_jpeg = jpeg.tobytes()
        finally:
            cap.release()
    except Exception as exc:
        camera_status = f'error: {exc}'
        print('CAMERA WORKER ERROR:',exc,flush=True)


@app.on_event('startup')
def startup():
    global products
    products = load_products()
    Thread(target=worker, daemon=True).start()


@app.get('/api/health')
def health():
    return {'status':'ok','camera':camera_status,'model_path':str(MODEL),'product_count':len(products)}


@app.get('/api/products')
def list_products():
    return list(products.values())


@app.get('/api/cart')
def get_cart():
    with lock:
        return cart_snapshot()


@app.get('/api/video')
def video():
    def stream():
        while True:
            with lock:
                frame = latest_jpeg
            if frame:
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'+frame+b'\r\n'
            time.sleep(0.05)
    return StreamingResponse(stream(), media_type='multipart/x-mixed-replace; boundary=frame')


@app.delete('/api/cart/{item_id}')
def delete_item(item_id: str):
    with lock:
        item = next((x for x in cart if x['id']==item_id),None)
        if item is None:
            raise HTTPException(404,'Item not found')
        if item['in_basket']:
            raise HTTPException(409,'Physical basket exit must be verified before deletion')
        cart.remove(item)
        return {'status':'removed','cart':cart_snapshot()}


@app.post('/api/cart/reset')
def reset_cart():
    # Demo/session reset only. Never interpret as physical basket removal.
    with lock:
        cart.clear()
        seen_classes.clear()
        first_seen.clear()
        last_seen.clear()
        return cart_snapshot()
