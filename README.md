![WhatsApp Image 2026-04-15 at 11 56 22 AM](https://github.com/user-attachments/assets/5dba2672-fb3d-4286-8a58-642fb72205c4)



![WhatsApp Image 2026-04-15 at 11 56 06 AM](https://github.com/user-attachments/assets/de56495f-977c-4e1e-857a-7751bb352d6b)




#MedSearch: India's AI-Powered Medicine Price Predictor

MedSearch is a full-stack web application designed to help consumers find the best deals on medicines in India. It does this by combining a robust search engine over a dataset of ~220,000 Indian pharmaceutical products with a deep learning Neural Network (Keras) that predicts the **"AI Fair Value"** of any medicine.

##  Features

- **Blazing Fast Offline Search**: Instantly filter across hundreds of thousands of medicines by brand name or active ingredient using a local dataset (no live web-scraping).
- **Dose Range Filtering**: Precise dual-handle slider to filter results by exact mg strengths.
- **✨ AI Fair Value Generation**: A trained Keras neural network analyzes the medicine's therapeutic class, chemical ingredients, and dosage form to estimate the "true market value" of the medicine.
- **Deal Indicator Badges**: 
  - 🟢 **Great Deal**: The listed price is significantly cheaper than the AI's market estimate.
  - ⬛ **Premium Brand**: The listed price carries a premium markup over the typical market rate.
- **Premium UI**: A clean, pastel-themed interface that offers a seamless user experience.


The core intelligence of MedSearch is a Deep Neural Network trained on the `indian_pharmaceutical_products_clean.csv` dataset.

1. **Features**: It learns from the medicine's `therapeutic_class`, `primary_ingredient`, `dosage_form`, `pack_size`, `num_active_ingredients`, and `strength_numeric`.
2. **Preprocessing**: Text parameters are encoded using `LabelEncoder`, and all numerical features are scaled using `StandardScaler`.
3. **Training**: The model is trained using TensorFlow/Keras on a log-transformed price (`np.log1p`) to handle extreme outliers in pharmaceutical pricing, using `BatchNormalization` and `EarlyStopping` for stable convergence.
4. **Prediction**: When you search for a medicine, the backend passes its chemical profile through the neural network. The network outputs a predicted price — essentially saying, _"Based on the chemical makeup of this drug, the market average price is ₹X."_

This benchmark allows the UI to highlight when a specific brand is offering a "Great Deal" compared to the market average!

---


- Python 3.9+ (Python 3.13 recommended)

### One-Click Setup (Mac / Linux / Windows)

Open a terminal and navigate to the project root directory.

**1. Create a virtual environment and install dependencies:**
```bash
python3 -m venv venv

# On Mac/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

pip install -r backend/requirements.txt
```

**2. Start the App:**
```bash
python3 start_app.py
```
*This single script will automatically launch the backend server, load the Keras AI model, serve the `frontend` HTML/CSS/JS files directly, and pop open your default web browser to the app.*

### 3. (Optional) Retraining the AI Model

If you want to tweak the neural network architecture or retrain it on a newer dataset:

1. Ensure your virtual environment is activated.
2. Run the provided training script:
```bash
python3 train_model.py
```
This script will:
- Clean and normalize the dataset.
- Remove price outliers (top 1%).
- Train the Keras Sequential model over 100 epochs.
- Export the updated `medicine_price_model.keras`, scalers, and encoders directly into the `backend/models/` directory.

The FastAPI server will automatically detect the changes and reload the new AI brain!

##  Tech Stack

- **Frontend**: HTML5, CSS3 (Custom Properties, Flexbox/Grid), Vanilla JavaScript (ES6+).
- **Backend API**: Python, FastAPI, Uvicorn.
- **Machine Learning**: TensorFlow / Keras, Scikit-Learn, Pandas, NumPy, Joblib.
