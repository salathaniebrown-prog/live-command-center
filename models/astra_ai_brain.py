import requests
import json
import time

# The prompt that defines Astra's persona
SYSTEM_PROMPT = "You are Astra, a highly advanced tactical AI command center. Keep your answers brief, robotic, and analytical."

def get_ai_response():
    try:
        # Send prompt to local Ollama server
        response = requests.post('http://localhost:11434/api/generate', json={
            "model": "tinyllama",
            "prompt": SYSTEM_PROMPT + "\nProvide a short status update on global network stability.",
            "stream": False
        })
        
        if response.status_code == 200:
            ai_text = response.json()['response']
            # Save the response to a file for the web UI to read
            with open("astra_voice_output.txt", "w") as f:
                f.write(ai_text.strip())
        else:
            print("AI Engine Error")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    while True:
        get_ai_response()
        time.sleep(60) # Generate a new thought every 60 seconds
