#!/bin/bash
cd /Users/alisherfounder/code/decentrathon/nosleep/backend
source /Users/alisherfounder/code/decentrathon/nosleep/.venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
