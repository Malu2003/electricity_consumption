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

print("Initial dataset columns:", data.columns)

data = data.drop(columns=['ages'], errors='ignore')

data.fillna(data.select_dtypes(include=[np.number]).median(), inplace=True)

# Define Features (X) and Target Variable (Y)
X = data.drop(columns=['energy_consumption'])
y = data['energy_consumption']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Define models
xgb_model = xgb.XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=8, min_child_weight=5, 
                             subsample=0.8, colsample_bytree=0.8, gamma=0.2, objective='reg:squarederror', 
                             random_state=42)
rf_model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42)

stacked_model = StackingRegressor(estimators=[('xgb', xgb_model), ('rf', rf_model)],
                                  final_estimator=xgb.XGBRegressor(n_estimators=100, learning_rate=0.05, 
                                                                   max_depth=6, random_state=42))

stacked_model.fit(X_train, y_train)

y_pred = stacked_model.predict(X_test)
print(f"MAE: {mean_absolute_error(y_test, y_pred)}")
print(f"RMSE: {np.sqrt(mean_squared_error(y_test, y_pred))}")

# Save model
MODEL_PATH = "stacked_energy_model.pkl"
joblib.dump(stacked_model, MODEL_PATH)

# Load trained model
model = joblib.load(MODEL_PATH)

db_url = "postgresql+psycopg2://postgres:tangumalu@localhost/seven"
engine = create_engine(db_url)

query = """
SELECT u.consumer_number, u.family_members, u.working_members, u.ages, 
       COALESCE(b.units_consumed, 0) AS units_consumed, 
       COALESCE(b.cost_per_unit, 0) AS cost_per_unit,
       COALESCE(a.usage_hours, 0) AS usage_hours,
       LOWER(TRIM(a.appliance_name)) AS appliance_name, 
       u.location
FROM users u
LEFT JOIN bills b ON u.consumer_number = b.consumer_number
LEFT JOIN appliances a ON u.consumer_number = a.consumer_number;
"""

df = pd.read_sql_query(query, engine)
print("Columns retrieved from database:", df.columns)

def process_ages(age_data):
    try:
        return float(age_data) if isinstance(age_data, (int, float)) else np.nan
    except:
        return np.nan

df["ages"] = df["ages"].apply(process_ages)

if 'usage_hours' in df.columns:
    total_usage_hours = df.groupby('consumer_number', as_index=False)['usage_hours'].sum()
    total_usage_hours.rename(columns={'usage_hours': 'total_usage_hours'}, inplace=True)
    df = df.merge(total_usage_hours, on='consumer_number', how='left')
    df["total_usage_hours"].fillna(0, inplace=True)
else:
    df["total_usage_hours"] = 0

print("Columns after merging total_usage_hours:", df.columns)

appliance_data = pd.read_csv("data/household.csv")
electricity_data = pd.read_csv("data/electricity1.csv")

df['appliance_name'] = df['appliance_name'].str.strip().str.lower()
appliance_data['appliance_name'] = appliance_data['appliance_name'].str.strip().str.lower()
df['location'] = df['location'].str.strip().str.lower()
electricity_data['location'] = electricity_data['location'].str.strip().str.lower()

df = df.merge(appliance_data[['appliance_name', 'Power_Rating_W', 'Units_Consumed_Per_Hour_kWh']],
              on='appliance_name', how='left')
df = df.merge(electricity_data[['location', 'Base Tariff (cents/kWh)', 'Final Per Unit Cost (cents/kWh)']],
              on='location', how='left')

df.fillna({'Power_Rating_W': 0, 'Units_Consumed_Per_Hour_kWh': 0, 'units_consumed': 0, 'cost_per_unit': 0}, inplace=True)

df = pd.get_dummies(df, columns=["appliance_name", "location"], drop_first=True)

# Ensure all required features are present
expected_features = list(X_train.columns)
for col in expected_features:
    if col not in df.columns:
        df[col] = 0

df = df[expected_features]  # Ensure correct column order

print("Columns in DataFrame before prediction:", df.columns)

try:
    df["energy_consumption"] = model.predict(df)
except Exception as e:
    print("Prediction error:", e)

if "total_usage_hours" not in df.columns:
    print("Warning: 'total_usage_hours' column is missing!")
    df["total_usage_hours"] = 1

print("Final DataFrame columns before calculations:", df.columns)

df["effective_usage_hours"] = np.maximum(df["total_usage_hours"].replace(0, 1) - 1, 0.1)
df["reduction_factor"] = df["effective_usage_hours"] / df["total_usage_hours"].replace(0, 1)
df["reduction_factor"].fillna(1, inplace=True)

df["reduced_consumption"] = df["energy_consumption"] * df["reduction_factor"]
df["reduced_consumption"] = df["reduced_consumption"].clip(lower=0)

df["carbon_footprint"] = df["energy_consumption"] * 0.82
df["reduced_carbon_footprint"] = df["reduced_consumption"] * 0.82
df["bill_amount"] = df["energy_consumption"] * 8
df["reduced_bill"] = df["reduced_consumption"] * 8
df = df.drop_duplicates()
print(df)