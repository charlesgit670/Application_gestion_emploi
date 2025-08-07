import requests
import pandas as pd
import json
import hashlib

class JobFinder:

    def formatData(self, plateforme, list_title, list_content, list_company, list_link, list_datetime):
        def generate_hash(text):
            return hashlib.sha256(text.encode('utf-8')).hexdigest()

        data = {
            "title": list_title,
            "content": list_content,
            "company": list_company,
            "link": list_link,
            "date": list_datetime,
            "is_read": 0,
            "is_apply": 0,
            "is_refused": 0,
            "is_good_offer": 1,
            "comment": "",
            "score": -1,
            "custom_profile": "",
            "hash": [generate_hash(plateforme + title + company + content + str(datetime)) for title, content, company, datetime in zip(list_title, list_content, list_company, list_datetime)]
        }
        df = pd.DataFrame(data=data)
        if plateforme == "apec":
            df["date"] = pd.to_datetime(df["date"], dayfirst=True).dt.date
        else:
            df["date"] = pd.to_datetime(df["date"]).dt.date
        return df


    def getJob(self, update_callback=None):
        pass

    def get_content(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        response = requests.get(url, headers=headers)

        return response
        # Vérifier si la requête a réussi
        # if response.status_code == 200:
        #     return response
        # else:
        #     print("Erreur get content :", response.status_code)

    # def post_content(self, url, data, userToken):
    #     headers = {
    #         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    #         "Authorization": f"Bearer {userToken}",
    #         "Content-Type": "application/json"
    #     }
    #
    #     response = requests.post(url, json=data, headers=headers)
    #
    #     # Vérifier si la requête a réussi
    #     if response.status_code == 200:
    #         return response
    #     else:
    #         print("Erreur get content WelcomeToTheJungle:", response.status_code)

