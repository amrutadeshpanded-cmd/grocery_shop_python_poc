import json
import os
import sys
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from integration.git.git_client import GitClient
from integration.testrail.testrail_client import TestRailClient


load_dotenv(REPO_ROOT / ".env")

PROMPT_FILE = (
    REPO_ROOT
    / "integration"
    / "ai_agent"
    / "prompts"
    / "analyze_release.txt"
)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def extract_json(text):
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return json.loads(text)


def call_claude_with_retry(client, prompt, payload, retries=3):
    last_error = None

    for attempt in range(1, retries + 1):
        print(f"Claude analysis attempt {attempt}/{retries}")

        if attempt == 1:
            user_message = f"""
Analyze this software release.

INPUT DATA:

{json.dumps(payload, indent=2)}

Return ONLY valid JSON.
"""
        else:
            user_message = f"""
Your previous response was invalid JSON.

Error:
{last_error}

Generate the release analysis again.

Return ONLY valid JSON.
Do not use markdown.
Do not include explanation.
"""

        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        text = "".join(
            block.text
            for block in response.content
            if hasattr(block, "text")
        )

        try:
            return extract_json(text)

        except json.JSONDecodeError as exc:
            last_error = str(exc)
            print(f"Invalid JSON returned: {exc}")

    raise RuntimeError(
        "Claude failed to return valid JSON after retries."
    )


def normalize_collection(data, key):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        value = data.get(key, [])

        if isinstance(value, list):
            return value

    return []


def load_master_cases(testrail):
    sections_raw = testrail.get_sections()
    cases_raw = testrail.get_cases()

    sections = normalize_collection(
        sections_raw,
        "sections"
    )

    cases = normalize_collection(
        cases_raw,
        "cases"
    )

    section_map = {
        section["id"]: section.get(
            "name",
            "Unknown Section"
        )
        for section in sections
    }

    master_cases = []

    for case in cases:
        section_id = case.get("section_id")

        master_cases.append({
            "case_id": case.get("id"),
            "title": case.get("title"),
            "section_id": section_id,
            "section": section_map.get(
                section_id,
                "Unknown Section"
            )
        })

    return master_cases


def validate_selected_cases(ai_result, master_cases):
    master_by_id = {
        case["case_id"]: case
        for case in master_cases
    }

    valid_selected = []

    seen_ids = set()

    for selected in ai_result.get(
        "selected_cases",
        []
    ):
        case_id = selected.get("case_id")

        if case_id not in master_by_id:
            print(
                f"WARNING: Unknown TestRail case "
                f"C{case_id}. Ignoring."
            )
            continue

        if case_id in seen_ids:
            continue

        seen_ids.add(case_id)

        master_case = master_by_id[case_id]

        valid_selected.append({
            "case_id": case_id,
            "title": master_case["title"],
            "section": master_case["section"],
            "reason": selected.get(
                "reason",
                "Selected by release impact analysis"
            ),
            "impact_type": selected.get(
                "impact_type",
                "Regression Risk"
            )
        })

    ai_result["selected_cases"] = valid_selected

    return ai_result

def validate_new_test_cases(
    ai_result,
    master_cases
):
    proposed_cases = ai_result.get(
        "new_test_cases",
        []
    )

    selected_cases = ai_result.get(
        "selected_cases",
        []
    )

    needs_review = ai_result.get(
        "needs_review",
        []
    )

    existing_titles = {
        case.get("title", "").strip().lower()
        for case in master_cases
    }

    selected_titles = {
        case.get("title", "").strip().lower()
        for case in selected_cases
    }

    review_titles = {
        case.get("title", "").strip().lower()
        for case in needs_review
    }

    valid_cases = []
    seen_titles = set()

    for case in proposed_cases:
        title = str(
            case.get("title", "")
        ).strip()

        section = str(
            case.get("section", "")
        ).strip()

        if not title:
            print(
                "WARNING: New test case without title. "
                "Ignoring."
            )
            continue

        if not section:
            print(
                f"WARNING: New test case '{title}' "
                f"has no section. Ignoring."
            )
            continue

        normalized_title = title.lower()

        if normalized_title in seen_titles:
            print(
                f"WARNING: Duplicate proposed test "
                f"'{title}'. Ignoring."
            )
            continue

        if normalized_title in existing_titles:
            print(
                f"WARNING: Proposed new test already "
                f"exists in Master: '{title}'. Ignoring."
            )
            continue

        if normalized_title in selected_titles:
            print(
                f"WARNING: Proposed new test overlaps "
                f"an existing selected case: "
                f"'{title}'. Ignoring."
            )
            continue

        if normalized_title in review_titles:
            print(
                f"WARNING: Proposed new test overlaps "
                f"a TBD/review case: "
                f"'{title}'. Ignoring."
            )
            continue

        seen_titles.add(normalized_title)

        preconditions = case.get(
            "preconditions",
            []
        )

        steps = case.get(
            "steps",
            []
        )

        if not isinstance(preconditions, list):
            preconditions = [str(preconditions)]

        if not isinstance(steps, list):
            steps = [str(steps)]

        valid_cases.append({
            "section": section,
            "title": title,
            "reason": case.get(
                "reason",
                "New regression coverage"
            ),
            "preconditions": preconditions,
            "steps": steps,
            "expected_result": case.get(
                "expected_result",
                ""
            ),
            "priority": case.get(
                "priority",
                "Medium"
            ),
            "test_type": case.get(
                "test_type",
                "Functional"
            )
        })

    ai_result["new_test_cases"] = valid_cases

    return ai_result


