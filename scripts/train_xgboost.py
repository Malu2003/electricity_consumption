import pandas as pd
import xgboost as xgb
import sklearn
import sklearn.metrics
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import inspect
import os

# ✅ Ensure 'models' directory exists
os.makedirs("models", exist_ok=True)
print(inspect.signature(mean_squared_error))
# ✅ Load theo dataset
df = pd.read_csv("data/energy_dataa.csv")

# ✅ Define Features (X) and Target (y)
X = df.drop(columns=["energy_consumption"])  # Features
y = df["energy_consumption"]  # Target variable

# ✅ Split into Training & Testing Sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# ✅ Train the XGBoost Model
model = xgb.XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5)
model.fit(X_train, y_train)

# ✅ Make Predictions
y_pred = model.predict(X_test)

# ✅ Evaluate Model Performance
mae = mean_absolute_error(y_test, y_pred)
rmse = mean_squared_error(y_test, y_pred)**0.5

print(f"Mean Absolute Error: {mae}")
print(f"Root Mean Squared Error: {rmse}")

# ✅ Save the Model
model.save_model("models/xgboost_energy_model.json")
print("Model saved successfully!")
