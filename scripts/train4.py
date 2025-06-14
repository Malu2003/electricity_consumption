import pandas as pd
import xgboost as xgb
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
from sqlalchemy import create_engine

# Load dataset
DATA_PATH = "data/energy_dataa.csv"
data = pd.read_csv(DATA_PATH)

# Drop unnecessary columns & handle missing values
data = data.drop(columns=['ages'], errors='ignore')
data = data.fillna(data.median())

# Define Features (X) and Target Variable (Y)
X = data.drop(columns=['energy_consumption'])
y = data['energy_consumption']

# Split dataset (80% train, 20% test)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Define models
xgb_model = xgb.XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=8, min_child_weight=5, 
                             subsample=0.8, colsample_bytree=0.8, gamma=0.2, objective='reg:squarederror', 
                             random_state=42)
xgb_model.fit(X_train, y_train)

# Save model
MODEL_PATH = "xgboost_energy_model.pkl"
joblib.dump(xgb_model, MODEL_PATH)
print(f"Model saved as {MODEL_PATH}")

# ---------------------------------------------
# PREDICTION SCRIPT
# ---------------------------------------------

# Load trained model
model = joblib.load(MODEL_PATH)

db_url = "postgresql+psycopg2://postgres:tangumalu@localhost/seven"
engine = create_engine(db_url)

query = """
SELECT u.consumer_number, u.family_members, u.working_members, 
       COALESCE(b.units_consumed, 0) AS units_consumed, 
       COALESCE(b.cost_per_unit, 0) AS cost_per_unit,
       a.appliance_name, a.usage_hours, u.location
FROM users u
LEFT JOIN bills b ON u.consumer_number = b.consumer_number
LEFT JOIN appliances a ON u.consumer_number = a.consumer_number;
"""
df = pd.read_sql_query(query, engine)

# Load additional datasets
appliance_data = pd.read_csv("data/household.csv")
electricity_data = pd.read_csv("data/electricity1.csv")

# Standardize column names and clean strings
df['appliance_name'] = df['appliance_name'].str.strip().str.lower()
appliance_data['appliance_name'] = appliance_data['appliance_name'].str.strip().str.lower()
df['location'] = df['location'].str.strip().str.lower()
electricity_data['location'] = electricity_data['location'].str.strip().str.lower()

# Merge appliance data
df = df.merge(appliance_data[['appliance_name', 'Power_Rating_W', 'Units_Consumed_Per_Hour_kWh']],
              on='appliance_name', how='left')

# Merge electricity data
df = df.merge(electricity_data[['location', 'Base Tariff (cents/kWh)', 'Final Per Unit Cost (cents/kWh)']],
              on='location', how='left')

# Fill missing values
df['Power_Rating_W'].fillna(0, inplace=True)
df['Units_Consumed_Per_Hour_kWh'].fillna(0, inplace=True)
df["usage_hours"].fillna(0, inplace=True)
df["units_consumed"].fillna(0, inplace=True)

# FIXED: Aggregate data per user
df = df.groupby('consumer_number', as_index=False).agg({
    'family_members': 'first',
    'working_members': 'first',
    'units_consumed': 'sum',   # Sum of all appliance usage per user
    'cost_per_unit': 'first',
    'usage_hours': 'sum',  # Sum of all usage hours per user
    'Power_Rating_W': 'sum', 
    'Units_Consumed_Per_Hour_kWh': 'sum', 
    'location': 'first'
})

# Ensure all required features are present
expected_features = list(X_train.columns)
for col in expected_features:
    if col not in df.columns:
        df[col] = 0

# Ensure column order matches training data
df = df[expected_features]

# Make predictions
df["energy_consumption"] = model.predict(df)
df["carbon_footprint"] = df["energy_consumption"] * 0.82
df["bill_amount"] = df["energy_consumption"] * df["cost_per_unit"]

# Display final output
pd.set_option('display.max_columns', None)
print(df)
