from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import keras
import joblib
import pandas as pd
import numpy as np
import os

# ── Config ──────────────────────────────────────────────────────────────────
MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(os.path.dirname(__file__), "models"))
DATA_PATH = os.getenv("DATA_PATH", "")

app = FastAPI(
    title="Medicine Price Prediction API",
    description="Search, filter, and price-predict Indian pharmaceutical products.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Globals ──────────────────────────────────────────────────────────────────
model = None
scaler = None
le_class = None
le_ing = None
le_dosage = None
df: pd.DataFrame = None

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def load_resources():
    global model, scaler, le_class, le_ing, le_dosage, df

    MODEL_PATH    = os.path.join(MODEL_DIR, "medicine_price_model.keras")
    SCALER_PATH   = os.path.join(MODEL_DIR, "scaler.joblib")
    LE_CLASS_PATH = os.path.join(MODEL_DIR, "le_class.joblib")
    LE_ING_PATH   = os.path.join(MODEL_DIR, "le_ing.joblib")
    LE_DOSAGE_PATH= os.path.join(MODEL_DIR, "le_dosage.joblib")
    CSV_PATH      = os.path.join(MODEL_DIR, "medicines.csv")

    # Load ML model
    try:
        if os.path.exists(MODEL_PATH):
            model     = keras.models.load_model(MODEL_PATH)
            scaler    = joblib.load(SCALER_PATH)
            le_class  = joblib.load(LE_CLASS_PATH)
            le_ing    = joblib.load(LE_ING_PATH)
            le_dosage = joblib.load(LE_DOSAGE_PATH)
            print("✅ Model components loaded.")
        else:
            print(f"⚠️  Model not found at {MODEL_PATH}. Run notebook export cell first.")
    except Exception as e:
        print(f"❌ Error loading model: {e}")

    # Load medicine dataset
    csv_candidates = [
        CSV_PATH,
        DATA_PATH,
        os.path.expanduser("~/Downloads/indian_pharmaceutical_products_clean.csv"),
    ]
    for path in csv_candidates:
        if path and os.path.exists(path):
            try:
                raw = pd.read_csv(path)
                # Apply same cleaning as notebook
                raw = raw[raw["is_discontinued"] == False]
                raw = raw[raw["primary_strength"].notna()]
                raw["primary_ingredient"] = raw["primary_ingredient"].str.strip().str.lower()
                raw["primary_strength"]   = raw["primary_strength"].str.strip().str.lower()
                raw["dosage_form"]        = raw["dosage_form"].str.strip().str.lower()
                raw["brand_name"]         = raw["brand_name"].str.strip()
                raw.reset_index(drop=True, inplace=True)

                import re
                def extract_strength(v):
                    m = re.search(r"\d+\.?\d*", str(v))
                    return float(m.group()) if m else None

                raw["strength_numeric"] = raw["primary_strength"].apply(extract_strength)
                raw = raw[raw["strength_numeric"].notna()]

                # Cap price outliers at 99th percentile
                upper = raw["price_inr"].quantile(0.99)
                raw = raw[raw["price_inr"] <= upper]

                # Add predicted "fair value" price via model or rule-based fallback
                def try_model_predictions(raw):
                    """Try Keras model first; return None array if model weights are NaN."""
                    if model is None or scaler is None:
                        return None
                    try:
                        raw["therapeutic_class"] = raw["therapeutic_class"].str.strip().str.lower()
                        known_classes = set(le_class.classes_)
                        known_ings    = set(le_ing.classes_)
                        known_dosages = set(le_dosage.classes_)
                        mask = (
                            raw["therapeutic_class"].isin(known_classes) &
                            raw["primary_ingredient"].isin(known_ings) &
                            raw["dosage_form"].isin(known_dosages)
                        )
                        preds_col = np.full(len(raw), np.nan)
                        sub = raw[mask].copy()
                        if len(sub) == 0:
                            return None
                        X = pd.DataFrame({
                            "class_enc":              le_class.transform(sub["therapeutic_class"].values),
                            "ing_enc":                le_ing.transform(sub["primary_ingredient"].values),
                            "dosage_enc":             le_dosage.transform(sub["dosage_form"].values),
                            "pack_size":              sub["pack_size"].fillna(0).values.astype(float),
                            "num_active_ingredients": sub["num_active_ingredients"].fillna(1).values.astype(float),
                            "strength_numeric":       sub["strength_numeric"].fillna(0).values.astype(float),
                        })
                        X_scaled = scaler.transform(X)
                        log_preds = model.predict(X_scaled, verbose=0).flatten()
                        preds = np.clip(np.expm1(log_preds), 0, None)
                        # Reject if model weights are NaN (bad checkpoint)
                        if np.isnan(preds).all():
                            print("⚠️  Model returned all-NaN predictions — using rule-based fallback.")
                            return None
                        preds_col[np.where(mask)[0]] = preds
                        return preds_col
                    except Exception as e:
                        print(f"⚠️  Model prediction error: {e}")
                        return None

                model_preds = try_model_predictions(raw)

                if model_preds is not None and not np.isnan(model_preds).all():
                    raw["predicted_price"] = model_preds
                    print(f"✅ Model predictions generated for {(~np.isnan(model_preds)).sum()}/{len(raw)} medicines.")
                else:
                    # Rule-based fallback: median price per ingredient+dosage group, scaled by strength
                    print("ℹ️  Using rule-based group median as AI Fair Value estimate.")
                    raw["therapeutic_class"] = raw["therapeutic_class"].str.strip().str.lower()
                    group_median = raw.groupby(["primary_ingredient", "dosage_form"])["price_inr"].transform("median")
                    group_med_str = raw.groupby(["primary_ingredient", "dosage_form"])["strength_numeric"].transform("median")
                    strength_ratio = (raw["strength_numeric"] / group_med_str.replace(0, 1)).clip(0.1, 10)
                    raw["predicted_price"] = (group_median * strength_ratio).round(2)
                    print(f"✅ Rule-based estimates computed for {raw['predicted_price'].notna().sum()}/{len(raw)} medicines.")

                df = raw.reset_index(drop=True)
                print(f"✅ Dataset loaded: {len(df)} medicines from {path}")
                break
            except Exception as e:
                print(f"❌ Could not load CSV from {path}: {e}")

    if df is None:
        print("⚠️  No dataset loaded. Search endpoints will return empty results.")


# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def medicines_to_json(subset: pd.DataFrame, limit: int = 50) -> list:
    cols = ["brand_name", "manufacturer", "price_inr", "predicted_price",
            "primary_ingredient", "primary_strength", "strength_numeric",
            "dosage_form", "therapeutic_class", "pack_size", "pack_unit"]
    out = []
    for _, row in subset.head(limit).iterrows():
        record = {}
        for c in cols:
            if c in row:
                val = row[c]
                if isinstance(val, float) and np.isnan(val):
                    val = None
                elif hasattr(val, "item"):
                    val = val.item()
                record[c] = val
        out.append(record)
    return out


# ── Endpoints ─────────────────────────────────────────────────────────────────

# Route previously defined here was removed to avoid conflict with frontend index.html


@app.get("/strength-range")
def strength_range():
    """Returns min/max strength_numeric for the slider bounds."""
    if df is None:
        return {"min": 0, "max": 1000}
    return {
        "min": float(df["strength_numeric"].min()),
        "max": float(df["strength_numeric"].max()),
    }


@app.get("/search")
def search_medicines(
    q: str = Query(default="", description="Search by brand name or ingredient"),
    mg_min: float = Query(default=None, description="Minimum dose (mg)"),
    mg_max: float = Query(default=None, description="Maximum dose (mg)"),
    sort: str = Query(default="price_asc", description="Sort: price_asc | price_desc | predicted_asc"),
    limit: int = Query(default=50, ge=1, le=200),
):
    if df is None:
        return {"results": [], "total": 0, "message": "Dataset not loaded on server."}

    subset = df.copy()

    # Text filter
    if q.strip():
        q_low = q.strip().lower()
        mask = (
            subset["brand_name"].str.lower().str.contains(q_low, na=False) |
            subset["primary_ingredient"].str.lower().str.contains(q_low, na=False)
        )
        subset = subset[mask]

    # mg range filter
    if mg_min is not None:
        subset = subset[subset["strength_numeric"] >= mg_min]
    if mg_max is not None:
        subset = subset[subset["strength_numeric"] <= mg_max]

    # Sort
    if sort == "price_desc":
        subset = subset.sort_values("price_inr", ascending=False)
    elif sort == "predicted_asc":
        subset = subset.sort_values("predicted_price", ascending=True)
    else:  # default: price_asc
        subset = subset.sort_values("price_inr", ascending=True)

    total = len(subset)
    results = medicines_to_json(subset, limit=limit)
    return {"results": results, "total": total}


# ── Price Prediction ───────────────────────────────────────────────────────────
class MedicineFeatures(BaseModel):
    therapeutic_class: str
    primary_ingredient: str
    dosage_form: str
    pack_size: float
    num_active_ingredients: int
    strength_numeric: float


@app.post("/predict")
def predict_price(features: MedicineFeatures):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded.")
    try:
        class_val  = features.therapeutic_class.strip().lower()
        ing_val    = features.primary_ingredient.strip().lower()
        dosage_val = features.dosage_form.strip().lower()
        try:
            class_enc  = le_class.transform([class_val])[0]
            ing_enc    = le_ing.transform([ing_val])[0]
            dosage_enc = le_dosage.transform([dosage_val])[0]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid categorical value: {e}")

        X = np.array([[class_enc, ing_enc, dosage_enc,
                       features.pack_size, features.num_active_ingredients, features.strength_numeric]])
        X_scaled = scaler.transform(X)
        log_pred = model.predict(X_scaled, verbose=0)
        actual_price = float(np.expm1(log_pred)[0][0])
        return {"predicted_price_inr": round(actual_price, 2), "currency": "INR"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")


# ── Serve Frontend ─────────────────────────────────────────────────────────────
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))

# Mount remaining static files (css, js, images) at / as fallback
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
