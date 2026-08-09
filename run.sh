#!/bin/bash
# Run grants scraper using autointern's Python 3.9 venv
PYTHON="/Users/siddharthsudunagunta/autointern/backend/.venv/bin/python"
cd "$(dirname "$0")"
$PYTHON main.py "$@"
