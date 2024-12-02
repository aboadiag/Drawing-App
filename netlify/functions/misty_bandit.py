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

interaction_history = deque(maxlen=10)  # Each entry in the deque will be a tuple (timestamp_seconds, interaction_value): Store timestamps and interactivity scores (1 or 0)
INTERACTIVITY_TIME_WINDOW  = 10  # Time window for interactivity level classification (in seconds)
PERSONALITY_CHANGE_TIME_WINDOW = 20  # Time window for changing the personality (in seconds)

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
                'timestamp', 'action', 'reward_assignment', 'context', 'arm_selection', 'log_timestamp'
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
            'timestamp', 'action', 'reward_assignment', 'context', 'arm_selection', 'log_timestamp'
        ])
        writer.writerow({
            'timestamp': data['timestamp'],
            'action': data['action'],
            # 'interaction_value': data['interaction_value'],
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
# Define the personality types and interactivity levels
PERSONALITY_CHARISMATIC = "Charismatic"
PERSONALITY_UNCHARISMATIC = "Uncharismatic"

INTERACTIVITY_LOW = "low"
INTERACTIVITY_MEDIUM = "medium"
INTERACTIVITY_HIGH = "high"

# Define a circular queue for personality changes with a fixed size
class CircularQueue:
    def __init__(self, max_size):
        self.queue = deque(maxlen=max_size)
    
    def enqueue(self, item):
        if item not in [PERSONALITY_CHARISMATIC, PERSONALITY_UNCHARISMATIC]:
            raise ValueError("Item must be Charismatic or Uncharismatic")
        self.queue.append(item)
    
    def dequeue(self):
        if self.queue:
            return self.queue.popleft()
        return None
    
    def is_empty(self):
        return len(self.queue) == 0
    
# Create a queue with a size of 2 (Charismatic and Uncharismatic)
personality_queue = CircularQueue(max_size=2)

# Constants
# PERSONALITY_CHANGE_TIME_WINDOW = 20  # Example window of 60 seconds
# # last_personality_change_time = 0  # Track when the last personality change occurred
# # last_interactivity_update_time = 0  # Last interactivity time
# # context = None  # Current context (interactivity level)
# # predicted_arm = None  # Predicted arm selection (not used in this specific code, but can be part of the context)

    # Track the last interaction time and last personality change time
last_interactivity_update_time = None  # Timestamp of the last interactivity update
last_personality_change_time = None  # Timestamp of the last personality change


# Update the Misty expressions and actions based on the current personality
def update_misty_personality(current_personality):
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

# def time_since_last_change(timestamp_seconds, last_personality_change_time):
#     """Returns the time in seconds since the last personality change."""
#     print(f"Time elapsed: {timestamp_seconds - last_personality_change_time}")
#     return timestamp_seconds - last_personality_change_time

# Function to handle queuing of personality changes
def maybe_queue_personality_change(new_personality, personality_queue, timestamp_seconds, last_personality_change_time):
    """Only enqueues the personality change if enough time has passed."""
    # Example logic
    if last_personality_change_time is None:
        print("Initializing last_personality_change_time for the first time.")
        last_personality_change_time = timestamp_seconds
 
    delta_t = timestamp_seconds - last_personality_change_time
    print(f"Time elapsed: {delta_t}")

    if delta_t >= PERSONALITY_CHANGE_TIME_WINDOW:
        personality_queue.enqueue(new_personality)
        print(f"Personality change enqueued: {new_personality}")
        print(f"Current Personality Queue: {list(personality_queue.queue)}")


        last_personality_change_time = timestamp_seconds  # Update the last change time
        print(f"last personality change at {last_personality_change_time}")
    else:
        print(f"Not enough time has passed. Time since last change: {delta_t} seconds.")

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


# ------------------- CHANGING MISTY'S PERSONA ------------------------------------ #
######################################## MISTY HELPER FUNCTIONS ######################################################

######################################## BAYESIAN BANDIT HELPER FUNCTIONS ######################################################

# Function to classify the interaction context
def classify_interactivity_level(timestamp_seconds):
    # Consider the last 10 actions for recent context
    recent_actions = list(interaction_history)[-10:] #make a list and get
    
    # Define action rewards: assign weights to interactive and non-interactive actions
    action_rewards = {
        action: 1 for action in interactive
    }
    action_rewards.update({
        action: 0 for action in not_interactive
    })
    
    # Calculate context value: average of rewards for recent actions
    if recent_actions:
        context_value = sum(action_rewards[action] for _, action in recent_actions) / len(recent_actions)
    else:
        context_value = 0  # Default to 0 if there are no recent actions
    
    # Classify interactivity level based on context value thresholds
    if context_value >= 0.8:  # High interactivity threshold
        return "high"
    elif context_value <= 0.2:  # Low interactivity threshold
        return "low"
    else:
        return "medium"

# Helper function to convert timestamp to seconds since the epoch
def convert_timestamp_to_seconds(timestamp_str):
    # Assuming the timestamp is in ISO8601 format (e.g., '2024-11-16T20:49:49.382Z')
    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))  # Convert to datetime object
    return timestamp.timestamp()  # Convert datetime to seconds since epoch