def create_new_master_cases(
    testrail,
    new_test_cases,
    master_cases
):
    if not new_test_cases:
        return [], []

    sections_raw = testrail.get_sections()

    sections = normalize_collection(
        sections_raw,
        "sections"
    )

    section_by_name = {
        section.get("name", "").strip().lower(): section
        for section in sections
    }

    # Existing Master cases indexed by:
    # (section name, case title)
    existing_by_key = {
        (
            case.get("section", "").strip().lower(),
            case.get("title", "").strip().lower()
        ): case
        for case in master_cases
    }

    created_cases = []
    reused_cases = []

    for case in new_test_cases:

        section_name = case["section"].strip()
        title = case["title"].strip()

        key = (
            section_name.lower(),
            title.lower()
        )

        # -----------------------------
        # DUPLICATE PROTECTION
        # -----------------------------
        existing = existing_by_key.get(key)

        if existing:
            print(
                f"Existing Master case reused: "
                f"C{existing['case_id']} - "
                f"{existing['title']}"
            )

            reused_cases.append({
                "case_id": existing["case_id"],
                "title": existing["title"],
                "section": existing["section"],
                "reason": case.get(
                    "reason",
                    "Existing coverage reused"
                ),
                "impact_type": "Existing Coverage",
                "is_new": False
            })

            continue

        # -----------------------------
        # FIND OR CREATE SECTION
        # -----------------------------
        section = section_by_name.get(
            section_name.lower()
        )

        if section:
            section_id = section["id"]

        else:
            print(
                f"Creating new TestRail section: "
                f"{section_name}"
            )

            created_section = (
                testrail.create_section(
                    name=section_name,
                    suite_id=int(
                        os.environ[
                            "TESTRAIL_SUITE_ID"
                        ]
                    )
                )
            )

            section_id = created_section["id"]

            section_by_name[
                section_name.lower()
            ] = created_section

        # -----------------------------
        # FORMAT TESTRAIL FIELDS
        # -----------------------------
        preconditions_text = "\n".join(
            case.get(
                "preconditions",
                []
            )
        )

        steps_text = "\n".join(
            f"{index}. {step}"
            for index, step in enumerate(
                case.get("steps", []),
                start=1
            )
        )

        expected_result = case.get(
            "expected_result",
            ""
        )

        print(
            f"Creating new Master case: "
            f"{title}"
        )

        # -----------------------------
        # CREATE CASE
        # -----------------------------
        created_case = testrail.create_case(
            section_id=section_id,
            title=title,
            custom_preconds=preconditions_text,
            custom_steps=steps_text,
            custom_expected=expected_result
        )

        new_case = {
            "case_id": created_case["id"],
            "title": created_case.get(
                "title",
                title
            ),
            "section": section_name,
            "reason": case.get(
                "reason",
                "New regression coverage"
            ),
            "impact_type": "New Coverage",
            "is_new": True
        }

        created_cases.append(new_case)

        # Prevent another AI proposal in this same run
        # from creating the same case again.
        existing_by_key[key] = new_case

    return created_cases, reused_cases

def calculate_excluded_cases(
    master_cases,
    selected_cases
):
    selected_ids = {
        case["case_id"]
        for case in selected_cases
    }

    return [
        case
        for case in master_cases
        if case["case_id"] not in selected_ids
    ]   

