import xgboost as xgb
import pandas as pd

# ✅ Load the trained XGBoost model
model = xgb.Booster()
model.load_model("models/xgboost_energy_model.json")
print("✅ Model loaded successfully!")

# ✅ Load new input data
new_data = pd.read_csv("data/energy_dataa.csv")  

# ✅ Drop 'energy_consumption' if it exists
if "energy_consumption" in new_data.columns:
    new_data = new_data.drop(columns=["energy_consumption"])

# ✅ Ensure "usage_hours" exists
if "usage_hours" not in new_data.columns:
    print("❌ Error: 'usage_hours' column not found in dataset!")
    exit()

# ✅ Convert new data to XGBoost's required format
dtest = xgb.DMatrix(new_data)

# ✅ Make Predictions for Original Energy Consumption
predictions = model.predict(dtest)

# ✅ Define Load Shift Logic Based on Usage Hours
shifted_hours = 1  # 🔹 Assume shifting 2 hours to non-peak time
new_data["effective_usage_hours"] = new_data["usage_hours"] - shifted_hours

# ✅ Ensure effective usage hours don't go below 1
new_data["effective_usage_hours"] = new_data["effective_usage_hours"].clip(lower=1)

# ✅ Compute Reduction Factor (Based on Usage Hours)
new_data["reduction_factor"] = new_data["effective_usage_hours"] / new_data["usage_hours"]

# ✅ Apply Reduction Dynamically
new_data["reduced_energy_consumption"] = predictions * new_data["reduction_factor"]

# ✅ Ensure No Negative or Unrealistic Values
new_data["reduced_energy_consumption"] = new_data["reduced_energy_consumption"].clip(lower=0)

# ✅ Debug: Print Before & After (First 10 Rows)
print("\n🔍 Original vs Reduced Predictions (First 10 Rows):")
for i in range(10):
    print(f"Original: {predictions[i]:.4f} → Reduced: {new_data['reduced_energy_consumption'].iloc[i]:.4f}")

# ✅ Save Predictions to CSV
new_data["predicted_energy_consumption"] = predictions  # Save original predictions
new_data.to_csv("data/reduced_predictions4.csv", index=False)

print("🚀 Reduced Predictions saved successfully in data/reduced_predictions3.csv!")