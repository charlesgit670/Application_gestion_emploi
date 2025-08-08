import os
import sys
import streamlit.web.cli as stcli

def resolve_path(path: str) -> str:
    resolved_path = os.path.abspath(os.path.join(os.getcwd(), path))
    return resolved_path

if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("src/app.py"),
        "--global.developmentMode=false",
        "--server.headless=true",
    ]
    sys.exit(stcli.main())