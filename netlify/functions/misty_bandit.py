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

interaction_history = deque()  # Each entry in the deque will be a tuple (timestamp_seconds, interaction_value): Store timestamps and interactivity scores (1 or 0)
INTERACTIVITY_TIME_WINDOW  = 10  # Time window for interactivity level classification (in seconds)
PERSONALITY_CHANGE_TIME_WINDOW = 15  # Time window for changing the personality (in seconds)

# Define the two personalities
personalities = ["Charismatic", "Uncharismatic"]

# Define Arms for Charismatic and Uncharismatic
arms = [
    Arm(0, learner=NormalInverseGammaRegressor()),  # Arm for Charismatic (action 0)
    Arm(1, learner=NormalInverseGammaRegressor())   # Arm for Uncharismatic (action 1)
]

# Initialize the Contextual Bandit Agent with ThompsonSampling policy
context_agent = ContextualAgent(arms, ThompsonSampling())

contexts = {
    "low": np.array([0.1]),     # Low interactivity
    "medium": np.array([0.5]),  # Medium interactivity
    "high": np.array([0.9])# High interactivity
}

        
######################################## BAYESIAN BANDIT SET UP ######################################################

######################################## USER INTERACTION DATA LOGGING #####################################################
# Use the persistent unique ID to create the file path
def get_user_log_path():
    """
    Generates a user-specific path based on the unique ID.
    """
    unique_id = global_unique_id  # Using the global unique ID
    # start_interaction(unique_id) # intiialize the misty
    # time.sleep(5)
    print(f"The unique ID is:{unique_id}")

    user_log_path = os.path.join(USER_LOG_BASE_PATH, unique_id)
    # print(f"User log path (before normalization): {user_log_path}")
    
    # Normalize the path to handle OS-specific separators
    user_log_path = os.path.normpath(user_log_path)
    # print(f"User log path (after normalization): {user_log_path}")

    os.makedirs(user_log_path, exist_ok=True)  # Ensure the directory exists
    return os.path.join(user_log_path, "interaction_log.csv")  # Return full file path

