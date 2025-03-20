import requests
import pandas as pd

class JobFinder:

    # def __init__(self, job_title, contract):
    #     self.job_title = job_title
    #     self.contract = contract

    def formatData(self, list_title, list_content, list_company, list_link):
        data = {
            "title": list_title,
            "content": list_content,
            "company": list_company,
            "link": list_link,
            "is_read": 0,
            "is_apply": 0,
            "is_refused": 0
        }
        return pd.DataFrame(data=data)


    def getJob(self):
        pass

    def get_content(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        response = requests.get(url, headers=headers)

        # Vérifier si la requête a réussi
        if response.status_code == 200:
            return response
        else:
            print("Erreur get content :", response.status_code)

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

