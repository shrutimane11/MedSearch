"""
Fixed Medicine Price Prediction Training Script
Fixes applied vs original notebook:
  1. Log-transform target (np.log1p) to fix NaN weights from exploding gradients
  2. Lowercase therapeutic_class (missing in original)
  3. Cap price outliers at 99th percentile BEFORE training
  4. BatchNormalization for more stable training
  5. EarlyStopping with restore_best_weights
  6. Use keras.Input() instead of deprecated input_shape=
  7. Export all artifacts to backend/models/
"""
import os
import re
import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # Suppress TF warnings
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, callbacks

# ── Config ────────────────────────────────────────────────────────────────────
DATA_PATH  = os.path.join(os.path.dirname(__file__), "indian_pharmaceutical_products_clean.csv")
MODEL_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

print(f"TensorFlow version: {tf.__version__}")
print(f"Loading data from: {DATA_PATH}")

# ── 1. Load & Clean ───────────────────────────────────────────────────────────
df = pd.read_csv(DATA_PATH)
print(f"Raw shape: {df.shape}")

df = df[df["is_discontinued"] == False]
df = df[df["primary_strength"].notna()]
df = df[df["price_inr"].notna()]
df = df[df["therapeutic_class"].notna()]

# Normalize ALL text columns (therapeutic_class was MISSING in original notebook)
df["primary_ingredient"]  = df["primary_ingredient"].str.strip().str.lower()
df["primary_strength"]    = df["primary_strength"].str.strip().str.lower()
df["dosage_form"]         = df["dosage_form"].str.strip().str.lower()
df["therapeutic_class"]   = df["therapeutic_class"].str.strip().str.lower()  # ← FIX #1
df["brand_name"]          = df["brand_name"].str.strip()
df.reset_index(drop=True, inplace=True)

# Extract numeric strength
def extract_strength(v):
    m = re.search(r"\d+\.?\d*", str(v))
    return float(m.group()) if m else None

df["strength_numeric"] = df["primary_strength"].apply(extract_strength)
df = df[df["strength_numeric"].notna()]

# ── 2. Cap outliers BEFORE training (FIX #2) ──────────────────────────────────
upper = df["price_inr"].quantile(0.99)
df_train = df[df["price_inr"] <= upper].copy()
print(f"Training shape after outlier cap (99th pct=₹{upper:.1f}): {df_train.shape}")

# ── 3. Encode categoricals ────────────────────────────────────────────────────
le_class  = LabelEncoder()
le_ing    = LabelEncoder()
le_dosage = LabelEncoder()

df_train["class_enc"]  = le_class.fit_transform(df_train["therapeutic_class"])
df_train["ing_enc"]    = le_ing.fit_transform(df_train["primary_ingredient"])
df_train["dosage_enc"] = le_dosage.fit_transform(df_train["dosage_form"])

feature_cols = ["class_enc", "ing_enc", "dosage_enc",
                "pack_size", "num_active_ingredients", "strength_numeric"]
X = df_train[feature_cols].fillna(0)

# ── 4. Log-transform target (FIX #3 — prevents NaN weights) ─────────────────
y = np.log1p(df_train["price_inr"])
print(f"Target (log scale) — min: {y.min():.3f}, max: {y.max():.3f}, "
      f"mean: {y.mean():.3f}")

# ── 5. Scale features ─────────────────────────────────────────────────────────
scaler   = StandardScaler()
X_scaled = scaler.fit_transform(X)

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42
)
print(f"Train: {X_train.shape}, Test: {X_test.shape}")

# ── 6. Build model ────────────────────────────────────────────────────────────
model = keras.Sequential([
    keras.Input(shape=(X_train.shape[1],)),   # FIX #4: use Input() not input_shape=
    layers.Dense(128, activation="relu"),
    layers.BatchNormalization(),              # FIX #5: stabilizes training
    layers.Dense(64, activation="relu"),
    layers.Dense(32, activation="relu"),
    layers.Dense(1)
], name="medicine_price_model")

model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=0.001),
    loss="mse",
    metrics=["mae"]
)
model.summary()

# ── 7. Train with EarlyStopping ───────────────────────────────────────────────
es = callbacks.EarlyStopping(
    monitor="val_loss",
    patience=8,
    restore_best_weights=True,
    verbose=1
)
lr_reduce = callbacks.ReduceLROnPlateau(
    monitor="val_loss", factor=0.5, patience=4, min_lr=1e-6, verbose=1
)

print("\nTraining started...")
history = model.fit(
    X_train, y_train,
    validation_split=0.2,
    epochs=100,
    batch_size=256,
    callbacks=[es, lr_reduce],
    verbose=1
)

# ── 8. Evaluate ───────────────────────────────────────────────────────────────
loss, mae = model.evaluate(X_test, y_test, verbose=0)
print(f"\nTest MAE  (log scale): {mae:.4f}")
print(f"Approx price error  : ≈ ₹{np.expm1(mae):.2f} (multiplicative)")

# Sample predictions
y_pred_log = model.predict(X_test[:5], verbose=0).flatten()
y_pred     = np.expm1(y_pred_log)
y_actual   = np.expm1(y_test.iloc[:5].values)
print("\nSample predictions vs actual:")
for pred, actual in zip(y_pred, y_actual):
    print(f"  Predicted ₹{pred:.2f}  |  Actual ₹{actual:.2f}")

# ── 9. Save all artifacts ─────────────────────────────────────────────────────
model_path    = os.path.join(MODEL_DIR, "medicine_price_model.keras")
scaler_path   = os.path.join(MODEL_DIR, "scaler.joblib")
le_class_path = os.path.join(MODEL_DIR, "le_class.joblib")
le_ing_path   = os.path.join(MODEL_DIR, "le_ing.joblib")
le_dosage_path= os.path.join(MODEL_DIR, "le_dosage.joblib")
csv_path      = os.path.join(MODEL_DIR, "medicines.csv")

model.save(model_path)
joblib.dump(scaler,   scaler_path)
joblib.dump(le_class, le_class_path)
joblib.dump(le_ing,   le_ing_path)
joblib.dump(le_dosage,le_dosage_path)
df.to_csv(csv_path, index=False)

print(f"\n✅ All artifacts saved to {MODEL_DIR}/")
print(f"   model:    {model_path}")
print(f"   scaler:   {scaler_path}")
print(f"   le_class: {le_class_path}")
print(f"   le_ing:   {le_ing_path}")
print(f"   le_dosage:{le_dosage_path}")
print(f"   dataset:  {csv_path}")

# Verify model weights are not NaN
all_nan = all(
    np.isnan(w.numpy()).all()
    for layer in model.layers for w in layer.weights
)
print(f"\n{'❌ WARNING: Model weights contain NaN!' if all_nan else '✅ Model weights are valid (no NaN).'}")
