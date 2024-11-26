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
import csv, random, string

# Define constants
# Base directory for user logs
USER_LOG_BASE_PATH = "./user_logs"

def generate_unique_id():
    """Generate a random unique ID."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

global_unique_id = generate_unique_id()

# MISTY URL AND ENDPOINTS
MISTY_URL = "http://172.26.189.224"
AUDIO_PLAY_ENDPOINT = "/api/audio/play"
LED_ENDPOINT = "/api/led"
ARM_ENDPOINT = "/api/arms"
FACE_IMAGE_ENDPOINT = "/api/images/display"
HEAD_ENDPOINT = "/api/head"

AUDIO_FILES_DIR = "misty_audio_files"
DEFAULT_VOLUME = 50

# Speech file names (stored in google drive misty_audio_files)
speech_file = {
    "char_s1": "https://drive.google.com/uc?id=1oJ6cL8X-b1PZAhO_7BIJwVa_cou9tyBa",
    "unchar_s1": "https://drive.google.com/uc?id=1jDwAgw4YFZvfJXHogHvNqLim3vhD4xMp",
}


# Misty API endpoints
led_url = f"{MISTY_URL}{LED_ENDPOINT}"
audio_url = f"{MISTY_URL}{AUDIO_PLAY_ENDPOINT}"
arms_url = f"{MISTY_URL}{ARM_ENDPOINT}"
face_url = f"{MISTY_URL}{FACE_IMAGE_ENDPOINT}"
head_url = f"{MISTY_URL}{HEAD_ENDPOINT}"

# ----------------------------- MISTY EXPRESSIONS -----------------------#
# DEFAULT
default_led =  {"red": 255, "green": 255, "blue": 255} # white (default)
default_arms = {
  "LeftArmPosition": 85, # arm straight down [in deg]
  "RightArmPosition": 85, # arm straight down
  "LeftArmVelocity": 10, # between 0-100
  "RightArmVelocity": 10
}

default_head = {
  "Pitch": 0, # head not tilted up or down
  "Roll": 0, # head not tilted side/side
  "Yaw": 0, # head not turned left or right
  "Velocity": 60 # move head (0-100)
}
default_face =  {
    "FileName": "e_DefaultContent.jpg",
    "Alpha": 1,
}

# CHARASMATIC
#  VERBAL:
char_speech  = speech_file["char_s1"]

# NON-VERBAL:
char_face = {
    "FileName": "e_Joy.jpg",
    "Alpha": 1,
}
char_arms_start = {
    "LeftArmPosition": -28, #up
    "RightArmPosition": -28,
  "LeftArmVelocity": 50,
  "RightArmVelocity": 50,
}

char_arms_end = {
    "LeftArmPosition": 90, #down
    "RightArmPosition": 90,
  "LeftArmVelocity": 50,
  "RightArmVelocity": 50,
}

char_head = {
    "Pitch": 0, # head not tilted up or down
  "Roll": 0, # head not tilted side/side
  "Yaw": 75, # head turned left
  "Velocity": 60
}
char_led = {"red": 0, "green": 0, "blue": 255}

# UNCHARASMATIC
#  VERBAL:
unchar_speech  = speech_file["unchar_s1"]

# NON-VERBAL
unchar_arms = default_arms
unchar_face = default_face
unchar_head = default_head
unchar_led =  default_led
# ----------------------------- MISTY EXPRESSIONS -----------------------#

# Initialize Flask app
app = Flask(__name__)


# Enable CORS for all routes
CORS(app)

######################################## BAYESIAN BANDIT SET UP ######################################################
# Data storage for logging purposes
user_data = []

# Define the user interaction actions
user_actions = [
    "Reset Canvas", "Start Drawing", "Stop Drawing",
    "Canvas Saved", "Switched to Erase", "Switched to Paint",
    "Changed Color", "Changed Line Width"
]
interactive = ["Start Drawing", "Switched to Paint", "Changed Color",
                                    "Switched to Erase", "Canvas Saved", "Changed Line Width"]
not_interactive = ["Stop Drawing", "Reset Canvas"]


interaction_history = deque()  # Store timestamps and interactivity scores (1 or 0)
INTERACTIVITY_TIME_WINDOW  = 10  # Time window for interactivity level classification (in seconds)
PERSONALITY_CHANGE_TIME_WINDOW = 15  # Time window for changing the personality (in seconds)


# Track the last interaction time and last personality change time
last_interactivity_update_time = 0  # Timestamp of the last interactivity update
last_personality_change_time = 0  # Timestamp of the last personality change

# Define the two personalities
personalities = ["Charismatic", "Uncharismatic"]

# Define Arms for Charismatic and Uncharismatic
arms = [
    Arm(0, learner=NormalInverseGammaRegressor()),  # Arm for Charismatic (action 0)
    Arm(1, learner=NormalInverseGammaRegressor())   # Arm for Uncharismatic (action 1)
]



# Initialize the Agent with ThompsonSampling policy
agent = Agent(arms, ThompsonSampling(), random_seed=0)

# Initialize interaction history as an empty deque
# Each entry in the deque will be a tuple (timestamp_seconds, interaction_value)
interaction_history = deque()


######################################## BAYESIAN BANDIT SET UP ######################################################

######################################## USER INTERACTION DATA LOGGING #####################################################

def log_to_csv(data, reward_assignment=None, context=None, arm_selection=None):
    """
    Log user interaction data to a CSV file and additional data to JSON in a unique user folder.

    Parameters:
        data (dict): Interaction data containing 'timestamp', 'action', and 'interaction_value'.
        reward_assignment (int, optional): Reward assignments for each action.
        context (str, optional): Contextual information (e.g., "low", "medium", "high").
        arm_selection (int, optional): Selected arm (e.g., 0 for Charismatic, 1 for Uncharismatic).
    """
    try:

        # Use the persistent unique ID
        unique_id = global_unique_id
        user_log_path = os.path.join(USER_LOG_BASE_PATH, unique_id)
        os.makedirs(user_log_path, exist_ok=True)

        # Log the interaction data to a CSV file
        csv_file_path = os.path.join(user_log_path, "interaction_log.csv")
        file_exists = os.path.isfile(csv_file_path)
        with open(csv_file_path, mode='a', newline='', encoding='utf-8') as file:
            fieldnames = ['timestamp', 'action', 'interaction_value']
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            # Write header if the file doesn't exist
            if not file_exists:
                writer.writeheader()

            writer.writerow(data)
        print(f"Logged interaction data: {data}")

        # Log additional data to a JSON file
        metadata = {
            "action_distribution": data.get("action"),  # Use action from data for action_distribution
            "reward_assignment": reward_assignment,
            "context": context,
            "arm_selection": arm_selection,
            "log_timestamp": datetime.now().isoformat()
        }

        # Write metadata to a JSON file
        metadata_file_path = os.path.join(user_log_path, "metadata.json")
        with open(metadata_file_path, mode='w', encoding='utf-8') as json_file:
            json.dump(metadata, json_file, indent=4)
        print(f"Logged metadata to {metadata_file_path}")

    except Exception as e:
        print(f"Error logging to user folder: {e}")
######################################## USER INTERACTION DATA LOGGING #####################################################

# -------------------------------------------- HELPER FUNCTIONS -----------------------------------------------------

######################################## MISTY HELPER FUNCTIONS ######################################################
# ------------------- CHANGING MISTY'S PERSONA ------------------------------------ #
def play_audio_on_misty(file_url, volume=DEFAULT_VOLUME):
    print("Playing audio on misty...")
    """Send a POST request to Misty to play audio."""
    try:
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
    print("Changing misty's led...")
    try:
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

def change_misty_face(face_data):
    print("Changing misty's face expression...")
    try:
        response = requests.post(
            face_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(face_data))
        
        if response.status_code == 200:
            print("Face expression changed successfully")
            print(response.json())  # Print response from Misty (optional)
        else:
            print(f"Error: {response.status_code}")
            return jsonify({"status": "error", "message": f"Face expression change failed with status code {response.status_code}"}), 500

    #timeout exception        
    except requests.exceptions.Timeout:
        print("Timeout occurred while trying to connect to Misty")
        return jsonify({"status": "error", "message": "Timeout error while connecting to Misty"}), 500

    #failure to send request request
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "success", "message": "Action processed and Face expression updated"}), 200

def move_misty_head(head_data):
    print("Moving misty's head...")
    try:
        response = requests.post(
            head_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(head_data))
        
        if response.status_code == 200:
            print("Face expression changed successfully")
            print(response.json())  # Print response from Misty (optional)
        else:
            print(f"Error: {response.status_code}")
            return jsonify({"status": "error", "message": f"Head position change failed with status code {response.status_code}"}), 500

    #timeout exception        
    except requests.exceptions.Timeout:
        print("Timeout occurred while trying to connect to Misty")
        return jsonify({"status": "error", "message": "Timeout error while connecting to Misty"}), 500

    #failure to send request request
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "success", "message": "Action processed and Head position updated"}), 200

def move_arms_on_misty(arm_data):
    print("Moving misty's arms...")
    try:
        response = requests.post(
            arms_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(arm_data))
        
        if response.status_code == 200:
            print("ARM moved successfully")
            print(response.json())  # Print response from Misty (optional)
        else:
            print(f"Error: {response.status_code}")
            return jsonify({"status": "error", "message": f"Arms move failed with status code {response.status_code}"}), 500

    #timeout exception        
    except requests.exceptions.Timeout:
        print("Timeout occurred while trying to connect to Misty")
        return jsonify({"status": "error", "message": "Timeout error while connecting to Misty"}), 500

    #failure to send request request
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "success", "message": "Action processed and Arms moved"}), 200

# ------------------- CHANGING MISTY'S PERSONA ------------------------------------ #
######################################## MISTY HELPER FUNCTIONS ######################################################

######################################## BAYESIAN BANDIT HELPER FUNCTIONS ######################################################

# Function to classify the interaction context
def classify_interactivity_level(timestamp_seconds):
    recent_actions = [action for _, action in interaction_history]

    # Count the number of "interactive" and "not interactive" actions
    high_interactivity_count = sum([1 for action in recent_actions if action in interactive])
    low_interactivity_count = sum([1 for action in recent_actions if action in not_interactive])

    if high_interactivity_count >= 4:
        return "high"  # High interactivity if 4 or more interactive actions
    elif low_interactivity_count >= 4:
        return "low"  # Low interactivity if 4 or more not interactive actions
    else:
        return "medium"  # Medium interactivity if it's a mix of both


# Helper function to convert timestamp to seconds since the epoch
def convert_timestamp_to_seconds(timestamp_str):
    # Assuming the timestamp is in ISO8601 format (e.g., '2024-11-16T20:49:49.382Z')
    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))  # Convert to datetime object
    return timestamp.timestamp()  # Convert datetime to seconds since epoch

######################################## BAYESIAN BANDIT HELPER FUNCTIONS ######################################################

# -------------------------------------------- HELPER FUNCTIONS -----------------------------------------------------

# Define the route for logging user data
@app.route('/logDrawingData', methods=['POST'])
def log_drawing_data():
    global last_interactivity_update_time, last_personality_change_time  # Track time for both windows
    try:
        data = request.json
        action = data.get("action")
        timestamp_str = data.get("timestamp")
        print(f"Received Action: {action} at {timestamp_str}")

        # Convert the timestamp to seconds since the epoch
        timestamp_seconds = convert_timestamp_to_seconds(timestamp_str)
   
        # Assign rewards            
        interaction_value = 1 if action in interactive else 0

        # Prepare interaction data
        log_data = {
            'timestamp': timestamp_seconds,
            'action': action,
            'interaction_value': interaction_value
        }
        
        #save action and timestamp
        interaction_history.append((timestamp_seconds, action))

        # --- Interactivity Classification ---  
        if timestamp_seconds - last_interactivity_update_time >= INTERACTIVITY_TIME_WINDOW:

            # Classify interactivity level
            context = classify_interactivity_level(timestamp_seconds)
            print(f"Interactivity Level: {context}")
            last_interactivity_update_time = timestamp_seconds  # Update the time after classifying


        # --- Personality Change ---
        # Only change personality if more than PERSONALITY_CHANGE_TIME_WINDOW seconds have passed
        if timestamp_seconds - last_personality_change_time >= PERSONALITY_CHANGE_TIME_WINDOW:
            print("Proceeding with personality change...") 

            # Select an action (personality) based on the current policy
            chosen_action,  = agent.pull()  # Pull the selected action (this selects an arm)
            print(f"Chosen Action: {chosen_action}")

            # Log all relevant data
            log_to_csv(
                data=log_data,
                reward_assignment= interaction_value,
                context=context,
                arm_selection=chosen_action
            )

            # Change Misty's PERSONALITY/chosen action
            if chosen_action == 0:

                # Charismatic Personality (Direct requests, eye contact and arm movement while speaking)
                change_led_on_misty(char_led)
                # play_audio_on_misty(char_speech)
                change_misty_face(char_face)
                move_arms_on_misty(char_arms_start)
                #delay for 5 seconds:
                time.sleep(5)
                move_arms_on_misty(char_arms_end)
                move_misty_head(char_head)

            else:
                # Uncharismatic Personality (Indirect requests, No eye contact and default gestures while speaking)
                change_led_on_misty(unchar_led)
                # play_audio_on_misty(unchar_speech)
                change_misty_face(unchar_face)
                move_arms_on_misty(unchar_arms)
                move_misty_head(unchar_head)

            last_personality_change_time = timestamp_seconds  # Update the last personality change time
            print(f"last personality change at {last_personality_change_time}")
        
    except Exception as e:
        print(f"Error processing data: {e}")
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

    # Add a valid return response at the end of the function
    return jsonify({"status": "success", "message": "Drawing data logged successfully"}), 200

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, port=80) #flask should listen here
