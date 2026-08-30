import json
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "integration" / "testrail"))

from testrail_client import TestRailClient


load_dotenv()

SECTIONS_FILE = REPO_ROOT / "output" / "rmp_sections.json"
PROMPT_FILE = (
    REPO_ROOT
    / "integration"
    / "ai_agent"
    / "prompts"
    / "generate_sections_cases.txt"
)

AUDIT_FILE = (
    REPO_ROOT
    / "output"
    / "master_regression_build_log.json"
)

MODEL = "claude-sonnet-4-6"


def collect_repository_context():
    files_to_read = [
        "app.py",
        "controller.py",
        "admin.py",
        "API.py",
        "model.py",
        "API.yaml",
        "README.md",
    ]

    context_parts = []

    for relative_path in files_to_read:
        file_path = REPO_ROOT / relative_path

        if file_path.exists():
            content = file_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )

            context_parts.append(
                f"\n===== FILE: {relative_path} =====\n{content}"
            )

    return "\n".join(context_parts)


def clean_json_response(raw_output):
    raw_output = raw_output.strip()

    if raw_output.startswith("```"):
        raw_output = raw_output.replace("```json", "", 1)
        raw_output = raw_output.replace("```", "")

    return raw_output.strip()


def generate_cases_for_section(
    claude_client,
    section,
    repository_context,
):
    instructions = PROMPT_FILE.read_text(
        encoding="utf-8"
    )

    section_json = json.dumps(
        section,
        indent=2,
    )

    user_prompt = f"""
{instructions}

SECTION TO GENERATE:

{section_json}

REPOSITORY CONTEXT:

{repository_context}
"""

    print()
    print(
        f"Generating cases for: {section['name']}"
    )

    response = claude_client.messages.create(
        model=MODEL,
        max_tokens=5000,
        messages=[
            {
                "role": "user",
                "content": user_prompt,
            }
        ],
    )

    raw_output = "".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    )

    raw_output = clean_json_response(
        raw_output
    )

    return json.loads(raw_output)


def list_to_text(values):
    if not values:
        return None

    return "\n".join(
        f"{index}. {value}"
        for index, value in enumerate(
            values,
            start=1,
        )
    )


def main():
    api_key = os.getenv(
        "ANTHROPIC_API_KEY"
    )

    suite_id = int(
        os.getenv(
            "TESTRAIL_SUITE_ID",
            "8",
        )
    )

    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is missing"
        )

    sections_data = json.loads(
        SECTIONS_FILE.read_text(
            encoding="utf-8"
        )
    )

    claude = Anthropic(
        api_key=api_key
    )

    testrail = TestRailClient()

    repository_context = (
        collect_repository_context()
    )

    audit = {
        "baseline": "baseline-v1",
        "suite_name": sections_data.get(
            "suite_name"
        ),
        "testrail_suite_id": suite_id,
        "sections": [],
    }

    for section in sections_data["sections"]:

        section_name = section["name"]

        existing_section = (
            testrail.find_section_by_name(
                section_name,
                suite_id=suite_id,
            )
        )

        if existing_section:
            section_id = existing_section["id"]

            print()
            print(
                f"Using existing section: "
                f"{section_name} "
                f"(ID={section_id})"
            )

        else:
            created_section = (
                testrail.create_section(
                    name=section_name,
                    suite_id=suite_id,
                )
            )

            section_id = created_section["id"]

            print()
            print(
                f"Created section: "
                f"{section_name} "
                f"(ID={section_id})"
            )

        try:
            generated = (
                generate_cases_for_section(
                    claude,
                    section,
                    repository_context,
                )
            )

        except Exception as exc:
            print(
                f"Failed generating cases "
                f"for {section_name}"
            )
            print(exc)
            continue

        section_log = {
            "section": section_name,
            "section_id": section_id,
            "created_cases": [],
            "existing_cases": [],
        }

        for case in generated.get(
            "cases",
            []
        ):

            title = case["title"]

            existing_case = (
                testrail.find_case_by_title(
                    title,
                    suite_id=suite_id,
                )
            )

            if existing_case:
                case_id = existing_case["id"]

                print(
                    f"  Existing C{case_id}: "
                    f"{title}"
                )

                section_log[
                    "existing_cases"
                ].append(
                    {
                        "case_id": case_id,
                        "title": title,
                    }
                )

                continue

            preconditions = list_to_text(
                case.get("preconditions")
            )

            steps = list_to_text(
                case.get("steps")
            )

            expected = case.get(
                "expected_result"
            )

            created_case = (
                testrail.create_case(
                    section_id=section_id,
                    title=title,
                    custom_preconds=preconditions,
                    custom_steps=steps,
                    custom_expected=expected,
                )
            )

            case_id = created_case["id"]

            print(
                f"  Created C{case_id}: "
                f"{title}"
            )

            section_log[
                "created_cases"
            ].append(
                {
                    "case_id": case_id,
                    "title": title,
                    "priority": case.get(
                        "priority"
                    ),
                    "test_type": case.get(
                        "test_type"
                    ),
                    "repository_evidence":
                        case.get(
                            "repository_evidence",
                            [],
                        ),
                }
            )

        audit["sections"].append(
            section_log
        )

    AUDIT_FILE.write_text(
        json.dumps(
            audit,
            indent=2,
        ),
        encoding="utf-8",
    )

    created_count = sum(
        len(section["created_cases"])
        for section in audit["sections"]
    )

    existing_count = sum(
        len(section["existing_cases"])
        for section in audit["sections"]
    )

    print()
    print("==============================")
    print("MASTER RMP BUILD COMPLETE")
    print("==============================")
    print(
        "New cases created:",
        created_count,
    )
    print(
        "Existing cases reused:",
        existing_count,
    )
    print(
        "Audit log:",
        AUDIT_FILE,
    )


if __name__ == "__main__":
    main()