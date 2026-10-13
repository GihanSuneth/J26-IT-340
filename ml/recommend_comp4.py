
from pathlib import Path

import joblib
import pandas as pd


# Locate the saved model.
ML_DIR = Path(__file__).parent
MODEL_PATH = ML_DIR / "models" / "comp4_recommendation_model.joblib"

# Location of the purchase-history dataset.
DATA_PATH = Path(
    r"C:\Users\Ovini\Desktop\Research Project"
    r"\sri_lankan_supermarket_recommendation_dataset_package"
    r"\sri_lankan_supermarket_purchase_history.csv"
)


# Load the trained model.
package = joblib.load(MODEL_PATH)
model = package["model"]
feature_columns = package["feature_columns"]

# Load purchase history.
df = pd.read_csv(DATA_PATH)
df["purchase_date"] = pd.to_datetime(
    df["purchase_date"], errors="coerce"
)

required_columns = {
    "customer_id",
    "transaction_id",
    "purchase_date",
    "product_id",
    "product_name",
    "category",
    "quantity",
}

missing = required_columns - set(df.columns)

if missing:
    raise ValueError(f"Missing dataset columns: {sorted(missing)}")

# Remove rows with invalid dates or missing essential values.
df = df.dropna(
    subset=[
        "customer_id",
        "transaction_id",
        "purchase_date",
        "product_id",
        "product_name",
        "category",
        "quantity",
    ]
).copy()


def recommend_products(customer_id, recommendation_date=None, top_n=5):
    """
    Recommend previously purchased products for one customer.

    If no date is supplied, use today's date.
    Historical evaluation can supply a specific date.
    """

    # Use today's date for normal live recommendations.
    if recommendation_date is None:
        recommendation_date = pd.Timestamp.today().normalize()
    else:
        recommendation_date = pd.Timestamp(recommendation_date)

    # Retrieve this customer's purchase history.
    customer_history = df[
        df["customer_id"].astype(str) == str(customer_id)
    ].copy()

    # Use only purchases made before the recommendation date.
    customer_history = customer_history[
        customer_history["purchase_date"] < recommendation_date
    ].copy()

    if customer_history.empty:
        print(
            f"No purchase history found for {customer_id} "
            f"before {recommendation_date.date()}."
        )
        return pd.DataFrame()

    # Calculate recency relative to the selected date.
    customer_history["days_ago"] = (
        recommendation_date - customer_history["purchase_date"]
    ).dt.days

    # Build product-level features.
    product_stats = customer_history.groupby("product_id").agg(
        product_name=("product_name", "last"),
        category=("category", "last"),
        past_purchase_count=("transaction_id", "nunique"),
        total_quantity=("quantity", "sum"),
        days_since_last_purchase=("days_ago", "min"),
    ).reset_index()

    # Calculate purchase frequency within each category.
    category_counts = customer_history.groupby("category")[
        "transaction_id"
    ].nunique().to_dict()

    product_stats["category_purchase_count"] = (
        product_stats["category"].map(category_counts).fillna(0)
    )

    # Generate model scores using the expected feature order.
    X = product_stats[feature_columns].fillna(0)
    product_stats["score"] = model.predict_proba(X)[:, 1]

    # Rank products by model score, then by recency.
    recommendations = (
        product_stats.sort_values(
            ["score", "days_since_last_purchase"],
            ascending=[False, True],
        )
        .head(top_n)
    )

    return recommendations[
        [
            "product_id",
            "product_name",
            "category",
            "past_purchase_count",
            "days_since_last_purchase",
            "score",
        ]
    ].reset_index(drop=True)


if __name__ == "__main__":
    customer_id = input(
        "Enter a customer ID (example: C0001): "
    ).strip()

    # Leave blank to use today's date automatically.
    date_input = input(
        "Enter recommendation date (YYYY-MM-DD), "
        "or press Enter for today: "
    ).strip()

    if date_input:
        results = recommend_products(customer_id, date_input)
    else:
        results = recommend_products(customer_id)

    if not results.empty:
        print("\nRecommended products:")
        print(results.to_string(index=False))
