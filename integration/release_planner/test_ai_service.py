from pathlib import Path

from integration.release_planner.git_service import (
    get_release_git_context
)
from integration.release_planner.jira_service import (
    get_release_jira_issues
)
from integration.release_planner.testrail_service import (
    load_master_cases
)
from integration.release_planner.context_builder import (
    build_release_context
)
from integration.release_planner.ai_service import (
    analyze_release,
    validate_selected_cases
)


REPO_ROOT = Path(__file__).resolve().parents[2]


jira_context = get_release_jira_issues(
    "release-3"
)

git_context = get_release_git_context(
    repo_path=REPO_ROOT,
    base_ref="release-2",
    target_ref="KAN-5"
)

master_cases = load_master_cases()

release_context = build_release_context(
    jira_context=jira_context,
    git_context=git_context,
    master_cases=master_cases
)

print("Calling OpenAI...")

ai_result = analyze_release(
    release_context
)

validated_result = validate_selected_cases(
    ai_result=ai_result,
    master_cases=master_cases
)

print()
print(
    f"Selected existing cases: "
    f"{len(validated_result['selected_cases'])}"
)

print(
    f"Invalid case IDs rejected: "
    f"{len(validated_result['invalid_selected_cases'])}"
)

print(
    f"Proposed new cases: "
    f"{len(validated_result['proposed_new_cases'])}"
)

print()
print(
    "Release summary:"
)

print(
    validated_result["release_summary"]
)

print()
print(
    "Selected cases:"
)

for case in validated_result[
    "selected_cases"
]:
    print(
        f"C{case['case_id']} - "
        f"{case.get('title', '')}"
    )

print()
print(
    "Proposed new cases:"
)

for case in validated_result[
    "proposed_new_cases"
]:
    print()
    print(
        f"- {case.get('title', '')}"
    )
    print(
        f"  Section: "
        f"{case.get('section', '')}"
    )
    print(
        f"  Reason: "
        f"{case.get('reason', '')}"
    )