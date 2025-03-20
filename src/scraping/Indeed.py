from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


from scraping.JobFinder import JobFinder
from scraping.utils import measure_time, create_driver


class Indeed(JobFinder):

    def __init__(self):
        self.url = "https://fr.indeed.com/jobs?q=data+scientist&l=Nanterre+%2892%29&radius=10&sc=0kf%3Aattr%285QWDV%29%3B&from=searchOnDesktopSerp&vjk=02e955b74a01fc7c"

    @measure_time
    def getJob(self):
        driver = create_driver()
        driver.get(self.url)

        # Attendre que l'élément soit présent
        job_title_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "jobTitle"))
        )

        # Extraire le texte du titre
        job_title = job_title_element.text
        print("Titre du poste :", job_title)

        driver.quit()
        pass

    def formatData(self, data):
        pass

if __name__ == "__main__":
    IND = Indeed()
    df = IND.getJob()