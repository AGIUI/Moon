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

# LangChain imports
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.vectorstores import Chroma
from langchain.llms import GPT4All, LlamaCpp

load_dotenv()
EXECUTOR = ThreadPoolExecutor(max_workers=1)
THREADPOOL_TIMEOUT = 1800  # 30 minutes

# Load environment variables
persist_directory = os.path.abspath(os.environ.get('PERSIST_DIRECTORY'))
embeddings_model_name = os.environ.get('EMBEDDINGS_MODEL_NAME')
chunk_size = 500
chunk_overlap = 50

# privateGPT root folder is in src/privateGPT relative to this file
project_path = Path(__file__).parent
privateGPT_path = project_path / "src" / "privateGPT"
sys.path.append(str(privateGPT_path))
from ingest import *

ACTIONS = ["ingest", "query", "status"]

def process_documents(source_directory: str, ignored_files: List[str] = []) -> List[Document]:
    res = {'status': 0, 'message': "Success", 'data': None}
    # This part references and re-writes parts of ingest.py in the privateGPT submodule because it doesn't have a separate query function we can use directly
    logger.info(f"Loading documents from {source_directory}")
    documents = load_documents(source_directory, ignored_files)
    if not documents:
        return res
    logger.info(f"Loaded {len(documents)} new documents from {source_directory}")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    texts = text_splitter.split_documents(documents)
    logger.info(f"Split into {len(texts)} chunks of text (max. {chunk_size} tokens each)")
    res['data'] = texts
    return res

def run_ingest(taskid: str, tasklist_fp: str, source_dir: str) -> dict:
    # This part references and re-writes parts of ingest.py in the privateGPT submodule because it doesn't have a separate query function we can use directly
    res = {'status': 0, 'message': "Data Ingestion Success"}
    if not os.path.isdir(source_dir):
        res['status'] = 2
        res['message'] = f"Source directory {source_dir} does not exist"
        return res
    try:
        # Create embeddings
        embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)

        if does_vectorstore_exist(persist_directory):
            # Update and store locally vectorstore
            logger.info(f"Appending to existing vectorstore at {persist_directory}")
            db = Chroma(persist_directory=persist_directory, embedding_function=embeddings, client_settings=CHROMA_SETTINGS)
            collection = db.get()
            process_res = process_documents(source_dir, [metadata['source'] for metadata in collection['metadatas']])
            if process_res['status'] != 0:
                return process_res
            texts = process_res['data']
            if not texts:
                res['message'] = f"No new documents to ingest"
                update_res = update_task_status(
                    taskid, tasklist_fp,
                    res)
                return res
            logger.info(f"Creating embeddings. May take some minutes...")
            db.add_documents(texts)
        else:
            # Create and store locally vectorstore
            logger.info("Creating new vectorstore")
            process_res = process_documents(source_dir)
            if process_res['status'] != 0:
                return process_res
            texts = process_res['data']
            if not texts:
                res['message'] = f"No new documents to ingest"
                update_res = update_task_status(
                    taskid, tasklist_fp,
                    res)
                return res
            logger.info(f"Creating embeddings. May take some minutes...")
            db = Chroma.from_documents(texts, embeddings, persist_directory=persist_directory, client_settings=CHROMA_SETTINGS)
        db.persist()
        db = None
    except Exception:
        res['status'] = 2
        res['message'] = f"Error ingesting data: {traceback.format_exc()}"
    update_res = update_task_status(
        taskid, tasklist_fp,
        res)
    return res

def query_db(query: str, hide_source: bool = False) -> dict:
    res = {'status': 0, 'message': "Success", 'data': None}
    try:
        model_type = os.environ.get('MODEL_TYPE')
        model_path = os.environ.get('MODEL_PATH')
        model_n_ctx = os.environ.get('MODEL_N_CTX')
        target_source_chunks = int(os.environ.get('TARGET_SOURCE_CHUNKS',4))
    except:
        res['status'] = 2
        res['message'] = f"Error reading environment variables: {traceback.format_exc()}"
        return res
    
    embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)
    db = Chroma(persist_directory=persist_directory, embedding_function=embeddings, client_settings=CHROMA_SETTINGS)
    retriever = db.as_retriever(search_kwargs={"k": target_source_chunks})

    # Prepare the LLM
    match model_type:
        case "LlamaCpp":
            llm = LlamaCpp(model_path=model_path, n_ctx=model_n_ctx, verbose=False)
        case "GPT4All":
            llm = GPT4All(model=model_path, n_ctx=model_n_ctx, backend='gptj', verbose=False)
        case _default:
            res['status'] = 2
            res['message'] = f"Model {model_type} not supported!"
            return res

    try:
        # Get the answer from the chain
        qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, return_source_documents= not hide_source)

        qa_res = qa(query)
        answer, docs = qa_res['result'], [] if hide_source else qa_res['source_documents']

        # If there are sources, append each of them to the answer
        if len(docs) > 0:
            answer += "\n\nSources:"
            for doc in docs:
                answer += f"\n\n{document.page_content} ({document.metadata['source']})"
        
        # Return the answer string as data to the user
        res['data'] = {'question': query, 'answer': answer}
    except:
        res['status'] = 2
        res['message'] = f"Error querying database: {traceback.format_exc()}"
    return res

def run(args: argparse.Namespace):
    logger.debug(f"Received arguments: {args}")
    res = {'status': 0, 'message': "Success", 'data': None}

    if args.action not in ACTIONS:
        res['status'] = 2
        res['message'] = f"Invalid action: {args.action}"
        return res

    if args.action == "status":
        if args.taskid is None:
            res['status'] = 2
            res['message'] = f"taskid must be specified for status action"
        return get_task_status(args.taskid, args.tasklist)

    if args.action == "ingest":
        if args.source is None:
            res['status'] = 2
            res['message'] = f"source must be specified for ingest action"
            return res
        # Update task status
        taskid = str(uuid.uuid4())
        task = EXECUTOR.submit(run_ingest, taskid, args.tasklist, args.source)
        update_res = update_task_status(
            taskid, args.tasklist,
            {'status': 0, 'message': "Data Ingestion Started"})
        if update_res['status'] != 0:
            return update_res
        # Report the active taskid back
        res['data'] = {'taskid': taskid}
        return res

    if args.action == "query":
        if args.query is None:
            res['status'] = 2
            res['message'] = f"Query string must be specified for query action"
            return res
        # This part references and re-writes parts of privateGPT.py in the privateGPT submodule because it doesn't have a separate query function we can use directly
        return query_db(args.query, args.hide_source)

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
    parser.add_argument("--action", type=str, required=True, choices=ACTIONS, help="Action to perform")
    parser.add_argument("-q", "--query", type=str, default=None, help="Query to ask the Q&A bot (Required if action is 'query')")
    parser.add_argument("-s", "--source", type=str, default=None, help="Source folder to ingest (Required if action is 'ingest')")
    parser.add_argument("--tasklist", default=str(project_path / "tasklist.json"), help="Path to tasklist file")
    parser.add_argument("--taskid", default=None, help="Task ID (Default is None which starts a new task)")
    parser.add_argument("--hide-source", action="store_true", help="Hide source documents in output")
    args = parser.parse_args()
    res = run(args)
    logger.info(res)