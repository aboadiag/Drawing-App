from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pyngrok import ngrok
from bayesianbandits import Arm, NormalInverseGammaRegressor, Agent, ThompsonSampling, UpperConfidenceBound
from gtts import gTTS
import os
import numpy as np
import time
import requests
import json
from collections import deque
from datetime import datetime

# Define constants
MISTY_URL = "http://172.26.189.224"
AUDIO_PLAY_ENDPOINT = "/api/audio/play"
LED_ENDPOINT = "/api/led"
AUDIO_FILES_DIR = "misty_audio_files"
DEFAULT_VOLUME = 50
LOCAL_SERVER_IP = "172.26.28.222"  # Replace with your local machine's IP address
LOCAL_SERVER_PORT = 8000

# Speech file names
speech = {
    "char_s1": f"{AUDIO_FILES_DIR}/misty_char1.mp3",
    "uncahr_s1": f"{AUDIO_FILES_DIR}/misty_unchar1.mp3",
}

# Misty API endpoints
led_url = f"{MISTY_URL}{LED_ENDPOINT}"
audio_url = f"{MISTY_URL}{AUDIO_PLAY_ENDPOINT}"

# Initialize Flask app
app = Flask(__name__)


# Enable CORS for all routes
CORS(app)

# Serve audio files from the 'misty_audio_files' directory as static files
@app.route('/misty_audio_files/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_FILES_DIR, filename)

######################################## MISTY HELPER FUNCTIONS ######################################################
#Playing new audio files:
def play_audio_on_misty(file_path, volume=DEFAULT_VOLUME):
    """Send a POST request to Misty to play audio."""
    try:
        # Construct the file URL served by the local server
        filename = os.path.basename(file_path)
        file_url = f"http://{LOCAL_SERVER_IP}:{LOCAL_SERVER_PORT}/{AUDIO_FILES_DIR}/{filename}"
        
        # Send the request
        response = requests.post(
            audio_url,
            headers={"Content-Type": "application/json"},
            json={
                "FileName": file_url,
                "Volume": DEFAULT_VOLUME
            }
        )
        if response.status_code == 200:
            print("Audio played successfully on Misty.")
        else:
            print(f"Error playing audio on Misty: {response.status_code} - {response.text}")

                #timeout exception        
    except requests.exceptions.Timeout:
        print("Timeout occurred while trying to connect to Misty")
        return jsonify({"status": "error", "message": "Timeout error while connecting to Misty"}), 500

    #failure to send request request
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return jsonify({"status": "error", "message": f"Error playing audio on Misty: {str(e)}"}), 500

    return jsonify({"status": "success", "message": "Audio file received and played sucessfully"}), 200

def change_led_on_misty(led_data):
    try:
        # response = requests.post(MISTY_URL + 'led', json=led_data)
        response = requests.post(
            led_url,
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


######################################## MISTY HELPER FUNCTIONS ######################################################

# Data storage for logging purposes
user_data = []

# Track interaction history (for the aggregate interactivity)
interaction_history = deque()  # Store timestamps and interactivity scores (1 or 0)
TIME_WINDOW = 20  # In seconds (e.g., track last 60 seconds of interactions)
MAX_HISTORY_LENGTH = 100  # Limit the length of the deque to avoid excessive memory usag

# Define the two personalities
personalities = ["Charismatic", "Uncharismatic"]


# Define Arms for Charismatic and Uncharismatic
arms = [
    Arm(0, learner=NormalInverseGammaRegressor()),  # Arm for Charismatic (action 0)
    Arm(1, learner=NormalInverseGammaRegressor())   # Arm for Uncharismatic (action 1)
]

# Timestamp to track the last personality change
last_personality_change_time = 0

# Initialize the Agent with ThompsonSampling policy
agent = Agent(arms, ThompsonSampling(), random_seed=0)

# # Set the time window in seconds (e.g., 60 seconds)
# TIME_WINDOW = 60

# Initialize interaction history as an empty deque
# Each entry in the deque will be a tuple (timestamp_seconds, interaction_value)
interaction_history = deque()

# Define the route for logging user data
@app.route('/logDrawingData', methods=['POST'])
def log_drawing_data():
    global last_personality_change_time  # Reference to the global variable

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
        if action in ["Start Drawing", "Switched to Paint", "Changed Color",
                                            "Switched to Erase", "Canvas Saved"]:
            interaction_value = 1 
        
        elif action in ["Stop Drawing", "Reset Canvas"]:
            interaction_value = 0 

        # Track the interaction with the current timestamp
        interaction_history.append((timestamp_seconds, interaction_value))

        # Calculate aggregate interactivity in the last TIME_WINDOW seconds
        aggregate_interactivity = calculate_aggregate_interactivity(timestamp_seconds)
        print(f"Aggregate Interactivity over last {TIME_WINDOW} seconds: {aggregate_interactivity}")

        # Update the agent with the action's reward (user interaction: 0 or 1)
        agent.update(np.array([aggregate_interactivity]))  # Using the 'update' method to update the agent

        print(f"timestamp_seconds {timestamp_seconds}")

        # Only change personality once every TIME_WINDOW
        if timestamp_seconds - last_personality_change_time >= TIME_WINDOW:

            # Select an action (personality) based on the current policy
            chosen_action = agent.pull()[0]  # Pull the selected action (this selects an arm)

            print(f"Chosen Action: {chosen_action}")
            last_personality_change_time = timestamp_seconds  # Update the last personality change time
            print(f"last personality change at {last_personality_change_time}")

            # Change Misty's LED color based on the chosen action
            if chosen_action == 0:
                # Charismatic Personality (LED color blue)
                led_data = {"red": 0, "green": 0, "blue": 255}
                change_led_on_misty(led_data)

                #play audio on misty
                speech_data  = speech["char_s1"]
                # audio_pathname = f"{speech_data}/{AUDIO_FILES_DIR}"
                print(f"charactersitic audio path: {speech_data}")
                play_audio_on_misty(speech_data)

                # speech_data = {"text": "Please continue drawing for a few more seconds."}
                print("Switching to Charismatic personality. LED color: Blue, Speech: Direct")

            else:
                # Uncharismatic Personality (Indirect requests, No eye contact, No gestures)
                led_data = {"red": 0, "green": 255, "blue": 0}
                change_led_on_misty(led_data)

                #play audio on misty
                speech_data  = speech["unchar_s1"]
                print(f"uncharactersitic audio path: {speech_data}")
                play_audio_on_misty(speech_data)
                # speech_data = {"text": "Maybe you could continue drawing?"}

                print("Switching to Uncharismatic personality. LED color: Green, Speech: Indirect")
    
    except Exception as e:
        print(f"Error processing data: {e}")
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500


######################################## BAYESIAN BANDIT HELPER FUNCTIONS ######################################################

# Helper function to calculate aggregate interactivity using the interaction's timestamp
def calculate_aggregate_interactivity(timestamp_seconds):
    # Remove interactions older than the TIME_WINDOW from the history
    while interaction_history and timestamp_seconds - interaction_history[0][0] > TIME_WINDOW:
        interaction_history.popleft() # The popleft() method in Python is used to remove and return the first element (leftmost) from a deque object.

   # Calculate the average of the interaction values (1 or 0) in the time window
    if len(interaction_history) > 0:
        total_interaction = sum([score for _, score in interaction_history])
        average_interactivity = total_interaction / len(interaction_history)  # Average interactivity
    else:
        average_interactivity = 0  # If no interactions in the window, return 0
    
    return average_interactivity

# Helper function to convert timestamp to seconds since the epoch
def convert_timestamp_to_seconds(timestamp_str):
    # Assuming the timestamp is in ISO8601 format (e.g., '2024-11-16T20:49:49.382Z')
    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))  # Convert to datetime object
    return timestamp.timestamp()  # Convert datetime to seconds since epoch

