import pandas as pd
import xgboost as xgb
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
from sklearn.ensemble import StackingRegressor, RandomForestRegressor
from sqlalchemy import create_engine

# -------------------------------
# TRAINING SCRIPT
# -------------------------------

# Load dataset
DATA_PATH = "data/energy_dataa.csv"
data = pd.read_csv(DATA_PATH)

# Drop unnecessary columns & handle missing values
data = data.drop(columns=['ages'], errors='ignore')
data = data.fillna(data.median(numeric_only=True))

# Define Features (X) and Target Variable (Y)
X = data.drop(columns=['energy_consumption'], errors='ignore')
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

# -------------------------------
# PREDICTION SCRIPT
# -------------------------------

# Load trained model
model = joblib.load(MODEL_PATH)

db_url = "postgresql+psycopg2://postgres:tangumalu@localhost/seven"
engine = create_engine(db_url)

query = """
SELECT u.consumer_number, u.family_members, u.working_members, u.ages, 
       COALESCE(b.units_consumed, 0) AS units_consumed, 
       COALESCE(b.cost_per_unit, 0) AS cost_per_unit,
       LOWER(TRIM(a.appliance_name)) AS appliance_name, 
       u.location, a.usage_hours,b.month

FROM users u
LEFT JOIN bills b ON u.consumer_number = b.consumer_number
LEFT JOIN appliances a ON u.consumer_number = a.consumer_number;
"""
df = pd.read_sql_query(query, engine)

# Ensure numeric values are properly handled
df["ages"] = pd.to_numeric(df["ages"], errors='coerce')

df['month'] = df['month'].astype(str)  # Ensure it's a string


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
df[['Power_Rating_W', 'Units_Consumed_Per_Hour_kWh', 'units_consumed', 'usage_hours']] = df[
    ['Power_Rating_W', 'Units_Consumed_Per_Hour_kWh', 'units_consumed', 'usage_hours']
].fillna(0)

# Calculate total usage hours
total_usage_hours = df.groupby('consumer_number', as_index=False)['usage_hours'].sum()
total_usage_hours.rename(columns={'usage_hours': 'total_usage_hours'}, inplace=True)
print("Columns in df after SQL fetch:", df.columns)
print(df.head())  # To check if 'month' exists

# Debugging: Check if total_usage_hours has data
print("total_usage_hours dataframe preview:")
print(total_usage_hours.head())

# Merge total_usage_hours back to the main df
df = df.merge(total_usage_hours, on='consumer_number', how='left')
df['total_usage_hours'] = df['total_usage_hours'].fillna(0)


# Debugging: Check if 'total_usage_hours' exists in df after merge
print("Columns after merging total_usage_hours:", df.columns)
print("Unique values in 'total_usage_hours':", df['total_usage_hours'].unique())

# Drop usage_hours since we now have total_usage_hours
df = df.drop(columns=['usage_hours'], errors='ignore')

# Convert categorical features into numerical
df = pd.get_dummies(df, columns=["appliance_name", "location"], drop_first=True)

# ----------------------------------------------------------------------
# IMPORTANT: Prepare the data for prediction.
# The training features (X_train.columns) likely do NOT include extra columns like total_usage_hours.
# We create a separate dataframe for prediction, then merge the extra columns needed for post-processing.
# ----------------------------------------------------------------------
expected_features = list(X_train.columns)
# Save extra columns needed for post-prediction calculations
extra_columns = ['total_usage_hours', 'working_members', 'family_members', 'cost_per_unit']
df_extra = df[extra_columns].copy()

# Create a dataframe with only the features used for training
df_pred = df.copy()
for col in expected_features:
    if col not in df_pred.columns:
        df_pred[col] = 0
df_pred = df_pred[expected_features]


# Make predictions using the training features
df_pred["energy_consumption"] = model.predict(df_pred)

# Now merge predictions back with the extra data for further calculations
df_final = df_pred.copy()
for col in extra_columns:
    df_final[col] = df_extra[col]
if "month" in df.columns:
    df_final["month"] = df["month"]
else:
    df_final["month"] = "Unknown"  # Handle missing values gracefully


# Compute additional outputs
df_final["carbon_footprint"] = df_final["energy_consumption"] * 0.82
df_final["bill_amount"] = df_final["energy_consumption"] * df_final["cost_per_unit"]

# Effective usage hours calculation with error handling
df_final["effective_usage_hours"] = df_final["total_usage_hours"] * (
    1 - ((df_final["working_members"] * 8 / 24) / (df_final["family_members"] * 24)).fillna(0)
)
df_final["effective_usage_hours"] = df_final["effective_usage_hours"].clip(lower=0)

df_final["reduced_consumption"] = df_final["energy_consumption"] * (
    df_final["effective_usage_hours"] / df_final["total_usage_hours"].replace(0, 1)
)
df_final["reduced_bill_amount"] = df_final["reduced_consumption"] * df_final["cost_per_unit"]
df_final["reduced_carbon_footprint"] = df_final["reduced_consumption"] * 0.82

df_final = df_final.drop_duplicates(subset=['consumer_number'])
pd.set_option('display.max_columns', None)
print(df_final)

# Convert consumer_number to string (remove .0 issue)
df_final["consumer_number"] = df_final["consumer_number"].astype(str).str.replace(r"\.0$", "", regex=True)

print("Columns in df_final after merging:", df_final.columns)
print(df_final.head())  # Check if 'month' still exists

# Insert/Update predictions in the database
from sqlalchemy import text
with engine.connect() as conn:
    for _, row in df_final.iterrows():
        query = text("""
            INSERT INTO predictions (consumer_number, energy_consumption, reduced_consumption,
                                    bill_amount, reduced_bill_amount, carbon_footprint, reduced_carbon_footprint,month)
            VALUES (:consumer_number, :energy_consumption, :reduced_consumption,
                    :bill_amount, :reduced_bill_amount, :carbon_footprint, :reduced_carbon_footprint,:month)
            ON CONFLICT (consumer_number,month)  
            DO UPDATE SET
                energy_consumption = EXCLUDED.energy_consumption,
                reduced_consumption = EXCLUDED.reduced_consumption,
                bill_amount = EXCLUDED.bill_amount,
                reduced_bill_amount = EXCLUDED.reduced_bill_amount,
                carbon_footprint = EXCLUDED.carbon_footprint,
                reduced_carbon_footprint = EXCLUDED.reduced_carbon_footprint;
        """)
        conn.execute(query, row.to_dict())

    conn.commit()

print("✅ Fixed consumer numbers and updated database!")
