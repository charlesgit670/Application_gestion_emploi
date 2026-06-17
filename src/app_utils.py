import pandas as pd
import json
import os

CONFIG_FILE = "config.json"

def save_data(df, data_file="data/job.csv"):
    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    df.to_csv(data_file, sep=";", index=False, encoding="utf-8")

def get_color(score):
    r = int(255 - (score * 2.55))
    g = int(score * 2.55)
    return f"rgb({r},{g},0)"