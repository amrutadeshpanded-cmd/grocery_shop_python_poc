import os
import re

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth


load_dotenv()


def clean_testrail_text(value):
    if not value:
        return ""

    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def load_master_cases():
    testrail_url = os.getenv(
        "TESTRAIL_URL"
    )

    testrail_email = os.getenv(
        "TESTRAIL_EMAIL"
    )

    testrail_api_key = os.getenv(
        "TESTRAIL_API_KEY"
    )

    project_id = os.getenv(
        "TESTRAIL_PROJECT_ID"
    )

    suite_id = os.getenv(
        "TESTRAIL_SUITE_ID"
    )

    if not all([
            testrail_url,
            testrail_email,
            testrail_api_key,
            project_id,
            suite_id
        ]):
            raise RuntimeError(
                "TestRail environment variables are missing."
            )
    

    sections_url = (
    f"{testrail_url}/index.php?"
    f"/api/v2/get_sections/{project_id}"
    f"&suite_id={suite_id}"
)

    sections_response = requests.get(
        sections_url,
        auth=HTTPBasicAuth(
            testrail_email,
            testrail_api_key
        ),
        headers={
            "Content-Type": "application/json"
        }
    )

    if sections_response.status_code != 200:
        raise RuntimeError(
            f"TestRail sections query failed. "
            f"Status: {sections_response.status_code}\n"
            f"{sections_response.text}"
        )

    sections_data = sections_response.json()

    raw_sections = (
        sections_data.get("sections", [])
        if isinstance(sections_data, dict)
        else sections_data
    )

    section_map = {
        section.get("id"): section.get("name", "")
        for section in raw_sections
    }


    
    url = (
        f"{testrail_url}/index.php?"
        f"/api/v2/get_cases/{project_id}"
        f"&suite_id={suite_id}"
    )

    response = requests.get(
        url,
        auth=HTTPBasicAuth(
            testrail_email,
            testrail_api_key
        ),
        headers={
            "Content-Type": "application/json"
        }
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"TestRail query failed. "
            f"Status: {response.status_code}\n"
            f"{response.text}"
        )

    data = response.json()

    raw_cases = (
        data.get("cases", [])
        if isinstance(data, dict)
        else data
    )

    cases = []

    for case in raw_cases:
        cases.append({
        "case_id": case.get("id"),
        "title": case.get("title", ""),
        "section_id": case.get("section_id"),
        "section": section_map.get(
            case.get("section_id"),
            ""
        ),
        "preconditions": clean_testrail_text(
            case.get("custom_preconds")
        ),
        "steps": clean_testrail_text(
            case.get("custom_steps")
        ),
        "expected_result": clean_testrail_text(
            case.get("custom_expected")
        ),
        "steps_separated": case.get(
            "custom_steps_separated"
        )
    })
    return cases

def create_test_run(
    run_name,
    case_ids,
    description=""
):
    testrail_url = os.getenv(
        "TESTRAIL_URL"
    )

    testrail_email = os.getenv(
        "TESTRAIL_EMAIL"
    )

    testrail_api_key = os.getenv(
        "TESTRAIL_API_KEY"
    )

    project_id = os.getenv(
        "TESTRAIL_PROJECT_ID"
    )

    suite_id = os.getenv(
        "TESTRAIL_SUITE_ID"
    )

    if not all([
        testrail_url,
        testrail_email,
        testrail_api_key,
        project_id,
        suite_id
    ]):
        raise RuntimeError(
            "TestRail environment variables are missing."
        )

    url = (
        f"{testrail_url}/index.php?"
        f"/api/v2/add_run/{project_id}"
    )

    payload = {
    "suite_id": int(suite_id),
    "name": run_name,
    "description": description,
    "include_all": False,
    "case_ids": case_ids
}

    response = requests.post(
        url,
        json=payload,
        auth=HTTPBasicAuth(
            testrail_email,
            testrail_api_key
        ),
        headers={
            "Content-Type": "application/json"
        }
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"TestRail run creation failed. "
            f"Status: {response.status_code}\n"
            f"{response.text}"
        )

    return response.json()

def create_test_case(
    section_id,
    title
):
    testrail_url = os.getenv(
        "TESTRAIL_URL"
    )

    testrail_email = os.getenv(
        "TESTRAIL_EMAIL"
    )

    testrail_api_key = os.getenv(
        "TESTRAIL_API_KEY"
    )

    if not all([
        testrail_url,
        testrail_email,
        testrail_api_key
    ]):
        raise RuntimeError(
            "TestRail environment variables are missing."
        )

    url = (
        f"{testrail_url}/index.php?"
        f"/api/v2/add_case/{section_id}"
    )

    payload = {
        "title": title
    }

    response = requests.post(
        url,
        json=payload,
        auth=HTTPBasicAuth(
            testrail_email,
            testrail_api_key
        ),
        headers={
            "Content-Type": "application/json"
        }
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"TestRail case creation failed. "
            f"Status: {response.status_code}\n"
            f"{response.text}"
        )

    return response.json()