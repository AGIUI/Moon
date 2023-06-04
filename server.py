# Code for the local API server that drives the underlying apps

from argparse import Namespace
from pydantic import BaseModel
from fastapi import FastAPI
from pathlib import Path
from pGPT_utils import *

project_path = Path(__file__).parent
app = FastAPI()

class QueryPayload(BaseModel):
    query: str
    hide_source: bool = False

class IngestionPayload(BaseModel):
    source: str

class RunResponse(BaseModel):
    status: int
    message: str
    data: dict | None = None

class ChatCompletionPayload(BaseModel):
    model: str
    messages: list
    temperature: float = 1
    top_p: float = 1
    n: int = 1
    stream: bool = False
    stop: str | list | None = None
    max_tokens: int | None = None
    presence_penalty: float = 0
    frequency_penalty: float = 0
    logit_bias: dict | None = None
    user: str | None = None

class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    choices: list
    usage: dict

def query_messages(messages: list) -> ChatCompletionResponse:
    res = {
        'id': None,
        'object': 'chat.completion',
        'created': None,
        'choices': [],
        'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    }
    # Only last entry of the messages list is considered query string
    query = messages[-1]['content']
    query_res = run(Namespace(action="query", query=query, hide_source=True))
    res['id'] = query_res['data']['id']
    res['created'] = query_res['data']['created']
    if query_res['status'] != 0:
        res['choices'] = [{'role': "system", 'content': query_res['message']}]
    else:
        res['choices'] = [{'role': "system", 'content': query_res['data']['answer']}]
    return res

@app.get("/")
def read_root():
    return {"Swagger": "/docs"}

@app.get("/status/{taskid}")
def get_status(taskid: str) -> RunResponse:
    return run(Namespace(action="status", taskid=taskid, tasklist=str(project_path / "tasklist.json")))

@app.post("/ingest")
def ingest(payload: IngestionPayload) -> RunResponse:
    return run(Namespace(action="ingest", source=payload.source, tasklist=str(project_path / "tasklist.json")))

@app.post("/query")
def query(payload: QueryPayload) -> RunResponse:
    return run(Namespace(action="query", query=payload.query, hide_source=payload.hide_source))

@app.post("/v1/chat/completions")
def chat_completions(payload: ChatCompletionPayload) -> ChatCompletionResponse:
    return query_messages(payload.messages)