# Log data into the user-specific CSV file
def log_to_csv(data, timestamp_in_secs, reward_assignment=None, context_label=None, arm_selection=None):
    """
    Log the action interaction to a CSV file with additional metadata.
    """
    log_file_path = get_user_log_path()

    # Initialize the log file if it doesn't exist
    if not os.path.exists(log_file_path):
        try:
            with open(log_file_path, mode='w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=[
                    'timestamp', 'action', 'additionalData', 'ObservedReward', 'Context', 'ContextFeatures', 'ChosenArm', 'log_timestamp'
                ])
                writer.writeheader()
                print(f"Log file initialized: {log_file_path}")
        except Exception as e:
            print(f"Error initializing log file: {e}")

    # log_timestamp = timestamp_to_iso(data['timestamp'])  # Convert timestamp to ISO format
    log_timestamp = timestamp_in_secs

    # Log data including all the necessary fields
    with open(log_file_path, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=[
                    'timestamp', 'action', 'additionalData', 'ObservedReward', 'Context', 'ContextFeatures', 'ChosenArm', 'log_timestamp'
        ])
        writer.writerow({
            'timestamp': timestamp_in_secs,
            'action': data['action'],
            'additionalData': data['additionalData'],
            'ObservedReward': reward_assignment,
            'Context': context_label,
            'ContextFeatures': contexts[context_label],
            'ChosenArm': arm_selection,
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
# Define the personality types and interactivity levels
PERSONALITY_CHARISMATIC = "Charismatic"
PERSONALITY_UNCHARISMATIC = "Uncharismatic"

INTERACTIVITY_LOW = "low"
INTERACTIVITY_MEDIUM = "medium"
INTERACTIVITY_HIGH = "high"


# Constants
# PERSONALITY_CHANGE_TIME_WINDOW = 20  # Example window of 60 seconds
# # last_personality_change_time = 0  # Track when the last personality change occurred
# # last_interactivity_update_time = 0  # Last interactivity time
# # context = None  # Current context (interactivity level)
# # predicted_arm = None  # Predicted arm selection (not used in this specific code, but can be part of the context)

    # Track the last interaction time and last personality change time
last_interactivity_update_time = None  # Timestamp of the last interactivity update
last_personality_change_time = None  # Timestamp of the last personality change
context_label = None
predicted_arm = None
reward = None
# Global flag to track Misty's execution state
misty_action_in_progress = False

# Update the Misty expressions and actions based on the current personality
def update_misty_personality(current_personality):
    global misty_action_in_progress
    
    # Check if an action is already in progress
    if misty_action_in_progress:
        print("Action in progress. Please wait until the current action is complete.")
        return  # Early exit if an action is in progress
 
    misty_action_in_progress = True
    try:
        # Perform the personality change logic
        print(f"Changing personality to {current_personality}...")
        if current_personality == PERSONALITY_CHARISMATIC: # Charismatic Personality (Direct requests, eye contact and arm movement while speaking)
            print("Charasmatic Misty")
            change_led_on_misty(char_led)
            play_audio_on_misty(char_speech)
            change_misty_face(char_face)
            move_misty_head(char_head)
            move_arms_on_misty(char_arms_start)
            time.sleep(5)
            move_arms_on_misty(char_arms_end)


        elif current_personality == PERSONALITY_UNCHARISMATIC:  # Uncharismatic Personality (Indirect requests, No eye contact and default gestures while speaking)
            print("Uncharasmatic Misty")
            change_led_on_misty(unchar_led)
            play_audio_on_misty(unchar_speech)
            change_misty_face(unchar_face)
            move_arms_on_misty(unchar_arms)
            move_misty_head(unchar_head)

    finally:
    # Mark the action as complete
        misty_action_in_progress = False


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
    change_led_on_misty(default_led) 
    change_misty_face(default_face)
    move_misty_head(default_head)
    move_arms_on_misty(default_arms)


# ------------------- CHANGING MISTY'S PERSONA ------------------------------------ #
######################################## MISTY HELPER FUNCTIONS ######################################################
# Constants
DRAW_THRESHOLD = 10  # Duration threshold for "high interactivity" (in seconds)
DRAW_THRESHOLD_med = 5
RESET_THRESHOLD = 2  # Reset count threshold for "low interactivity"
# INTERACTIVITY_TIME_WINDOW = 30  # Time window for recent action evaluation (in seconds)

######################################## BAYESIAN BANDIT HELPER FUNCTIONS ######################################################


# Define the user interaction actions
user_actions = [
    "Reset Canvas", "Start Drawing", "Stop Drawing",
    "Canvas Saved", "Switched to Erase", "Switched to Paint",
    "Changed Color", "Changed Line Width"
]
interactive = ["Start Drawing", "Switched to Paint", "Changed Color",
                                    "Switched to Erase", "Canvas Saved", "Changed Line Width"]
not_interactive = ["Stop Drawing", "Reset Canvas"]

# Function to classify the interaction context
def classify_interactivity_level(action, data, timestamp_seconds, time_window=INTERACTIVITY_TIME_WINDOW):
    # Consider the last 10 actions for recent context
    # recent_actions = list(interaction_history)[-10:] #make a list and get
    """
    Classify the level of interactivity based on the recent actions in the specified time window.
    Parameters:
    - timestamp_seconds (float): Current timestamp in seconds.
    - time_window (int): Time window in seconds to evaluate recent actions.

    Returns:
    - str: Interactivity level ('high', 'medium', 'low').
    """

    if action == "Stop Drawing":
        duration = data.get("duration", 0)
        if duration >= DRAW_THRESHOLD: # idle for more than 10s
          print("action: stop drawing")
          return "low" 
        elif duration == DRAW_THRESHOLD_med:
            print("action: stop drawing")
            return "medium"

    #drawing thresholds
    elif action == "Start Drawing":
        duration = data.get("duration", 0)
        if duration >= DRAW_THRESHOLD: #drawing for more than 10s
            print("action: start drawing")
            return "high"
        elif duration == DRAW_THRESHOLD_med:
            print("action: start drawing")
            return "medium"

    elif action == "Reset Canvas":
        reset_count = data.get("resetCount", 0)
        if reset_count >= RESET_THRESHOLD:
            print("action: reset canvas")
            return "low" 

    # Filter actions within the time window
    recent_actions = []
    for entry in interaction_history:
        try:
            ts, action = entry  # Unpack each entry
            if timestamp_seconds - ts <= time_window:
                recent_actions.append((timestamp_seconds, action))
        except ValueError as e:
            print(f"Error unpacking entry {entry}: {e}")
            continue  # Skip malformed entries

    # Define action rewards: assign weights to interactive and non-interactive actions
    action_rewards = {action: 1 for action in interactive}
    action_rewards.update({action: 0 for action in not_interactive})

    if recent_actions:
        print(f"Action contributions to context value:")
        for _, action in recent_actions:
            print(f"Action: {action}, Reward: {action_rewards.get(action, 0)}")
        context_value = sum(action_rewards.get(action, 0) for _, action in recent_actions) / len(recent_actions)
        print(f"Computed context value: {context_value}")
    else:
        print("No recent actions found.")
    
    # Classify interactivity level based on context value thresholds
    if context_value >= 0.8:  # High interactivity threshold
        return "high"
    elif context_value <= 0.2:  # Low interactivity threshold
        return "low"
    else:
        return "medium"

#  Function to update both personality and context simultaneously
def update_personality_and_context(timestamp_seconds, action, data, last_personality_change_time, last_interactivity_update_time):
    global context_label, predicted_arm, reward, cumulativeRegret

    # Initialize time-tracking variables
    if context_label is None:
        print("initializing context_label...")
        context_label = 0  
    if predicted_arm is None:
        print("initializing predicted_arm...")
        predicted_arm = 0 
    if reward is None:
        print("initializing reward...")
        reward = 0       
        
    # Classify the interactivity level and assign rewards after interaction delay
    print("Classifying interactivity and assigning rewards")
    if timestamp_seconds - last_interactivity_update_time >= INTERACTIVITY_TIME_WINDOW:

        print(f"Classified context is: {context_label}")
        context_label = classify_interactivity_level(action, data, timestamp_seconds)
        context = contexts[context_label]  # Set the current context (low, medium, high)

        # Update the time after classifying
        last_interactivity_update_time = timestamp_seconds

        # Predict the next arm to play based on the current context
        predicted_arm, = context_agent.pull(context)
        print(f"Chosen Arm: {predicted_arm}")

        # Choose the new personality based on the predicted arm (for demonstration)
        new_personality = PERSONALITY_CHARISMATIC if predicted_arm == 1 else PERSONALITY_UNCHARISMATIC
        update_misty_personality(new_personality)  # Update personality based on reward
        last_personality_change_time = timestamp_seconds  # Update last change time

        # Observe the reward
        reward = 1 if action in interactive else 0
        print(f"Reward assigned: {reward}")

    else:
        print(f"Waiting for {INTERACTIVITY_TIME_WINDOW - (timestamp_seconds - last_interactivity_update_time):.2f} more seconds to classify context.")

    return last_personality_change_time, last_interactivity_update_time, reward, context_label, predicted_arm


# Helper function to convert timestamp to seconds since the epoch
def convert_timestamp_to_seconds(timestamp_str):
    # Assuming the timestamp is in ISO8601 format (e.g., '2024-11-16T20:49:49.382Z')
    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))  # Convert to datetime object
    return timestamp.timestamp()  # Convert datetime to seconds since epoch