######################################## BAYESIAN BANDIT HELPER FUNCTIONS ######################################################

# -------------------------------------------- HELPER FUNCTIONS -----------------------------------------------------
# Global flag to track Misty's execution state
misty_action_in_progress = False

def execute_misty_action(personality_queue):
    global misty_action_in_progress
    
    if misty_action_in_progress:
        # Skip if Misty is already performing an action
        print("Misty is still executing an action. Waiting...")
        return
    
    if personality_queue.is_empty():
        #Choose the new personality based on the predicted arm (for demonstration)
        new_personality = PERSONALITY_CHARISMATIC if predicted_arm == 1 else PERSONALITY_UNCHARISMATIC
        maybe_queue_personality_change(new_personality, personality_queue, timestamp_seconds, last_personality_change_time)


    # If no action is in progress, proceed to dequeue and execute
    if not personality_queue.is_empty():
        current_personality = personality_queue.dequeue()
        print(f"Dequeued personality: {current_personality}")
        misty_action_in_progress = True  # Set the flag
        
        # Call Misty actions
        try:
            print("Proceed with Misty personality change...")
            update_misty_personality(current_personality)
        except Exception as e:
            print(f"Error executing Misty action: {e}")
            misty_action_in_progress = False  # Reset flag on failure
            return

        # Once actions complete, reset the flag
        misty_action_in_progress = False
        print("Misty action completed. Ready for the next action.")
    else:
        print("No actions in the queue.")

first_interaction = True
# Main loop that runs before handling the drawing data
def main_loop():
    global misty_initialized
    
    if misty_initialized is False:
        print("Initializing Misty...")
        initialize_misty()  # Initialize Misty
        misty_initialized = True  # Mark Misty as initialized

# Define the route for logging user data
@app.route('/logDrawingData', methods=['POST'])
def log_drawing_data(): 
    global first_interaction
    global last_interactivity_update_time, last_personality_change_time  # Track time for both windows
    global context, predicted_arm
    global timestamp_seconds
    # global last_chosen_arm
    main_loop()

    # Initialize time-tracking variables if needed
    if last_personality_change_time is None:
        print("initializing personality time change")
        last_personality_change_time = 0  # Initial timestamp (e.g., start of interaction)
    if last_interactivity_update_time is None:
        print("initializing interactivity update time")
        last_interactivity_update_time = 0  # Initialize last interactivity update time
    
    try:
        # collect data from client (with user interactions)

        data = request.json
        print(f"Raw payload: {request.data}")  # See the raw request body
        print(f"Parsed JSON: {data}") 

        action = data.get("action")
        timestamp_str = data.get("timestamp")
        print(f"Received Action: {action} at {timestamp_str}")

        # Convert the timestamp to seconds since the epoch
        timestamp_seconds = convert_timestamp_to_seconds(timestamp_str)
        print(f"timestamp_seconds: {timestamp_seconds}")

        #save user interactions (i.e. "actions") and timestamp
        interaction_history.append((timestamp_seconds, action))

        # Classify the interactivity level based on recent actions
        context_label = classify_interactivity_level(timestamp_seconds)
        context = contexts[context_label]  # Set the current context (low, medium, high)
        last_interactivity_update_time = timestamp_seconds  # Update the time after classifying
        # print(f"Context is: {context_label}")
        print(f"what is the context: {context}")

        # Assign rewards: interaction_value          
        reward = 1 if action in interactive else 0
        print(f"reward value is {reward}")

        #predict the next arm to play
        predicted_arm, = context_agent.pull(context)
        print(f"Chosen Arm: {predicted_arm}")

        # print(f"Timestamps seconds that have passed {timestamp_seconds}")

        # check when its time to execute
        execute_misty_action(personality_queue)

        # Update the last personality change time
        # last_personality_change_time = timestamp_seconds  
        # print(f"last personality change at {last_personality_change_time}")

        # Update the bandit with the predicted arm to update with context and the observed reward
        context_agent.select_for_update(predicted_arm).update(context, reward)

    # Log the arm selection after the agent's decision
    # log_to_csv(data, reward_assignment=reward, context=context_label, arm_selection=predicted_arm)
     
    except Exception as e:
        print(f"Error processing data: {e}")
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

    # Add a valid return response at the end of the function
    return jsonify({"status": "success", "message": "Drawing data logged successfully"}), 200

# Run the Flask app
if __name__ == "__main__":
    # start_interaction() # intiialize the misty
    app.run(debug=False, port=80) #flask should listen here
