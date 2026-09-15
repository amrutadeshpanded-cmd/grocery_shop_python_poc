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
    build_ai_prompt
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

print(
    f"Master cases in context: "
    f"{len(release_context['testrail_master_cases'])}"
)

print(
    f"Last case: "
    f"{release_context['testrail_master_cases'][-1]['case_id']} - "
    f"{release_context['testrail_master_cases'][-1]['title']}"
)

prompt = build_ai_prompt(
    release_context
)

print(
    f"Prompt characters: "
    f"{len(prompt)}"
)

print()

print(
    prompt[:3000]
)