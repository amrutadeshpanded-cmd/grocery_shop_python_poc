import os
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()


class TestRailClient:
    def __init__(self):
        self.base_url = os.getenv("TESTRAIL_URL", "").rstrip("/")
        self.email = os.getenv("TESTRAIL_EMAIL")
        self.api_key = os.getenv("TESTRAIL_API_KEY")
        self.project_id = os.getenv("TESTRAIL_PROJECT_ID")

        if not all([
            self.base_url,
            self.email,
            self.api_key,
            self.project_id,
        ]):
            raise RuntimeError(
                "Missing TestRail configuration in .env"
            )

        self.auth = HTTPBasicAuth(
            self.email,
            self.api_key
        )

        self.headers = {
            "Content-Type": "application/json"
        }

    def _get(self, endpoint):
        url = f"{self.base_url}/index.php?/api/v2/{endpoint}"

        response = requests.get(
            url,
            auth=self.auth,
            headers=self.headers,
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    def _post(self, endpoint, payload):
        url = f"{self.base_url}/index.php?/api/v2/{endpoint}"

        response = requests.post(
            url,
            auth=self.auth,
            headers=self.headers,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    def get_run(self, run_id):
        return self._get(
            f"get_run/{run_id}"
        )


    def get_tests(self, run_id):
        return self._get(
            f"get_tests/{run_id}"
        )

    def get_project(self):
        return self._get(
            f"get_project/{self.project_id}"
        )

    def get_suites(self):
        return self._get(
            f"get_suites/{self.project_id}"
        )

    def get_sections(self, suite_id=None):
        endpoint = f"get_sections/{self.project_id}"

        if suite_id:
            endpoint += f"&suite_id={suite_id}"

        result = self._get(endpoint)

        if isinstance(result, dict):
            return result.get("sections", [])

        return result

    def get_cases(self, suite_id=None):
        endpoint = f"get_cases/{self.project_id}"

        if suite_id:
            endpoint += f"&suite_id={suite_id}"

        result = self._get(endpoint)

        if isinstance(result, dict):
            return result.get("cases", [])

        return result

    def create_section(
        self,
        name,
        suite_id=None,
        parent_id=None,
    ):
        payload = {
            "name": name
        }

        if suite_id:
            payload["suite_id"] = suite_id

        if parent_id:
            payload["parent_id"] = parent_id

        return self._post(
            f"add_section/{self.project_id}",
            payload,
        )

    def create_case(
        self,
        section_id,
        title,
        priority_id=None,
        type_id=None,
        custom_preconds=None,
        custom_steps=None,
        custom_expected=None,
    ):
        payload = {
            "title": title
        }

        if priority_id:
            payload["priority_id"] = priority_id

        if type_id:
            payload["type_id"] = type_id

        if custom_preconds:
            payload["custom_preconds"] = custom_preconds

        if custom_steps:
            payload["custom_steps"] = custom_steps

        if custom_expected:
            payload["custom_expected"] = custom_expected

        return self._post(
            f"add_case/{section_id}",
            payload,
        )

    def find_section_by_name(
        self,
        name,
        suite_id=None,
    ):
        sections = self.get_sections(
            suite_id=suite_id
        )

        for section in sections:
            if section.get("name", "").strip().lower() == name.strip().lower():
                return section

        return None

    def find_case_by_title(
        self,
        title,
        suite_id=None,
    ):
        cases = self.get_cases(
            suite_id=suite_id
        )

        for case in cases:
            if case.get("title", "").strip().lower() == title.strip().lower():
                return case

        return None

    def create_run(self, name, case_ids, suite_id=None, description=None):
        suite_id = suite_id or int(os.getenv("TESTRAIL_SUITE_ID"))

        payload = {
            "name": name,
            "suite_id": suite_id,
            "include_all": False,
            "case_ids": case_ids
        }

        if description:
            payload["description"] = description

        return self._post(
            f"add_run/{self.project_id}",
            payload
        )