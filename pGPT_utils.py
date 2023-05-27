# Wrapper for privateGPT functions
import os
import sys
import uuid
import json
import argparse
import traceback
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_EXCEPTION

load_dotenv()
EXECUTOR = ThreadPoolExecutor(max_workers=1)
THREADPOOL_TIMEOUT = 1800  # 30 minutes

# privateGPT root folder is in src/privateGPT relative to this file
project_path = Path(__file__).parent
privateGPT_path = project_path / "src" / "privateGPT"
sys.path.append(str(privateGPT_path))
from ingest import *
from ingest import main as ingest_main

ACTIONS = ["ingest", "query", "status"]

def run_ingest(taskid: str, tasklist_fp: str) -> dict:
    res = {'status': 0, 'message': "Data Ingestion Success"}
    try:
        ingest_main()
    except BaseException:
        pass  # To ignore a normal SystemExit
    except Exception:
        res['status'] = 2
        res['message'] = f"Error ingesting data: {traceback.format_exc()}"
    update_res = update_task_status(
        taskid, tasklist_fp,
        res)
    return update_res

def main(args: argparse.Namespace):
    res = {'status': 0, 'message': "Success", 'data': None}

    if args.action not in ACTIONS:
        res['status'] = 2
        res['message'] = f"Invalid action: {args.action}"
        return res

    if args.action == "status":
        if args.taskid is None:
            res['status'] = 2
            res['message'] = f"taskid must be specified for status action"
        res['data'] = get_task_status(args.taskid, args.tasklist)
        return res

    if args.action == "ingest":
        if os.getenv("SOURCE_DIRECTORY") is None:
            res['status'] = 2
            res['message'] = f"SOURCE_DIRECTORY environment variable must be set"
        # Update task status
        taskid = str(uuid.uuid4())
        task = EXECUTOR.submit(run_ingest, taskid, args.tasklist)
        update_res = update_task_status(
            taskid, args.tasklist,
            {'status': 0, 'message': "Data Ingestion Started"})
        if update_res['status'] != 0:
            return update_res
        # Report the active taskid back
        res['data'] = {'taskid': taskid}
        return res


def load_tasklist(tasklist_fp: str) -> dict:
    """Load tasklist"""
    if not os.path.exists(tasklist_fp):
        tasks = {}
        json.dump(tasks, open(tasklist_fp, "w"))
    tasks = json.load(open(tasklist_fp))
    return tasks

def get_task_status(taskid: str, tasklist_fp: str) -> dict:
    """Get status of a task"""
    tasks = load_tasklist(tasklist_fp)
    return tasks[taskid]

def update_task_status(taskid: str, tasklist_fp: str, data) -> dict:
    """Update status of a task"""
    res = {'status': 0, 'message': "Task status updated"}
    try:
        tasks = load_tasklist(tasklist_fp)
        if taskid not in tasks:
            tasks[taskid] = {}
        tasks[taskid].update(data)
        json.dump(tasks, open(tasklist_fp, "w"))
    except:
        res['status'] = 2
        res['message'] = f"Error updating task status: {traceback.format_exc()}"
    return res

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=ACTIONS, help="Action to perform")
    parser.add_argument("--tasklist", default="tasklist.json", help="Path to tasklist file")
    parser.add_argument("--taskid", default=None, help="Task ID (Default is None which starts a new task)")
    args = parser.parse_args()
    res = main(args)
    logger.info(res)