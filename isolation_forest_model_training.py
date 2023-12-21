from sklearn.ensemble import IsolationForest
import numpy as np
from joblib import dump

# Random seed for reproducibility
rng = np.random.RandomState(42)

# Function to generate training data based on sensor ranges
def generate_training_data(range_min, range_max, size=500):
    data = rng.uniform(range_min, range_max, size)
    return data.reshape(-1, 1)

# Generate training data for three sensor types
X_train_temperature = generate_training_data(-45, 45)
X_train_humidity = generate_training_data(30, 90)
X_train_pressure = generate_training_data(10, 50)

# Fit the model for each sensor type
clf_temperature = IsolationForest(n_estimators=50, max_samples='auto', random_state=rng, contamination=0.01)
clf_humidity = IsolationForest(n_estimators=50, max_samples='auto', random_state=rng, contamination=0.01)
clf_pressure = IsolationForest(n_estimators=50, max_samples='auto', random_state=rng, contamination=0.01)

print("Training Isolation Forest model for temperature...")
clf_temperature.fit(X_train_temperature)
print("Model for temperature trained.")

print("Training Isolation Forest model for humidity...")
clf_humidity.fit(X_train_humidity)
print("Model for humidity trained.")

print("Training Isolation Forest model for pressure...")
clf_pressure.fit(X_train_pressure)
print("Model for pressure trained.")

# Save the models
dump(clf_temperature, './isolation_forest_temperature.joblib')
dump(clf_humidity, './isolation_forest_humidity.joblib')
dump(clf_pressure, './isolation_forest_pressure.joblib')

print("All models have been trained and saved.")
