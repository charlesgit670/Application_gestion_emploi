from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["os",
                 "sys",
                 "pandas",
                 "tqdm",
                 "openai",
                 "mistralai",
                 "ollama",
                 "backoff",
                 "requests",
                 "bs4",
                 "selenium",
                 "webdriver_manager",
                 "streamlit"],
    "include_files": [
        "README.md",
        "config.json",
        "config_default.json",
        "src/"
    ]
}

setup(
    name="App Gestion d'emploi",
    version="1.0",
    description="Permet de scrapper et de gérer facilement les offres d'emplois",
    options={"build_exe": build_exe_options},
    executables=[Executable("run.py", base=None)]
)