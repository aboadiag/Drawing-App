from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pyngrok import ngrok
from bayesianbandits import Arm, NormalInverseGammaRegressor, Agent, ThompsonSampling, ContextualAgent
from gtts import gTTS
import os
import numpy as np
import time
import requests
import json
from collections import deque
from datetime import datetime
import csv, random, string
from enum import Enum

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
ARM_ENDPOINT = "/api/arms/set"
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
  "Velocity": 85 # move head (0-100)
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
  "Yaw": 40, # head turned left
  "Velocity": 85
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

# Flag to track if Misty has been initialized
misty_initialized = False
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

interaction_history = deque()  # Each entry in the deque will be a tuple (timestamp_seconds, interaction_value): Store timestamps and interactivity scores (1 or 0)
INTERACTIVITY_TIME_WINDOW  = 10  # Time window for interactivity level classification (in seconds)
PERSONALITY_CHANGE_TIME_WINDOW = 20  # Time window for changing the personality (in seconds)


# Track the last interaction time and last personality change time
last_interactivity_update_time = 0  # Timestamp of the last interactivity update
last_personality_change_time = 0  # Timestamp of the last personality change

# Define the two personalities
personalities = ["Charismatic", "Uncharismatic"]

# Define Arms for Charismatic and Uncharismatic
context_arms = [
    Arm(0, learner=NormalInverseGammaRegressor()),  # Arm for Charismatic (action 0)
    Arm(1, learner=NormalInverseGammaRegressor())   # Arm for Uncharismatic (action 1)
]

# Initialize the Contextual Bandit Agent with ThompsonSampling policy
context_agent = ContextualAgent(arms=context_arms, policy=ThompsonSampling())

contexts = {
    "low": np.array([[0.1]]),     # Low interactivity
    "medium": np.array([[0.5]]),  # Medium interactivity
    "high": np.array([[0.9]])# High interactivity
}

        
######################################## BAYESIAN BANDIT SET UP ######################################################

######################################## USER INTERACTION DATA LOGGING #####################################################
# Use the persistent unique ID to create the file path
def get_user_log_path():
    """
    Generates a user-specific path based on the unique ID.
    """
    unique_id = global_unique_id  # Using the global unique ID
    start_interaction(unique_id) # intiialize the misty
    time.sleep(5)
    print(f"The unique ID is:{unique_id}")
    user_log_path = os.path.join(USER_LOG_BASE_PATH, unique_id)
    os.makedirs(user_log_path, exist_ok=True)  # Ensure the directory exists
    return os.path.join(user_log_path, "interaction_log.csv")  # Return full file path

# Initialize the log file (only creates the file if it doesn't exist)
def initialize_log_file():
    log_file_path = get_user_log_path()
    if not os.path.exists(log_file_path):
        with open(log_file_path, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=[
                'timestamp', 'action', 'interaction_value', 'reward_assignment', 'context', 'arm_selection', 'log_timestamp'
            ])
            writer.writeheader()

# Log data into the user-specific CSV file
def log_to_csv(data, reward_assignment=None, context=None, arm_selection=None):
    """
    Log the action interaction to a CSV file with additional metadata.
    """
    log_file_path = get_user_log_path()
    log_timestamp = timestamp_to_iso(data['timestamp'])  # Convert timestamp to ISO format

    # Log data including all the necessary fields
    with open(log_file_path, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=[
            'timestamp', 'action', 'interaction_value', 'reward_assignment', 'context', 'arm_selection', 'log_timestamp'
        ])
        writer.writerow({
            'timestamp': data['timestamp'],
            'action': data['action'],
            'interaction_value': data['interaction_value'],
            'reward_assignment': reward_assignment,
            'context': context,
            'arm_selection': arm_selection,
            'log_timestamp': log_timestamp
        })
    print("Logged interaction data to CSV.")

# Convert timestamp to ISO format
def timestamp_to_iso(timestamp):
    """
    Convert a timestamp (in seconds) to an ISO 8601 format string.
    """
    return datetime.utcfromtimestamp(timestamp).isoformat()
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

def initialize_misty():
#  play_audio_on_misty()
 change_led_on_misty(default_led) 
 change_misty_face(default_face)
 move_misty_head(default_head)
 move_arms_on_misty(default_arms)


