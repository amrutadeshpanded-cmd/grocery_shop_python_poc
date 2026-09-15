from pathlib import Path

from integration.release_planner.git_service import (
    get_release_git_context
)


REPO_ROOT = Path(__file__).resolve().parents[2]


context = get_release_git_context(
    repo_path=REPO_ROOT,
    base_ref="release-2",
    target_ref="KAN-5"
)

print(
    f"Commits: "
    f"{context['commit_count']}"
)

print(
    f"Changed files: "
    f"{len(context['changed_files'])}"
)

print(
    "Files:"
)

for file_name in context["changed_files"]:
    print(
        f"- {file_name}"
    )