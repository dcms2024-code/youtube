"""Ejecutar una vez en Windows para generar token.json"""
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CREDENTIALS_FILE = r"C:\Users\andre\Downloads\client_secret_54387645613-dclt50r9adrmjbsadhlnoj9m9e2do4io.apps.googleusercontent.com.json"
TOKEN_FILE = r"C:\Users\andre\youtube_bot\token.json"

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
creds = flow.run_local_server(port=0)
Path(TOKEN_FILE).write_text(creds.to_json())
print(f"token.json guardado en {TOKEN_FILE}")
