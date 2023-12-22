from flask import Flask, jsonify
from flask_cors import CORS, cross_origin
from flask_socketio import SocketIO
from pymongo import MongoClient
from confluent_kafka import Consumer, Producer
from joblib import load
import json
import threading
import os
import random
import time
from dotenv import load_dotenv
from colorama import init, Fore, Style
from flask import Flask, Response, render_template



# Initialize colorama
init(autoreset=True)

# Load environment variables
load_dotenv()



app = Flask(__name__)
CORS(app)  # Initialize CORS with default settings (allow all origins)
socketio = SocketIO(app, cors_allowed_origins="*")

# MongoDB setup
client = MongoClient(os.environ['MONGO_URI'])
db = client.sensor_data

# Ping MongoDB to test the connection
try:
    client.admin.command('ping')
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(f"MongoDB connection error: {e}")

# Load trained models
model_temperature = load('./isolation_forest_temperature.joblib')
model_humidity = load('./isolation_forest_humidity.joblib')
model_pressure = load('./isolation_forest_pressure.joblib')

# Kafka configuration
kafka_conf = {
    'bootstrap.servers': 'kafka:9092',
    'group.id': 'sensor-group',
    'auto.offset.reset': 'earliest'
}
producer = Producer({'bootstrap.servers': 'kafka:9092'})
consumer = Consumer(kafka_conf)
consumer.subscribe(['sensor_temperature', 'sensor_humidity', 'sensor_pressure'])

# Sensor simulation configuration
SENSOR_TOPICS = {
    'temperature': 'sensor_temperature',
    'humidity': 'sensor_humidity',
    'pressure': 'sensor_pressure'
}
UPDATE_INTERVALS = {
    'temperature': 2,
    'humidity': 3,
    'pressure': 4
}
SPIKE_PROBABILITY = 0.1

def generate_reading(sensor_type):
    ranges = {'temperature': (-45, 45), 'humidity': (30, 90), 'pressure': (10, 50)}
    return round(random.uniform(*ranges[sensor_type]), 2)

def should_spike():
    return random.random() < SPIKE_PROBABILITY

def delivery_report(err, msg):
    if err is not None:
        print(Fore.RED + 'Message delivery failed: {}'.format(err))
    else:
        print(Fore.GREEN + 'Message delivered to {} [{}]'.format(msg.topic(), msg.partition()))

def publish_sensor_data():
    last_update_time = {sensor: 0 for sensor in SENSOR_TOPICS}
    
    while True:
        current_time = time.time()
        for sensor, topic in SENSOR_TOPICS.items():
            if current_time - last_update_time[sensor] >= UPDATE_INTERVALS[sensor] or should_spike():
                data_value = generate_reading(sensor)
                sensor_record = {sensor: data_value, "timestamp": time.time()}

                # Save raw sensor data to MongoDB
                db[sensor].insert_one(sensor_record.copy())

                # Remove MongoDB specific fields before sending to Kafka
                sensor_record.pop('_id', None)

                # Produce to Kafka topic
                producer.produce(topic, json.dumps(sensor_record), callback=delivery_report)
                last_update_time[sensor] = current_time
                socketio.emit('sensor_data', {'type': sensor, 'value': data_value})
        
        producer.poll(0)
        time.sleep(0.1)



def predict_anomaly(model, value):
    prediction = model.predict([[value]])
    return prediction[0] == -1

def consume_and_process():
    while True:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue

        sensor_value = json.loads(msg.value().decode('utf-8'))
        sensor_type = msg.topic().split('_')[1]
        value = sensor_value[sensor_type]
        model = model_temperature if sensor_type == 'temperature' else model_humidity if sensor_type == 'humidity' else model_pressure

        if predict_anomaly(model, value):
            print(Fore.YELLOW + f"Anomaly detected in {sensor_type}: {value}")
            socketio.emit('anomaly_data', {'type': sensor_type, 'value': sensor_value})
            anomaly_record = {"value": value, "timestamp": time.time()}
            db[f"{sensor_type}_anomalies"].insert_one(anomaly_record)

@app.route('/')
def index() -> str:
    return render_template("index.html")

@app.route('/sensor_historical_data')
def historical_data() -> str:
    return render_template("historical_data.html")

@app.route('/about_project')
def about_project() -> str:
    return render_template("about_project.html")


@app.route('/api/sensor_data/<sensor_type>', methods=['GET'])
def get_sensor_data(sensor_type):
    data = list(db[sensor_type].find({}, {'_id': 0}).sort([("timestamp", -1)]).limit(100))
    return jsonify(data)

@app.route('/api/anomalies/<sensor_type>', methods=['GET'])
def get_anomalies(sensor_type):
    anomalies = list(db[f"{sensor_type}_anomalies"].find({}, {'_id': 0}).sort([("timestamp", -1)]).limit(100))
    return jsonify(anomalies)

if __name__ == '__main__':
    threading.Thread(target=consume_and_process, daemon=True).start()
    threading.Thread(target=publish_sensor_data, daemon=True).start()
    print("Running Flask with SocketIO")
    #socketio.run(app, allow_unsafe_werkzeug=True)
    socketio.run(app, host='0.0.0.0', port=80,allow_unsafe_werkzeug=True) 
