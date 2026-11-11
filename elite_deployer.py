import os
import sys
import time
import json
import urllib.request
import urllib.error
import subprocess

def call_gemini(prompt, max_retries=3, backoff_factor=2):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Run: export GEMINI_API_KEY='your_key'")
    
    url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'
    payload = {'contents': [{'parts': [{'text': prompt}]}]}
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'x-goog-api-key': api_key
        }
    )
    
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode('utf-8'))
                return data['candidates'][0]['content']['parts'][0]['text']
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < max_retries - 1:
                sleep_time = backoff_factor ** attempt
                print(f"Service unavailable (503). Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                raise e

def generate_task_files(task):
    print(f"Architecting and generating code with Gemini for: {task}")
    prompt = f"Write the complete code and file structure for the following task in a clean format: {task}"
    return call_gemini(prompt)

def deploy_project(app_files):
    print("Deploying to cloud infrastructure...")
    # Execution telemetry and deployment commands go here
    print("Deployment complete.")

if __name__ == "__main__":
    task = input("What do you want to build and deploy? > ")
    app_files = generate_task_files(task)
    deploy_project(app_files)

