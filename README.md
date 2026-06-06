# Local LLM Agent

## Run the API

Use the project virtualenv explicitly so the shell does not fall back to the system `uvicorn`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./run_api.sh
```

## Environment

The project is configured to use:

- `LLM_BACKEND=transformers`
- `LLM_MODEL_PATH=models/Llama-3B-Instruct`

## Notes

- Do not run `uvicorn` directly unless you know it resolves to `.venv/bin/uvicorn`.
- If you want the RAG and model stack, install `requirements-full.txt`.