def build_run_description(
    base_ref,
    target_ref,
    git_context,
    ai_result,
    selected_cases,
    created_new_cases,
    master_case_count,
    excluded_cases
):
    release_total = (
        len(selected_cases)
        + len(created_new_cases)
    )

    review_ids = {
        item.get("case_id")
        for item in ai_result.get(
            "needs_review",
            []
        )
    }

    existing_cases = [
        case
        for case in selected_cases
        if case.get("case_id")
        not in review_ids
    ]

    review_cases = [
        case
        for case in selected_cases
        if case.get("case_id")
        in review_ids
    ]

    lines = []

    divider = "=" * 50

    lines.append(
        "AI RISK-BASED REGRESSION PLAN"
    )
    lines.append("")
    lines.append(
        f"Release: {target_ref}"
    )
    lines.append(
        f"Risk: "
        f"{ai_result.get('risk_level', 'Unknown')}"
    )

    # CHANGE SUMMARY
    lines.append("")
    lines.append(divider)
    lines.append("CHANGE SUMMARY")
    lines.append(divider)
    lines.append("")

    lines.append(
        ai_result.get(
            "release_summary",
            "No summary available."
        )
    )

    # TEST FOCUS
    lines.append("")
    lines.append(divider)
    lines.append("TEST FOCUS")
    lines.append(divider)
    lines.append("")

    impacted_areas = ai_result.get(
        "impacted_areas",
        []
    )

    if impacted_areas:
        for item in impacted_areas:
            lines.append(
                f"- {item.get('area', 'Unknown')}"
            )
    else:
        lines.append(
            "- No specific impacted areas identified"
        )

    # COVERAGE SUMMARY
    lines.append("")
    lines.append(divider)
    lines.append("COVERAGE SUMMARY")
    lines.append(divider)
    lines.append("")

    lines.append(
        f"Reference cases:       "
        f"{master_case_count}"
    )
    lines.append(
        f"Existing selected:     "
        f"{len(selected_cases)}"
    )
    lines.append(
        f"New cases added:       "
        f"{len(created_new_cases)}"
    )
    lines.append(
        f"Release run total:     "
        f"{release_total}"
    )
    lines.append(
        f"Excluded:              "
        f"{len(excluded_cases)}"
    )

    # SELECTED TESTS
    lines.append("")
    lines.append(divider)
    lines.append("SELECTED TESTS")
    lines.append(divider)

    # EXISTING
    lines.append("")
    lines.append("EXISTING")

    if existing_cases:
        for case in sorted(
            existing_cases,
            key=lambda x: x.get(
                "case_id",
                0
            )
        ):
            lines.append(
                f"- C{case.get('case_id')} - "
                f"{case.get('title', '')}"
            )
    else:
        lines.append(
            "- None"
        )

    # TBD
    lines.append("")
    lines.append(
        "TBD - REVIEW / UPDATE"
    )

    if review_cases:
        for case in sorted(
            review_cases,
            key=lambda x: x.get(
                "case_id",
                0
            )
        ):
            lines.append(
                f"- C{case.get('case_id')} - "
                f"{case.get('title', '')}"
            )
    else:
        lines.append(
            "- None"
        )

    # NEW
    lines.append("")
    lines.append("NEW")

    if created_new_cases:
        for case in sorted(
            created_new_cases,
            key=lambda x: x.get(
                "case_id",
                0
            )
        ):
            lines.append(
                f"- C{case.get('case_id')} - "
                f"{case.get('title', '')}"
            )
    else:
        lines.append(
            "- None"
        )

    # NEW COVERAGE
    coverage_gaps = ai_result.get(
        "coverage_gaps",
        []
    )

    if coverage_gaps:
        lines.append("")
        lines.append(divider)
        lines.append("NEW COVERAGE")
        lines.append(divider)
        lines.append("")

        for gap in coverage_gaps:
            lines.append(
                f"- {gap.get('area', 'Unknown')}"
            )

    return "\n".join(lines)

def create_dynamic_run(
    testrail,
    target_ref,
    selected_cases,
    description
):
    case_ids = [
        case["case_id"]
        for case in selected_cases
    ]

    if not case_ids:
        raise RuntimeError(
            "No TestRail cases were selected. "
            "Dynamic test run was not created."
        )

    run_name = (
        f"Dynamic Regression - {target_ref}"
    )

    return testrail.create_run(
        name=run_name,
        case_ids=case_ids,
        description=description
    )

def group_cases_by_section(cases):
    grouped = {}

    for case in cases:
        section = case.get(
            "section",
            "Unknown Section"
        )

        grouped.setdefault(
            section,
            []
        ).append(case)

    return [
        {
            "section": section,
            "selected_count": len(section_cases),
            "cases": section_cases
        }
        for section, section_cases in grouped.items()
    ]

