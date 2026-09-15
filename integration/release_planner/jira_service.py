import os

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth


load_dotenv()


def extract_jira_text(value):
    if not value:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return " ".join(
            extract_jira_text(item)
            for item in value
        ).strip()

    if isinstance(value, dict):
        parts = []

        if value.get("text"):
            parts.append(
                value["text"]
            )

        for child in value.get(
            "content",
            []
        ):
            child_text = extract_jira_text(
                child
            )

            if child_text:
                parts.append(
                    child_text
                )

        return " ".join(
            parts
        ).strip()

    return str(value)



def get_release_jira_issues(
    target_release
):
    jira_url = os.getenv(
        "JIRA_BASE_URL"
    )

    jira_email = os.getenv(
        "JIRA_EMAIL"
    )

    jira_token = os.getenv(
        "JIRA_API_TOKEN"
    )

    if not all([
        jira_url,
        jira_email,
        jira_token
    ]):
        raise RuntimeError(
            "Jira environment variables are missing."
        )

    jql = (
    f'"Target Release" = "{target_release}" '
    f'ORDER BY key ASC'
)

    url = (
        f"{jira_url}/rest/api/3/search/jql"
    )

    response = requests.get(
        url,
        auth=HTTPBasicAuth(
            jira_email,
            jira_token
        ),
        headers={
            "Accept": "application/json"
        },
        params={
            "jql": jql,
            "maxResults": 100,
            "fields": (
                "summary,"
                "description,"
                "status,"
                "components,"
                "labels,"
                "fixVersions"
            )
        }
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Jira query failed. "
            f"Status: {response.status_code}\n"
            f"{response.text}"
        )

    data = response.json()

    issues = []

    for issue in data.get(
        "issues",
        []
    ):
        fields = issue.get(
            "fields",
            {}
        )

        issues.append({
            "key": issue.get(
                "key",
                ""
            ),
            "summary": fields.get(
                "summary",
                ""
            ),
            "description": extract_jira_text(
                fields.get(
                    "description"
                )
            ),
            "status": (
                fields.get(
                    "status",
                    {}
                ).get(
                    "name",
                    ""
                )
            ),
            "components": [
                component.get(
                    "name",
                    ""
                )
                for component in fields.get(
                    "components",
                    []
                )
            ],
            "labels": fields.get(
                "labels",
                []
            ),
            "fix_versions": [
                version.get(
                    "name",
                    ""
                )
                for version in fields.get(
                    "fixVersions",
                    []
                )
            ]
        })

    return {
        "target_release": target_release,
        "issue_count": len(
            issues
        ),
        "issues": issues
    }