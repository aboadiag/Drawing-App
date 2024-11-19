from flask import Flask, request, jsonify
from flask_cors import CORS
from pyngrok import ngrok
# from bayesianbandits import UpperConfidenceBound
from bayesianbandits import Arm, NormalInverseGammaRegressor, Agent, ThompsonSampling, UpperConfidenceBound
import numpy as np
# import random
import time
import requests
import json
from collections import deque
from datetime import datetime

#misty url:
# Define your Misty WebAPI URL
MISTY_URL = "http://172.26.189.224/api/"

app = Flask(__name__)


# Enable CORS for all routes
CORS(app)

# Data storage for logging purposes
user_data = []

# Track interaction history (for the aggregate interactivity)
interaction_history = deque()  # Store timestamps and interactivity scores (1 or 0)
TIME_WINDOW = 60  # In seconds (e.g., track last 60 seconds of interactions)
MAX_HISTORY_LENGTH = 100  # Limit the length of the deque to avoid excessive memory usag

# Define the two personalities
personalities = ["Charismatic", "Uncharismatic"]


# Define Arms for Charismatic and Uncharismatic
arms = [
    Arm(0, learner=NormalInverseGammaRegressor()),  # Arm for Charismatic (action 0)
    Arm(1, learner=NormalInverseGammaRegressor())   # Arm for Uncharismatic (action 1)
]


# Initialize the Agent with ThompsonSampling policy
agent = Agent(arms, ThompsonSampling(), random_seed=0)

# Set the time window in seconds (e.g., 10 seconds)
TIME_WINDOW = 10

# Initialize interaction history as an empty deque
# Each entry in the deque will be a tuple (timestamp_seconds, interaction_value)
interaction_history = deque()

# Helper function to calculate aggregate interactivity using the interaction's timestamp
def calculate_aggregate_interactivity(timestamp_seconds):
    # Remove interactions older than the TIME_WINDOW from the history
    while interaction_history and timestamp_seconds - interaction_history[0][0] > TIME_WINDOW:
        interaction_history.popleft() # The popleft() method in Python is used to remove and return the first element (leftmost) from a deque object.

    # Sum the interaction values (1 or 0) in the time window
    total_interaction = sum([score for _, score in interaction_history])
    return total_interaction

# Helper function to convert timestamp to seconds since the epoch
def convert_timestamp_to_seconds(timestamp_str):
    # Assuming the timestamp is in ISO8601 format (e.g., '2024-11-16T20:49:49.382Z')
    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))  # Convert to datetime object
    return timestamp.timestamp()  # Convert datetime to seconds since epoch

# Define the route for logging user data
@app.route('/logDrawingData', methods=['POST'])
def log_drawing_data():
    try:
        data = request.json
        action = data.get("action")
        timestamp_str = data.get("timestamp")
        # additional_data = data.get("additionalData", {})

        # data received
        print(f"Received Action: {action} at {timestamp_str}")
        
        # Convert the timestamp to seconds since the epoch
        timestamp_seconds = convert_timestamp_to_seconds(timestamp_str)

        #append to in-memory storage (for debug)
        user_data.append(data)
        print("Data received:", data)  # Print data for debugging purposes

        # Define the user interaction actions
        user_actions = [
            "Reset Canvas", "Start Drawing", "Stop Drawing",
            "Canvas Saved", "Switched to Erase", "Switched to Paint",
            "Changed Color", "Changed Line Width"
        ]

        # Assume 'Start Drawing' means interaction, 'Stop Drawing' means no interaction
        interaction_value = 1 if action in ["Start Drawing", "Switched to Paint", "Changed Color"] else 0

        # Track the interaction with the current timestamp
        interaction_history.append((timestamp_seconds, interaction_value))

        # Calculate aggregate interactivity in the last TIME_WINDOW seconds
        aggregate_interactivity = calculate_aggregate_interactivity(timestamp_seconds)
        print(f"Aggregate Interactivity over last {TIME_WINDOW} seconds: {aggregate_interactivity}")

        # Update the agent with the action's reward (user interaction: 0 or 1)
        agent.update(np.array([aggregate_interactivity]))  # Using the 'update' method to update the agent

        # Select an action (personality) based on the current policy
        chosen_action = agent.pull()[0]  # Pull the selected action (this selects an arm)

        print(f"Chosen Action: {chosen_action}")

        # Change Misty's LED color based on the chosen action
        if chosen_action == 0:
            # Charismatic Personality (LED color blue)
            led_data = {"red": 0, "green": 0, "blue": 255}
            print("Switching to Charismatic personality. LED color: Blue")

        else:
            # Uncharismatic Personality (Indirect requests, No eye contact, No gestures)
            led_data = {"red": 255, "green": 0, "blue": 0}
            print("Switching to Uncharismatic personality. LED color: Red")

        # Send request to Misty to change LED color
        try:
            # response = requests.post(MISTY_URL + 'led', json=led_data)
            response = requests.post(f"{MISTY_URL}led",
                headers={"Content-Type": "application/json"},
                data=json.dumps(led_data))
             
            if response.status_code == 200:
                print("LED color changed successfully")
                print(response.json())  # Print response from Misty (optional)
            else:
                print(f"Error: {response.status_code}")
                return jsonify({"status": "error", "message": f"LED change failed with status code {response.status_code}"}), 500

        #timeout exception        
        except requests.exceptions.Timeout:
            print("Timeout occurred while trying to connect to Misty")
            return jsonify({"status": "error", "message": "Timeout error while connecting to Misty"}), 500

        #failure to send request request
        except requests.exceptions.RequestException as e:
            print(f"Error making request: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

        return jsonify({"status": "success", "message": "Action processed and LED color updated"}), 200


    except Exception as e:
        print(f"Error processing data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# authenticate with token
# ngrok.set_auth_token('2otdzQUTflD4b8Rr6rgKPkvSMUz_51jw94NLV3RPaw4Dhzh8W')

# # Start ngrok and get the public URL
# public_url = ngrok.connect(5000)  # Start ngrok tunnel on port 5000
# print(f" * ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:5000\"")

# Run the Flask app
if __name__ == "__main__":
    app.run(port=5000) #flask should listen here