######################################## BAYESIAN BANDIT HELPER FUNCTIONS ######################################################


# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, port=80) #flask should listen here


################ DRAFTS ############################

        #     try:
        #         speech_response = requests.post(f"{MISTY_URL}tts/speak",
        #             headers={"Content-Type": "application/json"},
        #             data=json.dumps(speech_data))

        #         if speech_response.status_code == 200:
        #             print("Speech request sent successfully")
        #             print(speech_response.json())  # Print response from Misty (optional)
        #         else:
        #             print(f"Error sending speech: {speech_response.status_code}")

        #     #timeout exception        
        #     except requests.exceptions.Timeout:
        #         print("Timeout occurred while trying to connect to Misty")
        #         return jsonify({"status": "error", "message": "Timeout error while connecting to Misty"}), 500

        #     #failure to send request request
        #     except requests.exceptions.RequestException as e:
        #         print(f"Error making request: {e}")
        #         return jsonify({"status": "error", "message": str(e)}), 500

        #     return jsonify({"status": "success", "message": "Action processed and LED color updated"}), 200
        # # ---------------------------------- Send request to Misty to speak ----------------------------------------

                    # -------------------------- Send request to Misty to change LED color ---------------------------------------

        
            # -------------------------- Send request to Misty to change LED color ---------------------------------------
            # #delay to give enough time for speaking request
            # time.sleep(10)
            # ---------------------------------- Send request to Misty to speak ----------------------------------------




    #timeout exception        
    # except requests.exceptions.Timeout:
    #     print("Timeout occurred while trying to connect to Misty")
    #     return jsonify({"status": "error", "message": "Timeout error while connecting to Misty"}), 500

    # #failure to send request request
    # except requests.exceptions.RequestException as e:
    #     print(f"Error making request: {e}")
    #     return jsonify({"status": "error", "message": str(e)}), 500

    
# authenticate with token
# ngrok.set_auth_token('2otdzQUTflD4b8Rr6rgKPkvSMUz_51jw94NLV3RPaw4Dhzh8W')

# # Start ngrok and get the public URL
# public_url = ngrok.connect(5000)  # Start ngrok tunnel on port 5000
# print(f" * ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:5000\"")