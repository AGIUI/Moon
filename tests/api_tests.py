# API tests to call the local API server

import time
import argparse
import requests
from pathlib import Path
from loguru import logger

project_path = Path(__file__).parent.parent
COOLDOWN = 10
RETRIES = 5


parser = argparse.ArgumentParser()
parser.add_argument("-p", "--port", type=str, default="8000")
parser.add_argument("-s", "--source", type=str, default=str(project_path / "src" / "privateGPT" / "source_documents"))

args = parser.parse_args()

headers = {
    "Content-Type": "application/json"
}

# Test 1: Ingest a folder
payload = {
    "source": args.source
}
logger.info(f"Calling localhost:{args.port}/ingest with payload {payload}")
resp = requests.post(f"http://localhost:{args.port}/ingest", headers=headers, json=payload)
if resp.status_code != 200:
    logger.error(f"Error: {resp.text}")
    exit(resp.status_code)
resp_json = resp.json()
if resp_json['status'] != 0:
    logger.error(f"Error: {resp_json['message']}")
    exit(resp_json['status'])
taskid = resp_json['data']['taskid']

# Test 2: Check the status of the task periodically until it's done
for i in range(RETRIES):
    resp = requests.get(f"http://localhost:{args.port}/status/{taskid}")
    if resp.status_code != 200:
        logger.error(f"Error: {resp.text}")
        exit(resp.status_code)
    resp_json = resp.json()
    if resp_json['status'] != 0:
        logger.error(f"Error: {resp_json['message']}")
        exit(resp_json['status'])
    status = resp_json['message']
    logger.info(f"Task {taskid} status: {status}")
    if status == "Data Ingestion Success" or status == "No new documents to ingest":  # Run completed without errors
        break
    if i == RETRIES - 1:
        logger.error(f"Error: Task {taskid} did not complete after {RETRIES} retries")
        exit(2)
    time.sleep(COOLDOWN)

# Test 3: Query the database
payload = {
    'model': "model_name",
    'messages': [{'role': "user", 'content': "Why was NATO created?"}]
}
logger.info(f"Calling localhost:{args.port}/v1/chat/completions with payload {payload}")
resp = requests.post(f"http://localhost:{args.port}/v1/chat/completions", headers=headers, json=payload, timeout=300)
if resp.status_code != 200:
    logger.error(f"Error: {resp.text}")
    exit(resp.status_code)
resp_json = resp.json()
logger.info(f"Response: {resp_json}")
