import time
import re
import json
import functools
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import backoff
from ollama import generate
from pydantic import BaseModel

# from scraping.prompts import my_resume, instruction_custom_profile, instruction_scoring

class Format(BaseModel):
    response: int
    justification: str

def measure_time(func):
    """Annotation pour mesurer le temps d'exécution d'une fonction"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()  # Démarre le chrono
        result = func(*args, **kwargs)
        end_time = time.time()  # Arrête le chrono
        execution_time = end_time - start_time

        if args and hasattr(args[0], "__class__"):
            class_name = args[0].__class__.__name__
            print(f"Temps d'exécution de {class_name}.{func.__name__}: {execution_time:.2f} secondes")
        else:
            print(f"Temps d'exécution de {func.__name__}: {execution_time:.2f} secondes")

        # print(f"Temps d'exécution de {func.__name__}: {execution_time:.2f} secondes")
        return result
    return wrapper

# Fonction pour créer un driver
def create_driver():

    options = Options()
    # options.add_argument("user-data-dir=C:\\Users\\charles\\AppData\\Local\\Google\\Chrome\\User Data")
    options.add_argument("--headless")  # Mode headless
    options.add_argument("--disable-gpu")  # Recommandé pour éviter certains bugs en mode headless
    options.add_argument("--window-size=1920x1080")  # Taille de la fenêtre (facultatif)
    options.add_argument("--no-sandbox")  # Utile dans certains environnements Linux
    options.add_argument("--disable-dev-shm-usage")  # Évite certains problèmes de mémoire

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

@backoff.on_exception(backoff.expo, Exception)
def add_LLM_comment(client_LLM, llm_config, row):
    """
    Modifier l'instruction_scoring en fonction de ce que vous recherchez
    """
    if llm_config["generate_score"]:
        title = row["title"]
        company = row["company"]
        description = row["content"]

        if llm_config["provider"] == "Local":
            response = generate(
                model="gemma3:12b",
                options={
                    "temperature": 0.1,
                },
                format={
                    "type": "object",
                    "properties": {
                        "reponse": {
                            "type": "number"
                        },
                        "justification": {
                            "type": "string",
                        },
                    }
                },
                prompt=llm_config["prompt_score"] + "\n" + company + "\n" + title + "\n" + description,

            )
            json_output = json.loads(response.response)
        elif llm_config["provider"] == "ChatGPT":
            response = client_LLM.responses.parse(
                model="gpt-4o-mini",
                instructions=llm_config["prompt_score"],
                temperature=0.1,
                input=company + "\n" + title + "\n" + description,
                text_format=Format
            )
            json_output = json.loads(response.output_text)
        elif llm_config["provider"] == "Mistral":
            chat_response = client_LLM.chat.complete(
                model="mistral-large-latest",
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": llm_config["prompt_score"] + "\n" + company + "\n" + title + "\n" + description,
                    },
                ],
                response_format={
                    "type": "json_object",
                    "json_schema": {
                        "reponse": {
                            "type": "integer"
                        },
                        "justification": {
                            "type": "string",
                        },
                    }
                }
            )
            json_output = json.loads(chat_response.choices[0].message.content)

        row["is_good_offer"] = 1 if int(json_output["reponse"]) >= 50 else 0
        row["comment"] = json_output["justification"]
        row["score"] = int(json_output["reponse"])

    if llm_config["generate_custom_profile"] and (
            not llm_config["generate_score"] or row["is_good_offer"] == 1
    ):
        row["custom_profile"] = add_custom_cv_profile(client_LLM, llm_config, row)

    return row


def add_custom_cv_profile(client_LLM, llm_config, row):
    if llm_config["provider"] == "Local":
        response = generate(
            model="gemma3:12b",
            options={
                "temperature": 0.3,
            },
            prompt=llm_config["cv"] + "\n" + row["content"] + "\n" + llm_config["prompt_custom_profile"],
        )
        output_text = response.response
    elif llm_config["provider"] == "ChatGPT":
        response = client_LLM.responses.create(
            model="gpt-4o-mini",
            instructions=llm_config["prompt_custom_profile"],
            temperature=0.3,
            input=llm_config["cv"] + "\n" + row["content"],
        )
        output_text = response.output_text
    elif llm_config["provider"] == "Mistral":
        chat_response = client_LLM.chat.complete(
            model="mistral-large-latest",
            temperature=0.1,
            messages=[
                {
                    "role": "user",
                    "content": llm_config["cv"] + "\n" + row["content"],
                },
            ],
        )
        output_text = chat_response.choices[0].message.content

    return output_text

