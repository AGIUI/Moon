# Project Moon

This is a demonstration of a locally hosted server to perform data ingestion and Q&A retrieval in concert with a browser plugin/extension that calls it using a REST API. Uses [privateGPT](https://github.com/imartinez/privateGPT) as submodule.

## Installation

1. Clone this repository with submodules: `git clone --recurse-submodules`
2. `pip install -r requirements.txt` in both this and the privateGPT submodule under `src/privateGPT` (after submodules are also cloned)
3. Download the `ggml-gpt4all-j-v1.3-groovy.bin` model file from the [privateGPT](https://github.com/imartinez/privateGPT) submodule's README and place it in the `models` directory in project root
4. Create a `.env` file in project root as follows:

    ```
    PERSIST_DIRECTORY=DB
    MODEL_TYPE=GPT4All
    MODEL_PATH=models/ggml-gpt4all-j-v1.3-groovy.bin
    EMBEDDINGS_MODEL_NAME=all-MiniLM-L6-v2
    MODEL_N_CTX=1000
    TARGET_SOURCE_CHUNKS=4
    ```

## Usage

1. Start server with `uvicorn server:app --port [port]` (leave `--port` unset for default port of 8000)
2. Open your browser to `http://localhost:[port]/docs` and follow the Swagger instructions for REST API usage
3. (Optional) Run the test suite in `tests/api_tests.py` to ensure everything is working as expected

_(The test suite will proceed to ingest a sample document, repeatedly check its status, and then query one question against the database built from the document.)_
