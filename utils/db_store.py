# -----------------------------------------
# Save DB connections locally
# -----------------------------------------

import json
import os

FILE = "saved_connections.json"

def load_connections():

    if not os.path.exists(FILE):
        return []

    with open(FILE, "r") as f:
        return json.load(f)


def save_connection(data):

    items = load_connections()

    # update existing if same name
    items = [x for x in items if x["name"] != data["name"]]
    items.append(data)

    with open(FILE, "w") as f:
        json.dump(items, f, indent=2)