import sys

from google import genai

import config

client = genai.Client(api_key=config.GEMINI_API_KEY)
names = [m.name.replace("models/", "") for m in client.models.list()
         if "generateContent" in (m.supported_actions or [])]
for n in names:
    print(n)

if "--test" in sys.argv:
    print("\n--- test ---")
    for n in [x for x in names if "flash" in x][:10]:
        try:
            client.models.generate_content(model=n, contents="Say OK")
            print(f"OK    {n}")
        except Exception as e:
            print(f"FAIL  {n}: {str(e)[:90]}")