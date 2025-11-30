import time
import requests
import os
import json
from dotenv import load_dotenv
from . import metrics

load_dotenv()

INGESTION_URL = os.getenv("INGESTION_URL", "http://localhost:8001/ingest")
AGENT_ID = os.getenv("AGENT_ID", "agent-1")
INTERVAL = int(os.getenv("INTERVAL", "1"))

def main():
    print(f"Starting Agent {AGENT_ID}...")
    print(f"Sending metrics to {INGESTION_URL} every {INTERVAL} seconds.")
    
    while True:
        try:
            data = metrics.collect_all_metrics()
            data["agent_id"] = AGENT_ID
            
            # print(json.dumps(data, indent=2)) # Debug
            
            response = requests.post(INGESTION_URL, json=data, timeout=2)
            if response.status_code != 200:
                print(f"Error sending metrics: {response.status_code} - {response.text}")
            
        except requests.exceptions.ConnectionError:
            print(f"Connection error to {INGESTION_URL}. Retrying...")
        except Exception as e:
            print(f"Error: {e}")
            
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
