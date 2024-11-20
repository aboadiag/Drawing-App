import os
from gtts import gTTS
import requests

# Define constants
MISTY_URL = "http://172.26.189.224"
AUDIO_PLAY_ENDPOINT = "/api/audio/play"
AUDIO_FILES_DIR = "misty_audio_files"
DEFAULT_VOLUME = 50
LOCAL_SERVER_IP = "172.26.28.222"  # Replace with your local machine's IP address
LOCAL_SERVER_PORT = 8000
url = f"{MISTY_URL}{AUDIO_PLAY_ENDPOINT}"


# Ensure the directory exists
if os.path.exists(AUDIO_FILES_DIR):
    if not os.path.isdir(AUDIO_FILES_DIR):
        raise FileExistsError(f"A file named '{AUDIO_FILES_DIR}' exists. Please rename or remove it.")
else:
    os.makedirs(AUDIO_FILES_DIR, exist_ok=True)


def generate_tts(text, filename):
    """Generate TTS audio and save to the specified directory."""
    try:
        # Create TTS
        tts = gTTS(text=text, lang='en')
        file_path = os.path.join(AUDIO_FILES_DIR, filename)
        
        # Save audio file
        tts.save(file_path)
        print(f"Audio file saved at: {file_path}")
        return file_path
    except Exception as e:
        print(f"Error generating TTS: {e}")
        return None


# IF YOU WANT TO TEST also playing new audio files:
# def play_audio_on_misty(file_path, volume=DEFAULT_VOLUME):
#     """Send a POST request to Misty to play audio."""
#     try:
#         # Construct the file URL served by the local server
#         filename = os.path.basename(file_path)
#         file_url = f"http://{LOCAL_SERVER_IP}:{LOCAL_SERVER_PORT}/{AUDIO_FILES_DIR}/{filename}"
        
#         # Send the request
#         response = requests.post(
#             url,
#             headers={"Content-Type": "application/json"},
#             json={
#                 "FileName": file_url,
#                 "Volume": DEFAULT_VOLUME
#             }
#         )
#         if response.status_code == 200:
#             print("Audio played successfully on Misty.")
#         else:
#             print(f"Error playing audio on Misty: {response.status_code} - {response.text}")
#     except requests.exceptions.RequestException as e:
#         print(f"Error playing audio on Misty: {e}")


if __name__ == "__main__":
    # Example use:
        # text_to_convert = "Hello! I am Misty, your friendly robot."
        # audio_filename = "misty_greeting.mp3"
        # audio_path = generate_tts(text_to_convert, audio_filename)

    # Generate audio speech data
    speech_char1 = {"Please continue drawing for a few more seconds."}
    sc1_aud_file = "misty_char1.mp3"
    aud_pa_sc1 = generate_tts(speech_char1, sc1_aud_file)

    speech_unchar1 = {"Maybe you could continue drawing?"}
    suc1_aud_file = "misty_unchar1.mp3"
    aud_pa_suc1 = generate_tts(suc1_aud_file, suc1_aud_file)



    # Play audio on Misty (adjust volume if needed)
    # if audio_path:
    #     play_audio_on_misty(audio_path)
