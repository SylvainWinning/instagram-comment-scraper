import json
import os
import gspread
from google.oauth2.service_account import Credentials

# On récupère la clé JSON du compte de service depuis une variable d'env
service_account_info = json.loads(os.environ['GCP_SERVICE_ACCOUNT'])
creds = Credentials.from_service_account_info(service_account_info, scopes=["https://www.googleapis.com/auth/spreadsheets"])

# Identifiant de ta feuille Google (dans l’URL)
SPREADSHEET_ID = "ton_identifiant_de_feuille"

# Ouvre la feuille
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.sheet1  # par exemple la première feuille

# Ex: on lit ton fichier local output.json (généré par script.py)
with open("output.json", "r") as f:
    data = json.load(f)

# Suppose que data est une liste de listes ou un tableau
# On vide la feuille ou on écrit à partir de la première cellule
worksheet.clear()

# Exemple : si data est du type:
# [
#   ["Nom", "Age"],
#   ["Alice", 30],
#   ["Bob", 25]
# ]
worksheet.update("A1", data)

print("Données envoyées à Google Sheets !")
