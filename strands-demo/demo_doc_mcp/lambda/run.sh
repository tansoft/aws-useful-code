#!/bin/bash

# https://github.com/awslabs/aws-lambda-web-adapter/blob/main/examples/fastapi-response-streaming-zip/README.md

PATH=$PATH:$LAMBDA_TASK_ROOT/bin \
    PYTHONPATH=$PYTHONPATH:/opt/python:$LAMBDA_RUNTIME_DIR \
    exec python -m uvicorn --port=$PORT mcp_web:app
