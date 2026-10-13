
import joblib
from pathlib import Path

model_path = (
    Path(__file__).parent
    / "models"
    / "comp4_recommendation_model.joblib"
)

print("Model path:", model_path)
print("File exists:", model_path.exists())

model_package = joblib.load(model_path)

model = model_package["model"]
feature_columns = model_package["feature_columns"]

print("\nModel loaded successfully!")
print("Model type:", type(model).__name__)
print("Required features:", feature_columns)

import pandas as pd

sample = pd.DataFrame([{
    "past_purchase_count": 5,
    "total_quantity": 8,
    "days_since_last_purchase": 3,
    "category_purchase_count": 10
}])[feature_columns]

prediction = model.predict_proba(sample)[0, 1]

print("Sample prediction score:", round(float(prediction), 3))
