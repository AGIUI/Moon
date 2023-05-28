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
