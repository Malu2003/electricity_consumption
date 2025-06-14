from sqlalchemy import create_engine
import pandas as pd
import joblib
from sklearn.preprocessing import LabelEncoder, StandardScaler
import numpy as np

# Database connection
DB_URL = "postgresql+psycopg2://postgres:tangumalu@localhost/seven"
engine = create_engine(DB_URL)

# Fetch Data
query = """
SELECT u.consumer_number, u.family_members, u.working_members, u.ages, 
       COALESCE(b.units_consumed, 0) AS units_consumed, 
       COALESCE(b.cost_per_unit, 0) AS cost_per_unit,
       COALESCE(a.usage_hours, 0) AS usage_hours,
       SUM(a.usage_hours) AS total_usage_hours,
       LOWER(TRIM(a.appliance_name)) AS appliance_name, 
       u.location
FROM users u
LEFT JOIN bills b ON u.consumer_number = b.consumer_number
LEFT JOIN appliances a ON u.consumer_number = a.consumer_number
GROUP BY u.consumer_number, u.family_members, u.working_members, u.ages, 
         a.usage_hours, b.units_consumed, b.cost_per_unit, 
         u.location, a.appliance_name;
"""
df = pd.read_sql_query(query, engine)

# Data Preprocessing
df["ages"] = df["ages"].astype(str)
label_encoders = {}
for col in ["ages", "appliance_name", "location"]:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col])
    label_encoders[col] = le

scaler = StandardScaler()
df[["units_consumed", "cost_per_unit", "usage_hours", "total_usage_hours"]] = scaler.fit_transform(
    df[["units_consumed", "cost_per_unit", "usage_hours", "total_usage_hours"]]
)

X = df.drop(columns=["units_consumed"])  # Features
y = df["units_consumed"]  # Target variable

# Train/Test Split
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Load Trained Model
model = joblib.load("xgboost_model.pkl")

# Make Predictions
df["predicted_units"] = model.predict(X)

# WattsNext Prediction Calculations
emission_factor = 0.92  # kg CO₂ per kWh (Fixed India-specific Emission Factor)
per_unit_cost = 7.5  # Example per unit cost (Adjust if dynamic)
df["reduction_factor"] = 0.85  # Example efficiency factor (Adjust as needed)

df["reduced_consumption"] = df["predicted_units"] * df["reduction_factor"]
df["reduced_consumption"] = df["reduced_consumption"].clip(lower=0)

df["carbon_footprint"] = df["predicted_units"] * emission_factor
df["reduced_carbon_footprint"] = df["reduced_consumption"] * emission_factor

df["bill_amount"] = df["predicted_units"] * per_unit_cost
df["reduced_bill"] = df["reduced_consumption"] * per_unit_cost

# Save to Database
df.to_sql("predictions", engine, if_exists="replace", index=False)

# Print Predictions for Verification
print("Predictions:")
print(df[["consumer_number", "predicted_units", "bill_amount", "carbon_footprint", "reduced_consumption", "reduced_bill", "reduced_carbon_footprint" ]].head())
print("Predictions saved successfully!")
