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
    analyze_release
)
from integration.release_planner.plan_service import (
    build_regression_plan
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

plan = build_regression_plan(
    ai_result=ai_result,
    master_cases=master_cases
)

print()
print("DYNAMIC REGRESSION PLAN")
print()

print(
    f"Selected existing cases: "
    f"{len(plan['selected_cases'])}"
)

print(
    f"Invalid cases rejected: "
    f"{len(plan['invalid_cases'])}"
)

print(
    f"Proposed new cases: "
    f"{len(plan['proposed_new_cases'])}"
)

print()
print("Selected cases:")

for case in plan["selected_cases"]:
    print()
    print(
        f"C{case['case_id']} - "
        f"{case['section']} - "
        f"{case['title']}"
    )
    print(
        f"Reason: "
        f"{case['reason']}"
    )
    print(
        f"Impact: "
        f"{case['impact_type']}"
    )