# Code for the local API server that drives the underlying apps

from typing import Union
from fastapi import FastAPI
from pGPT_utils import *

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}