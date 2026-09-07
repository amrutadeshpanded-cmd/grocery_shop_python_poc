import json
import os
import sys
import csv
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

def save_proposed_cases_csv(
    release_name,
    proposed_cases
):
    repo_root = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            ".."
        )
    )

    output_dir = os.path.join(
        repo_root,
        "processed_output",
        release_name
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    file_path = os.path.join(
        output_dir,
        "05_proposed_new_test_cases.csv"
    )

    fieldnames = [
        "Section",
        "Title",
        "Preconditions",
        "Steps",
        "Expected Result",
        "Reason",
        "Closest Existing Case ID",
        "Why Not Reuse Existing",
        "RMP Status"
    ]

    with open(
        file_path,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for case in proposed_cases:

            preconditions = "\n".join(
                case.get(
                    "preconditions",
                    []
                )
            )

            steps = "\n".join(
                f"{index}. {step}"
                for index, step in enumerate(
                    case.get("steps", []),
                    start=1
                )
            )

            writer.writerow({
                "Section": case.get(
                    "section",
                    ""
                ),
                "Title": case.get(
                    "title",
                    ""
                ),
                "Preconditions": preconditions,
                "Steps": steps,
                "Expected Result": case.get(
                    "expected_result",
                    ""
                ),
                "Reason": case.get(
                    "reason",
                    ""
                ),
                "Closest Existing Case ID": (
                    case.get(
                        "closest_existing_case_id",
                        ""
                    )
                    or ""
                ),
                "Why Not Reuse Existing": (
                    case.get(
                        "why_not_reuse_existing",
                        ""
                    )
                ),
                "RMP Status": (
                    "Pending RMP Review"
                )
            })

    print(
        f"Saved proposed cases CSV: "
        f"{file_path}"
    )

    return file_path

def save_processed_output(
    release_name,
    filename,
    data
):
    repo_root = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

    output_dir = os.path.join(
    repo_root,
    "processed_output",
    release_name
)
    output_dir = os.path.join(
        "processed_output",
        release_name
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    file_path = os.path.join(
        output_dir,
        filename
    )

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )
    print(f"Saved processed output: {file_path}")
    
    return file_path

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

        closest_existing_case_id = case.get(
            "closest_existing_case_id"
        )

        why_not_reuse_existing = str(
            case.get(
                "why_not_reuse_existing",
                ""
            )
        ).strip()


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

        if closest_existing_case_id is not None:
            if not why_not_reuse_existing:
                print(
                    f"WARNING: Proposed new test '{title}' "
                    f"has closest existing case "
                    f"C{closest_existing_case_id} but no "
                    f"reuse justification. Ignoring."
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
            "closest_existing_case_id": (
                closest_existing_case_id
            ),
            "why_not_reuse_existing": (
                why_not_reuse_existing
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
    new_test_cases,
    master_case_count,
    excluded_cases
):
    lines = []

    review_items = ai_result.get(
        "needs_review",
        []
    )

    review_by_id = {
        item.get("case_id"): item
        for item in review_items
    }

    review_ids = set(
        review_by_id.keys()
    )

    existing_cases = [
        case
        for case in selected_cases
        if case.get("case_id") not in review_ids
    ]

    review_cases = [
        case
        for case in selected_cases
        if case.get("case_id") in review_ids
    ]

    total_release_cases = len(
        selected_cases
    )

    separator = "=" * 50

    lines.append(
        "AI RISK-BASED REGRESSION PLAN"
    )
    lines.append(
        f"Release: {target_ref}"
    )
    lines.append(
        f"Risk: "
        f"{ai_result.get('risk_level', 'Unknown').upper()}"
    )
    lines.append("")

    # --------------------------------------------------
    # CHANGE
    # --------------------------------------------------

    lines.append(separator)
    lines.append("CHANGE")
    lines.append(separator)

    release_summary = ai_result.get(
        "release_summary",
        "No release summary available."
    )

    lines.append(
        release_summary
    )
    lines.append("")

    impacted_areas = ai_result.get(
        "impacted_areas",
        []
    )

    if impacted_areas:
        area_names = []

        for item in impacted_areas:

            if isinstance(item, dict):
                area = item.get(
                    "area",
                    ""
                )
            else:
                area = str(item)

            if area:
                area_names.append(
                    area
                )

        if area_names:
            lines.append(
                "Impacted area: "
                + " / ".join(
                    area_names
                )
            )
            lines.append("")

    # --------------------------------------------------
    # COVERAGE
    # --------------------------------------------------

    lines.append(separator)
    lines.append("COVERAGE")
    lines.append(separator)

    lines.append(
        f"Reference:              "
        f"{master_case_count}"
    )

    lines.append(
        f"Selected for execution: "
        f"{len(selected_cases)} existing"
    )

    lines.append(
        f"Proposed new:            "
        f"{len(new_test_cases)} "
        f"(pending RMP review)"
    )

    lines.append(
        f"Excluded:                "
        f"{len(excluded_cases)}"
    )

    lines.append(
        f"TOTAL IN THIS RUN:       "
        f"{total_release_cases}"
    )

    # --------------------------------------------------
    # EXISTING
    # --------------------------------------------------

    lines.append("")
    lines.append(separator)
    lines.append("SELECTED COVERAGE")
    lines.append(separator)

    if existing_cases:

        section_counts = {}

        for case in existing_cases:

            section = case.get(
                "section",
                "Other"
            )

            if not section:
                section = "Other"

            section_counts[
                section
            ] = (
                section_counts.get(
                    section,
                    0
                )
                + 1
            )

        for section, count in sorted(
            section_counts.items()
        ):
            lines.append(
                f"{section}: "
                f"{count} test"
                f"{'s' if count != 1 else ''}"
            )

    else:
        lines.append("None")

    # --------------------------------------------------
    # TBD / REVIEW
    # --------------------------------------------------

    lines.append("")
    lines.append(separator)
    lines.append(
        "TBD - REVIEW / UPDATE"
    )
    lines.append(separator)

    if review_cases:

        for case in sorted(
            review_cases,
            key=lambda item: item.get(
                "case_id",
                0
            )
        ):

            case_id = case.get(
                "case_id"
            )

            title = case.get(
                "title",
                ""
            )

            review = review_by_id.get(
                case_id,
                {}
            )

            reason = review.get(
                "reason",
                ""
            )

            if reason.startswith(
                "TBD - update test case:"
            ):
                reason = reason.replace(
                    "TBD - update test case:",
                    ""
                ).strip()

            lines.append(
                f"C{case_id}  {title}"
            )

            if reason:
                lines.append(
                    f"      Update: "
                    f"{reason}"
                )

    else:
        lines.append("None")

    # --------------------------------------------------
    # PROPOSED NEW COVERAGE
    # --------------------------------------------------

    lines.append("")
    lines.append(separator)
    lines.append(
        "PROPOSED NEW TESTS - "
        "PENDING RMP REVIEW"
    )
    lines.append(separator)

    if new_test_cases:

        for case in new_test_cases:

            title = case.get(
                "title",
                ""
            )

            section = case.get(
                "section",
                ""
            )

            lines.append(
                f"{title}"
            )

            if section:
                lines.append(
                    f"      Proposed section: "
                    f"{section}"
                )

        lines.append("")
        lines.append(
            "These cases are not included "
            "in this TestRail run."
        )

        lines.append(
            "See proposed_new_test_cases.csv "
            "for review/import."
        )

    else:
        lines.append("None")

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

    testrail_run_input = {
    "name": run_name,
    "description": description,
    "case_ids": case_ids
}

    save_processed_output(
        target_ref,
        "05_testrail_run_input.json",
        testrail_run_input
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
    new_test_cases
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
            "diff_stat": git_context["diff_stat"],
            "diff": git_context["diff"]
        },

        "testrail_run": {
            "run_id": test_run.get("id"),
            "name": test_run.get("name"),
            "url": test_run.get("url")
        },

        "master_suite": {
            "current_count": len(master_cases),
            "new_cases_created": 0,
            "rmp_updated_automatically": False
        },

        "selection_summary": {
            "existing_selected": len(selected_cases),
            "proposed_new_pending_rmp_review": len(
                new_test_cases
            ),
            "total_release_cases": len(
                selected_cases
            ),
            "excluded": len(
                excluded_cases
            )
        },

        "impacted_areas": ai_result.get(
            "impacted_areas",
            []
        ),

        "proposed_new_test_cases": {
            "status": "Pending RMP Review",
            "included_in_testrail_run": False,
            "count": len(new_test_cases),
            "cases": new_test_cases,
            "csv_file": (
                "05_proposed_new_test_cases.csv"
            )
        },

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

    save_processed_output(
        target_ref,
        "01_git_release_context.json",
        git_context
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

    save_processed_output(
        target_ref,
        "02_claude_input.json",
        payload
    )

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

    save_processed_output(
        target_ref,
        "03_claude_output.json",
        ai_result
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

    save_proposed_cases_csv(
    target_ref,
    ai_result.get(
        "new_test_cases",
        []
    )
)
    
    save_processed_output(
        target_ref,
        "04_python_validated_result.json",
        ai_result
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
    # Proposed new cases are NOT created in TestRail.
    # They remain in the CSV pending RMP review.

    release_cases_by_id = {
        case["case_id"]: case
        for case in selected_cases
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

    # 7. Build TestRail run description / changelog
    run_description = build_run_description(
        base_ref,
        target_ref,
        git_context,
        ai_result,
        selected_cases,
        new_test_cases,
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
    new_test_cases
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
    f"New cases pending RMP review: "
    f"{len(new_test_cases)}"
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