def build_change_log(
    base_ref,
    target_ref,
    git_context,
    master_cases,
    ai_result,
    excluded_cases,
    test_run,
    created_new_cases
):
    
    selected_cases = ai_result.get(
        "selected_cases",
        []
    )

    return {
        "release": target_ref,
        "base_ref": base_ref,
        "target_ref": target_ref,
        "generated_at": datetime.now().isoformat(),

        "release_summary": ai_result.get(
            "release_summary"
        ),

        "risk_level": ai_result.get(
            "risk_level"
        ),

        "git_change": {
            "commit_count": git_context["commit_count"],
            "commits": git_context["commits"],
            "changed_files": git_context["changed_files"],
            "diff_stat": git_context["diff_stat"]
        },

        "testrail_run": {
            "run_id": test_run.get("id"),
            "name": test_run.get("name"),
            "url": test_run.get("url")
        },

        "master_suite": {
            "before_count": len(master_cases),
            "new_cases_created": len(created_new_cases),
            "after_count": (
                len(master_cases)
                + len(created_new_cases)
            )
        },

        "selection_summary": {
            "existing_selected": len(selected_cases),
            "new_selected": len(created_new_cases),
            "total_release_cases": (
                len(selected_cases)
                + len(created_new_cases)
            ),
            "excluded": len(excluded_cases)
        },

        "impacted_areas": ai_result.get(
            "impacted_areas",
            []
        ),

        "new_regression_cases": created_new_cases,

        "selected_sections": group_cases_by_section(
            selected_cases
        ),

        "excluded_sections": ai_result.get(
            "excluded_sections",
            []
        ),

        "needs_review": ai_result.get(
            "needs_review",
            []
        )
    }

def extract_testrail_run_id(run_url):
    if not run_url:
        return None

    marker = "/runs/view/"

    if marker not in run_url:
        raise ValueError(
            "Invalid TestRail run URL. "
            "Expected URL containing '/runs/view/<id>'."
        )

    run_id_text = run_url.split(marker)[-1]

    run_id_text = run_id_text.split("&")[0]
    run_id_text = run_id_text.split("#")[0]

    return int(run_id_text)

def load_reference_plan(
    testrail,
    reference_run_id
):
    run = testrail.get_run(
        reference_run_id
    )

    tests_raw = testrail.get_tests(
        reference_run_id
    )
    tests = normalize_collection(
        tests_raw,
        "tests"
    )

    return {
        "run_id": reference_run_id,
        "name": run.get("name"),
        "description": run.get(
            "description",
            ""
        ),
        "tests": [
            {
                "case_id": test.get(
                    "case_id"
                ),
                "title": test.get(
                    "title"
                ),
                "status_id": test.get(
                    "status_id"
                )
            }
            for test in tests
        ]
    }

