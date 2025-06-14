import pandas as pd
import xgboost as xgb
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
from sklearn.ensemble import StackingRegressor, RandomForestRegressor
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
rf_model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42)

# Stacking Model: XGBoost + Random Forest
stacked_model = StackingRegressor(estimators=[('xgb', xgb_model), ('rf', rf_model)],
                                  final_estimator=xgb.XGBRegressor(n_estimators=100, learning_rate=0.05, 
                                                                   max_depth=6, random_state=42))
stacked_model.fit(X_train, y_train)

# Evaluate Model
y_pred = stacked_model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
print(f"Mean Absolute Error: {mae}\nRoot Mean Squared Error: {rmse}")

# Save model
MODEL_PATH = "stacked_energy_model.pkl"
joblib.dump(stacked_model, MODEL_PATH)
print(f"Model saved as {MODEL_PATH}")

# ---------------------------------------------
# PREDICTION SCRIPT
# ---------------------------------------------

# Load trained model
model = joblib.load(MODEL_PATH)

db_url = "postgresql+psycopg2://postgres:tangumalu@localhost/seven"
engine = create_engine(db_url)

query = """
SELECT u.consumer_number, u.family_members, u.working_members, u.ages, 
       COALESCE(b.units_consumed, 0) AS units_consumed, 
       COALESCE(b.cost_per_unit, 0) AS cost_per_unit,
       SUM(a.usage_hours) AS total_usage_hours,
       LOWER(TRIM(a.appliance_name)) AS appliance_name, 
       u.location
FROM users u
LEFT JOIN bills b ON u.consumer_number = b.consumer_number
LEFT JOIN appliances a ON u.consumer_number = a.consumer_number
GROUP BY u.consumer_number, u.family_members, u.working_members, u.ages, 
         b.units_consumed, b.cost_per_unit, u.location, a.appliance_name;
"""
df = pd.read_sql_query(query, engine)

def process_ages(age_data):
    try:
        return float(age_data) if isinstance(age_data, (int, float)) else np.nan
    except:
        return np.nan

df["ages"] = df["ages"].apply(process_ages)

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
df["total_usage_hours"].fillna(0, inplace=True)
df["units_consumed"].fillna(0, inplace=True)

# Convert categorical features into numerical
df = pd.get_dummies(df, columns=["appliance_name", "location"], drop_first=True)

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

df = df.drop_duplicates(subset=['consumer_number'])
pd.set_option('display.max_columns', None)
print(df)
