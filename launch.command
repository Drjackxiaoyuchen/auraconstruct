#!/bin/zsh
set -e
cd "${0:A:h}"
if [[ ! -x .venv/bin/auraconstruct ]]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -e .
fi
.venv/bin/auraconstruct serve
