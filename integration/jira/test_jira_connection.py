import os
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

jira_url = os.getenv("JIRA_BASE_URL")
jira_email = os.getenv("JIRA_EMAIL")
jira_token = os.getenv("JIRA_API_TOKEN")

url = f"{jira_url}/rest/api/3/myself"

response = requests.get(
    url,
    auth=HTTPBasicAuth(jira_email, jira_token),
    headers={"Accept": "application/json"},
)

if response.status_code == 200:
    data = response.json()
    print("Connected to Jira successfully")
    print("User:", data.get("displayName"))
else:
    print("Jira connection failed")
    print("Status:", response.status_code)
    print(response.text)