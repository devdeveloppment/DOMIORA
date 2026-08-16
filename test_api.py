import requests

API_KEY = "your_gemini_api_key_here"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

print("=== Testing Gemini API ===")
print(f"API Key: {API_KEY[:20]}...")
print(f"Endpoint: {GEMINI_API_URL}")

try:
    response = requests.post(
        f"{GEMINI_API_URL}?key={API_KEY}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": [{"text": "Bonjour, réponds simplement 'OK'"}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 50,
            }
        },
        timeout=15,
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"\nResponse Body:\n{response.text}")
    
    if response.status_code == 200:
        data = response.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"\n✅ Success! Reply: {reply}")
        else:
            print(f"\n❌ No candidates in response")
    else:
        print(f"\n❌ API Error: {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Exception: {str(e)}")
    print(f"Error type: {type(e).__name__}")