def start_interaction(unique_id):
    global misty_initialized
    
    if not misty_initialized:
        print("Initializing Misty...")
        initialize_misty()  # Initialize Misty if it's the first interaction
        misty_initialized = True  # Mark that Misty has been initialized
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
    global context
    try:
        # collect data from client (with user interactions)
        data = request.json
        action = data.get("action")
        timestamp_str = data.get("timestamp")
        print(f"Received Action: {action} at {timestamp_str}")

        # Convert the timestamp to seconds since the epoch
        timestamp_seconds = convert_timestamp_to_seconds(timestamp_str)
   
        #save user interactions (i.e. "actions") and timestamp
        interaction_history.append((timestamp_seconds, action))

        # Classify the interactivity level based on recent actions
        context_label = classify_interactivity_level(timestamp_seconds)
        context = contexts[context_label]  # Set the current context (low, medium, high)
        print(f"Context is: {context_label}")

        # Assign rewards: interaction_value          
        reward = 1 if action in interactive else 0

        # Log all relevant data
        log_to_csv(data, reward_assignment=reward, context=context_label,arm_selection=None)

        # Select an arm based on the context and estimated reward probability with said arm
        predicted_arm = context_agent.pull(context)  
        print(f"Chosen Arm Token: {predicted_arm}")

        print("Proceeding with personality change...") 

        # Change Misty's PERSONALITY/chosen action
        if predicted_arm == 0: # Charismatic Personality (Direct requests, eye contact and arm movement while speaking)
            change_led_on_misty(char_led)
            # play_audio_on_misty(char_speech)
            change_misty_face(char_face)
            move_misty_head(char_head)
            move_arms_on_misty(char_arms_start)
            time.sleep(5)
            move_arms_on_misty(char_arms_end)


        elif predicted_arm == 1:  # Uncharismatic Personality (Indirect requests, No eye contact and default gestures while speaking)
            change_led_on_misty(unchar_led)
            # play_audio_on_misty(unchar_speech)
            change_misty_face(unchar_face)
            move_arms_on_misty(unchar_arms)
            move_misty_head(unchar_head)


        # Update the bandit with the observed reward
        context_agent.update(predicted_arm, reward)  

        # Log the arm selection after the agent's decision
        log_to_csv(data, reward_assignment=reward, context=context_label, arm_selection=predicted_arm)

            # last_personality_change_time = timestamp_seconds  # Update the last personality change time
            # print(f"last personality change at {last_personality_change_time}")
        
    except Exception as e:
        print(f"Error processing data: {e}")
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

    # Add a valid return response at the end of the function
    return jsonify({"status": "success", "message": "Drawing data logged successfully"}), 200

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True, port=80) #flask should listen here



    
     # if timestamp_seconds - last_interactivity_update_time >= INTERACTIVITY_TIME_WINDOW:

        #     # Classify interactivity level
        #     context = classify_interactivity_level(timestamp_seconds)[0]
        #     print(f"Interactivity Level: {context[1]}")
        #     last_interactivity_update_time = timestamp_seconds  # Update the time after classifying

        #log:
        # log_to_csv(
        #         data=log_data,
        #         reward_assignment= context[0],
        #         context=context[1],
        # )
        # --- Personality Change ---
        # Only change personality if more than PERSONALITY_CHANGE_TIME_WINDOW seconds have passed
        # if timestamp_seconds - last_personality_change_time >= PERSONALITY_CHANGE_TIME_WINDOW:

        # Use the Contextual Agent to select an arm (personality)
        # Select an action (personality) based the context
        # context_key = classify_interactivity_level(timestamp_seconds)[1]  # Timestamp can be the current time or relevant time for your logic
        # context = contexts[context_key]


        # chosen_arm_token, = context_agent.pull(context)
        # print(f"Chosen Arm Token: {chosen_arm_token}")


#         class InteractivityLevel(Enum):
# #     LOW = 0
#     MEDIUM = 1
#     HIGH = 2

#     def get_value(self):
#         """Return the corresponding np.array for each level of interactivity."""
#         if self == InteractivityLevel.LOW:
#             return np.array([[0.1]])  # Low interactivity
#         elif self == InteractivityLevel.MEDIUM:
#             return np.array([[0.5]])  # Medium interactivity
#         elif self == InteractivityLevel.HIGH:
#             return np.array([[0.9]])  # High interactivity

