import os
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

testrail_url = os.getenv("TESTRAIL_URL")
testrail_email = os.getenv("TESTRAIL_EMAIL")
testrail_api_key = os.getenv("TESTRAIL_API_KEY")
project_id = os.getenv("TESTRAIL_PROJECT_ID")

url = f"{testrail_url}/index.php?/api/v2/get_project/{project_id}"

response = requests.get(
    url,
    auth=HTTPBasicAuth(testrail_email, testrail_api_key),
    headers={"Content-Type": "application/json"},
)

if response.status_code == 200:
    project = response.json()

    print("Connected to TestRail successfully")
    print("Project:", project.get("name"))
    print("Project ID:", project.get("id"))
else:
    print("TestRail connection failed")
    print("Status:", response.status_code)
    print(response.text)