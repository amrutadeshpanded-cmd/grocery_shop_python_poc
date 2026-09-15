def build_regression_plan(
    ai_result,
    master_cases
):
    master_by_id = {
        case["case_id"]: case
        for case in master_cases
    }

    selected_cases = []
    invalid_cases = []

    for ai_case in ai_result.get(
        "selected_cases",
        []
    ):
        case_id = ai_case.get(
            "case_id"
        )

        master_case = master_by_id.get(
            case_id
        )

        if not master_case:
            invalid_cases.append(
                ai_case
            )
            continue

        selected_cases.append({
            "case_id": case_id,
            "section": master_case.get(
                "section",
                ""
            ),
            "title": master_case.get(
                "title",
                ""
            ),
            "reason": ai_case.get(
                "reason",
                ""
            ),
            "impact_type": ai_case.get(
                "impact_type",
                ""
            )
        })

    return {
        "release_summary": ai_result.get(
            "release_summary",
            ""
        ),
        "selected_cases": selected_cases,
        "invalid_cases": invalid_cases,
        "proposed_new_cases": ai_result.get(
            "proposed_new_cases",
            []
        )
    }