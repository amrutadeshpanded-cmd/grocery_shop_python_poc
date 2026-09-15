from integration.release_planner.jira_service import (
    get_release_jira_issues
)


context = get_release_jira_issues(
    "release-3"
)

print(
    f"Target Release: "
    f"{context['target_release']}"
)

print(
    f"Issues found: "
    f"{context['issue_count']}"
)

for issue in context["issues"]:
    print()
    print(
        f"{issue['key']} - "
        f"{issue['summary']}"
    )
    print(
        f"Status: "
        f"{issue['status']}"
    )
    print(
        f"Description: "
        f"{issue['description']}"
    )