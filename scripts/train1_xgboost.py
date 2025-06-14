import pandas as pd
import xgboost as xgb
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
from sklearn.ensemble import StackingRegressor, RandomForestRegressor

# Load dataset (Ensure it has all features needed)
data = pd.read_csv("data/energy_dataa.csv")  # Replace with your dataset filename

# Remove 'ages' column if it exists
data = data.drop(columns=['ages'], errors='ignore')

# Handle missing values (if any)
data = data.fillna(data.median())

# Define Features (X) and Target Variable (Y)
X = data.drop(columns=['energy_consumption'])  # Adjust as per actual target variable name
y = data['energy_consumption']

# Split dataset (80% training, 20% testing)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Define XGBoost Regressor model
xgb_model = xgb.XGBRegressor(
    n_estimators=300,      
    learning_rate=0.05,    
    max_depth=8,           
    min_child_weight=5,    
    subsample=0.8,         
    colsample_bytree=0.8,  
    gamma=0.2,             
    objective='reg:squarederror',
    random_state=42
)

# Define Random Forest Regressor model
rf_model = RandomForestRegressor(
    n_estimators=200, 
    max_depth=10, 
    random_state=42
)

# Stacking Model: XGBoost + Random Forest
stacked_model = StackingRegressor(
    estimators=[('xgb', xgb_model), ('rf', rf_model)],
    final_estimator=xgb.XGBRegressor(n_estimators=100, learning_rate=0.05, max_depth=6, random_state=42)
)

# Train the stacked model
stacked_model.fit(X_train, y_train)

# Predictions
y_pred = stacked_model.predict(X_test)

# Evaluate the model
mae = mean_absolute_error(y_test, y_pred)
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)

print(f"Model Performance:")
print(f"Mean Absolute Error: {mae}")
print(f"Root Mean Squared Error: {rmse}")

# Save trained model
joblib.dump(stacked_model, "stacked_energy_model1.pkl")

print("Model training completed. Model saved as 'stacked_energy_model1.pkl'.")
