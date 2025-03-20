import hrequests

response = hrequests.get('https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles=data%20scientist&lieux=596212&typesConvention=143684&typesConvention=143685&typesConvention=143686&typesConvention=143687&typesContrat=101888&page=0&distance=10')
print(response.text)