import json
import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def build_ai_prompt(release_context):
    context_json = json.dumps(
        release_context,
        indent=2,
        ensure_ascii=False
    )

    prompt = f"""
You are an AI risk-based regression planning agent.

Your task is to analyze a software release using three sources:

1. Jira release context
   - Describes the intended release changes.

2. Git release context
   - Shows what actually changed in the code.

3. TestRail Master cases
   - Contains the complete existing regression test inventory.

Use Jira and Git together to understand the release impact.

Then review the complete TestRail Master and select the existing
test cases that should be included in the regression plan.

Do not invent TestRail case IDs.
Every selected case_id must exist in the provided TestRail Master.

If important coverage is missing from the Master, suggest it separately
under proposed_new_cases.

Proposed new cases must not be treated as existing TestRail cases.

Return JSON only in this structure:

{{
    "release_summary": "Short explanation of release impact and risk",
    "selected_cases": [
        {{
            "case_id": 123,
            "section": "Section name",
            "title": "Existing TestRail case title",
            "reason": "Why this case is relevant",
            "impact_type": "direct"
        }}
    ],
    "proposed_new_cases": [
        {{
            "section": "Section name",
            "title": "Proposed test title",
            "reason": "Why additional coverage is needed"
        }}
    ]
}}

Allowed impact_type values:
- direct
- indirect
- regression

RELEASE CONTEXT:

{context_json}
"""

    return prompt.strip()

def analyze_release(
    release_context
):
    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing."
        )

    client = OpenAI(
        api_key=api_key
    )

    prompt = build_ai_prompt(
        release_context
    )

    response = client.responses.create(
        model="gpt-5.6",
        input=prompt
    )

    result_text = response.output_text

    try:
        return json.loads(
            result_text
        )
    except json.JSONDecodeError:
        raise RuntimeError(
            "OpenAI did not return valid JSON.\n"
            f"{result_text}"
        )


def validate_selected_cases(
    ai_result,
    master_cases
):
    valid_case_ids = {
        case["case_id"]
        for case in master_cases
    }

    valid_selected_cases = []
    invalid_selected_cases = []

    for selected_case in ai_result.get(
        "selected_cases",
        []
    ):
        case_id = selected_case.get(
            "case_id"
        )

        if case_id in valid_case_ids:
            valid_selected_cases.append(
                selected_case
            )
        else:
            invalid_selected_cases.append(
                selected_case
            )

    return {
        "release_summary": ai_result.get(
            "release_summary",
            ""
        ),
        "selected_cases": valid_selected_cases,
        "invalid_selected_cases": invalid_selected_cases,
        "proposed_new_cases": ai_result.get(
            "proposed_new_cases",
            []
        )
    }