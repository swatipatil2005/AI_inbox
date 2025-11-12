import google.generativeai as genai
import os

# --- PASTE YOUR GEMINI API KEY HERE ---
GEMINI_API_KEY = 'AIzaSyChymKBe5M1PxUa9mvvRGH2JvIS1PztuYw' 
# -------------------------------------

print("Connecting to Google AI...")

try:
    genai.configure(api_key=GEMINI_API_KEY)

    print("--- Available Models for Your Key ---")
    
    # This will list all models your key can use
    for m in genai.list_models():
        # We only care about models that can 'generateContent'
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
            
    print("---------------------------------------")
    print("Find a model in the list above ('models/gemini-2.0-pro') and paste it into app.py")

except Exception as e:
    print("\n--- ERROR ---")
    print(f"An error occurred: {e}")
    print("This might be a problem with your API key or internet connection.")