######################################## BAYESIAN BANDIT HELPER FUNCTIONS ######################################################

# -------------------------------------------- HELPER FUNCTIONS -----------------------------------------------------

INTERACTION_THRESHOLD = 2*60  #in seconds

# Define the route for logging user data
@app.route('/logDrawingData', methods=['POST'])
def log_drawing_data():
    global last_interactivity_update_time, last_personality_change_time  # Track time for both windows
    global context_label, predicted_arm, observed_reward
    global timestamp_seconds
    
    try:
        # Initialize time-tracking variables if needed
        if last_personality_change_time is None:
            print("initializing personality time change")
            last_personality_change_time = 0  # Initial timestamp (e.g., start of interaction)
        if last_interactivity_update_time is None:
            print("initializing interactivity update time")
            last_interactivity_update_time = 0  # Initialize last interactivity update time
            # collect data from client (with user interactions)

        data = request.json
        print(f"Raw data: {data}")
        action = data.get("action")
        timestamp_str = data.get("timestamp")

        additionalData = data.get("additionalData")
        # print(f"Received Action: {action} at {timestamp_str}")

        if action == "Reset Initialized":
            # Reset Misty to initial state
            print("Reset Initialized: Reinitializing Misty...")
            initialize_misty()
            return jsonify({"status": "Misty reinitialized"})
        elif data.get("duration", 0) == INTERACTION_THRESHOLD:
            # end interaction
            print("End of Interaction: Reinitializing Misty...")
            initialize_misty()
            return jsonify({"status": "Misty homed"})

        # Convert the timestamp to seconds since the epoch
        timestamp_seconds = convert_timestamp_to_seconds(timestamp_str)
        # print(f"timestamp_seconds: {timestamp_seconds}")

        
        # Save user interactions (i.e. "actions") and timestamp
        interaction_history.append((timestamp_seconds, action))
       
        #update personality and context at the same time:
        last_personality_change_time, last_interactivity_update_time, observed_reward, context_label, predicted_arm = update_personality_and_context(timestamp_seconds, action, data, last_personality_change_time, last_interactivity_update_time)
        
        print(f"last personality change occured at {last_personality_change_time}")
        print(f"last interactivity time update occured at {last_interactivity_update_time}")

        #  Only log the reward and update the contextual bandit once the reward is assigned
        print("Logging drawing data...")
        log_to_csv(data=data, timestamp_in_secs=timestamp_seconds, reward_assignment=observed_reward, context=context_label, arm_selection=predicted_arm)
        
        # Update the bandit with the predicted arm and the observed reward
        print(f"Updating contextual bandit: predicted_arm={predicted_arm}, reward={observed_reward}")
        context_agent.select_for_update(predicted_arm).update(contexts[context_label], observed_reward)
     
    except Exception as e:
        print(f"Error processing data: {e}")
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

    # Add a valid return response at the end of the function
    return jsonify({"status": "success", "message": "Drawing data logged successfully"}), 200

# Run the Flask app
if __name__ == "__main__":
    # start_interaction() # intiialize the misty
    app.run(debug=False, port=80) #flask should listen here



        # print(f"Recent Actions: {recent_actions}")

    # Calculate context value: average of rewards for recent actions
    # if recent_actions:
    #     context_value = sum(action_rewards.get(action, 0) for _, action in recent_actions) / len(recent_actions)
    # else:
    #     context_value = 0  # Default to 0 if there are no recent actions

          # if action == "Stop Drawing" and additionalData.get("duration", 0) >= 5000:  # 5 seconds threshold
        #     reward = 1
        # else:
        #     reward = 0