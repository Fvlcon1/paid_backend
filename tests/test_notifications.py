import requests
import time

BASE_URL = "https://api-paiv.blvcksapphire.com/ws/trigger"
USER_ID = "2" 

statuses = ["approved", "rejected", "flagged"]

for status in statuses:
    try:
        print(f"Sending test notification for status: {status}")
        response = requests.post(BASE_URL, json={"user_id": USER_ID, "status": status})
        print("Response:", response.status_code, response.json())
        time.sleep(1)  
    except Exception as e:
        print(f"Error sending {status} notification:", e)
