# -----------------------------------------
# Convert AI response string to JSON safely
# -----------------------------------------

import json

def parse_response(response):
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        return json.loads(response[start:end])
    except:
        return None
