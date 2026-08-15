import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client() # Initializing new client

print("Models available for your API Key:")
for model in client.models.list():
    # Only print models that generate text to keep the list clean
    if "generateContent" in model.supported_actions:
        print(model.name)