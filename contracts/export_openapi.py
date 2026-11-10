#!/usr/bin/env python3
import json
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app

def export_openapi():
    openapi_schema = app.openapi()
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "openapi.json"))
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"Exported OpenAPI schema to {output_path}")

if __name__ == "__main__":
    export_openapi()
