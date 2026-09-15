def remove_empty_fields(value):
    if isinstance(value, dict):
        cleaned = {}

        for key, item in value.items():
            cleaned_item = remove_empty_fields(
                item
            )

            if cleaned_item not in (
                None,
                "",
                [],
                {}
            ):
                cleaned[key] = cleaned_item

        return cleaned

    if isinstance(value, list):
        return [
            remove_empty_fields(item)
            for item in value
        ]

    return value


def compact_master_cases(
    master_cases
):
    compact_cases = []

    for case in master_cases:
        compact_case = {
            "case_id": case.get(
                "case_id"
            ),
            "section": case.get(
                "section",
                ""
            ),
            "title": case.get(
                "title",
                ""
            ),
            "preconditions": case.get(
                "preconditions",
                ""
            ),
            "steps": case.get(
                "steps",
                ""
            ),
            "expected_result": case.get(
                "expected_result",
                ""
            )
        }

        compact_cases.append(
            remove_empty_fields(
                compact_case
            )
        )

    return compact_cases


def build_release_context(
    jira_context,
    git_context,
    master_cases
):
    compact_jira = remove_empty_fields(
        jira_context
    )

    compact_git = remove_empty_fields(
        git_context
    )

    compact_cases = compact_master_cases(
        master_cases
    )

    return {
        "jira_release_context": compact_jira,
        "git_release_context": compact_git,
        "testrail_master_cases": compact_cases
    }