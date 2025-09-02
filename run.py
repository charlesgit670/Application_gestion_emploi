import os
import sys
import streamlit.web.cli as stcli

# force l'utilisation de utf8 pour les pc chinois
os.environ["PYTHONUTF8"] = "1"
sys.stdout.reconfigure(encoding='utf-8')

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