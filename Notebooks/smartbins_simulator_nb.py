#!/usr/bin/env python
# coding: utf-8

# ## smartbins_simulator_nb
# 
# null

# In[5]:


# Welcome to your new notebook
# Type here in the cell editor to add code!


# In[1]:


pip install azure-eventhub pandas faker


# In[7]:


# ==========================================================
# SMART WASTE MANAGEMENT - DALLAS CITY IOT SIMULATOR
# ==========================================================

import json, time, random
from datetime import datetime, timezone
from faker import Faker
from azure.eventhub import EventHubProducerClient, EventData

# ---------------- CONFIG ----------------
CONNECTION_STR = "Your Connection String"
EVENTHUB_NAME_MAIN = "smartbins-stream"
EVENTHUB_NAME_COLLECTION = "smartbins-collection"  # optional: create second hub for collection logs
BATCH_SIZE = 10
SLEEP_INTERVAL = 5

faker = Faker()

# --- Residential / road-weighted coordinates ---
ZONES = {
    "Central": {"bins":180, "roads":[{"lat":(32.770,32.800),"lon":(-96.820,-96.790)},
                                     {"lat":(32.775,32.785),"lon":(-96.810,-96.780)}]},
    "North":   {"bins":200, "roads":[{"lat":(32.880,32.950),"lon":(-96.810,-96.770)},
                                     {"lat":(32.890,32.930),"lon":(-96.850,-96.790)}]},
    "South":   {"bins":150, "roads":[{"lat":(32.640,32.690),"lon":(-96.840,-96.740)},
                                     {"lat":(32.650,32.680),"lon":(-96.870,-96.800)}]},
    "East":    {"bins":130, "roads":[{"lat":(32.780,32.830),"lon":(-96.730,-96.660)},
                                     {"lat":(32.800,32.840),"lon":(-96.700,-96.640)}]},
    "West":    {"bins":160, "roads":[{"lat":(32.770,32.810),"lon":(-96.880,-96.840)},
                                     {"lat":(32.750,32.790),"lon":(-96.920,-96.870)}]}
}
CITY_BOUND = {"lat":(32.600,33.000), "lon":(-96.950,-96.550)}

# ---------------- STATE -----------------
bin_states = {}      # current fill level
bin_histories = {}   # rolling fill history
bin_empties = {}     # number of times emptied

def generate_coordinates(zone):
    road = random.choice(ZONES[zone]["roads"])
    lat = round(random.uniform(*road["lat"]), 6)
    lon = round(random.uniform(*road["lon"]), 6)
    lat = min(max(lat, CITY_BOUND["lat"][0]), CITY_BOUND["lat"][1])
    lon = min(max(lon, CITY_BOUND["lon"][0]), CITY_BOUND["lon"][1])
    return lat, lon

def generate_bin_data():
    """Simulate a single sensor reading."""
    zone = random.choice(list(ZONES.keys()))
    bin_id = f"{zone[:2].upper()}_{random.randint(1, ZONES[zone]['bins'])}"

    # Initialize state if new
    if bin_id not in bin_states:
        bin_states[bin_id] = random.uniform(60, 90)
        bin_histories[bin_id] = []
        bin_empties[bin_id] = 0

    fill = bin_states[bin_id] + random.uniform(1, 5)
    emptied = False
    if fill > 90 and random.random() < 0.8:
        fill = random.uniform(0, 10)
        emptied = True
        bin_empties[bin_id] += 1

    bin_states[bin_id] = fill
    timestamp = datetime.now(timezone.utc).isoformat()
    bin_histories[bin_id].append({"t": timestamp, "fill": round(fill, 2)})
    if len(bin_histories[bin_id]) > 15:
        bin_histories[bin_id].pop(0)

    lat, lon = generate_coordinates(zone)

    return {
        "bin_id": bin_id,
        "zone": zone,
        "timestamp": timestamp,
        "fill_level": round(fill, 2),
        "temperature": round(random.uniform(15, 42), 2),
        "vibration": round(random.uniform(0, 0.2), 3),
        "latitude": lat,
        "longitude": lon,
        "emptied": emptied,
        "empty_count": bin_empties[bin_id],
        "fill_history": bin_histories[bin_id]
    }

def generate_collection_log(bin_record):
    """Create a collection log entry whenever a bin is emptied."""
    return {
        "bin_id": bin_record["bin_id"],
        "zone": bin_record["zone"],
        "timestamp_collected": bin_record["timestamp"],
        "latitude": bin_record["latitude"],
        "longitude": bin_record["longitude"],
        "empty_count": bin_record["empty_count"]
    }

def start_streaming():
    producer_main = EventHubProducerClient.from_connection_string(CONNECTION_STR, eventhub_name=EVENTHUB_NAME_MAIN)
    producer_log = EventHubProducerClient.from_connection_string(CONNECTION_STR, eventhub_name=EVENTHUB_NAME_COLLECTION)

    print("🚀 Streaming Smart Waste data (with collection log)...")

    while True:
        batch_main = producer_main.create_batch()
        batch_log = producer_log.create_batch()

        for _ in range(BATCH_SIZE):
            record = generate_bin_data()
            batch_main.add(EventData(json.dumps(record)))

            # If bin emptied → add to collection log
            if record["emptied"]:
                log_entry = generate_collection_log(record)
                batch_log.add(EventData(json.dumps(log_entry)))

        producer_main.send_batch(batch_main)
        if len(batch_log) > 0:
            producer_log.send_batch(batch_log)

        print(f"✅ Sent {BATCH_SIZE} sensor events; {len(batch_log)} collection logs at {datetime.now().strftime('%H:%M:%S')}")
        time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    start_streaming()