def main():
    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "python integration/ai_agent/release_agent.py "
            "<base_ref> <target_ref> "
            "[previous_release_run_url]"
        )
        sys.exit(1)

    base_ref = sys.argv[1]
    target_ref = sys.argv[2]

    reference_run_url = sys.argv[3]

    reference_run_id = extract_testrail_run_id(
        reference_run_url
    )

    print(
        f"Reference TestRail run ID: "
        f"{reference_run_id}"
    )
        
    print("\n==============================")
    print("DYNAMIC REGRESSION PLANNER")
    print("==============================")
    print(f"Base:   {base_ref}")
    print(f"Target: {target_ref}")

    # 1. Git comparison
    git_client = GitClient(
        repo_path=str(REPO_ROOT)
    )

    print("\nReading Git diff...")

    git_context = (
        git_client.get_release_context(
            base_ref,
            target_ref
        )
    )

    print(
        f"Commits: "
        f"{git_context['commit_count']}"
    )

    print(
        f"Changed files: "
        f"{len(git_context['changed_files'])}"
    )

    if not git_context["changed_files"]:
        print(
            "\nNo release changes found. "
            "No dynamic run created."
        )
        return

    # 2. Read master suite
    print(
        "\nReading TestRail Master suite..."
    )

    testrail = TestRailClient()

    master_cases = load_master_cases(
        testrail
    )

    print(
        f"Master cases loaded: "
        f"{len(master_cases)}"
    )

    if not master_cases:
        raise RuntimeError(
            "No TestRail master cases found."
        )

    reference_plan = (
    load_reference_plan(
        testrail,
        reference_run_id
    )
)

    if reference_plan:
        print(
            f"Reference plan loaded: "
            f"{reference_plan['name']}"
        )

        print(
            f"Reference cases: "
            f"{len(reference_plan['tests'])}"
        )

    reference_plan = (
    load_reference_plan(
        testrail,
        reference_run_id
    )
)

    print(
        f"Reference plan loaded: "
        f"{reference_plan['name']}"
    )

    print(
        f"Reference cases: "
        f"{len(reference_plan['tests'])}"
    )

    reference_cases = reference_plan["tests"]

    master_by_id = {
        case["case_id"]: case
        for case in master_cases
    }

    for case in reference_cases:
        master_case = master_by_id.get(
            case["case_id"]
        )

        if master_case:
            case["section"] = master_case.get(
                "section",
                ""
            )
        else:
            case["section"] = ""

    if not reference_cases:
        raise RuntimeError(
            "The supplied TestRail reference run "
            "contains no test cases."
        )
    # 3. Prepare compact AI input
    
    ai_reference_cases = [
        {
            "case_id": case["case_id"],
            "title": case["title"],
            "section": case.get("section", "")
        }
        for case in reference_cases
    ]

    payload = {
        "release": {
            "base_ref": base_ref,
            "target_ref": target_ref
        },
        "git_release_context": git_context,
        "testrail_reference_cases": ai_reference_cases
    }


    # 4. Claude impact analysis
    prompt = PROMPT_FILE.read_text(
        encoding="utf-8"
    )

    claude = Anthropic(
        api_key=os.environ[
            "ANTHROPIC_API_KEY"
        ]
    )

    print(
        "\nAnalyzing release impact "
        "with Claude..."
    )

    ai_result = call_claude_with_retry(
        claude,
        prompt,
        payload
    )

    # 5. Validate selected C IDs
    ai_result = validate_selected_cases(
        ai_result,
        reference_cases
    )

    ai_result = validate_new_test_cases(
    ai_result,
    master_cases
    )

    selected_cases = ai_result.get(
        "selected_cases",
        []
    )
    
    print(
        f"\nCases selected: "
        f"{len(selected_cases)}"
    )

    new_test_cases = ai_result.get(
    "new_test_cases",
    []
    )

    print(
    f"New regression cases proposed: "
    f"{len(new_test_cases)}"
    )

    created_new_cases, reused_existing_cases = (
    create_new_master_cases(
        testrail,
        new_test_cases,
        master_cases
    )
)

    print(
        f"New master cases created: "
        f"{len(created_new_cases)}"
    )

    release_cases_by_id = {
    case["case_id"]: case
    for case in (
        selected_cases
        + reused_existing_cases
        + created_new_cases
    )
}

    release_cases = list(
        release_cases_by_id.values()
    )

    # 6. Calculate exclusions
    excluded_cases = (
        calculate_excluded_cases(
            reference_cases,
            selected_cases
        )
    )

    print(
        f"Cases excluded: "
        f"{len(excluded_cases)}"
    )

    # 7. Create TestRail run
    print(
        "\nCreating dynamic TestRail run..."
    )
    # 7. Build TestRail run description / changelog
    run_description = build_run_description(
        base_ref,
        target_ref,
        git_context,
        ai_result,
        selected_cases,
        created_new_cases,
        len(reference_cases),
        excluded_cases
    )

    # 8. Create TestRail dynamic run
    print(
        "\nCreating dynamic TestRail run..."
    )

    test_run = create_dynamic_run(
        testrail=testrail,
        target_ref=target_ref,
        selected_cases=release_cases,
        description=run_description
    )

    print(
        f"Created TestRail run "
        f"ID={test_run.get('id')}"
    )


    # 8. Build changelog
    change_log = build_change_log(
    base_ref,
    target_ref,
    git_context,
    master_cases,
    ai_result,
    excluded_cases,
    test_run,
    created_new_cases
)

    

    # 9. Save output
    safe_target = (
        target_ref
        .replace("/", "_")
        .replace("\\", "_")
    )

    output_dir = (
        REPO_ROOT
        / "output"
        / safe_target
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        output_dir
        / "regression_change_log.json"
    )

    output_file.write_text(
        json.dumps(
            change_log,
            indent=2
        ),
        encoding="utf-8"
    )

    print("\n==============================")
    print("DYNAMIC RUN COMPLETE")
    print("==============================")

    print(
        f"Risk: "
        f"{change_log['risk_level']}"
    )

    print(
    f"Reference cases: "
    f"{len(reference_cases)}"
)

    print(
        f"Existing selected: "
        f"{len(selected_cases)}"
    )

    print(
        f"New cases added to RMP: "
        f"{len(created_new_cases)}"
    )

    print(
        f"Total release cases: "
        f"{len(release_cases)}"
    )

    print(
        f"Excluded: "
        f"{len(excluded_cases)}"
    )

    print(
        f"TestRail run: "
        f"{test_run.get('id')}"
    )

    print(
        f"Change log:\n"
        f"{output_file}"
    )


if __name__ == "__main__":
    main()