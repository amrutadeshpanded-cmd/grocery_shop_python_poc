import streamlit as st
from pathlib import Path

from integration.release_planner.ai_service import (
    analyze_release
)

from integration.release_planner.plan_service import (
    build_regression_plan
)

from integration.release_planner.git_service import (
    get_release_git_context,
    get_files_diff
)
from integration.release_planner.jira_service import (
    get_release_jira_issues
)

from integration.release_planner.testrail_service import (
    load_master_cases,
    create_test_run
)

from integration.release_planner.context_builder import (
    build_release_context
)

REPO_ROOT = Path(__file__).resolve().parents[2]


st.set_page_config(
    page_title="Risk-Based Regression Planner",
    layout="wide"
)

st.title(
    "Risk-Based Regression Planner"
)

st.subheader(
    "Release Inputs"
)

previous_release = st.text_input(
    "Previous Release",
    value="release-2"
)

current_release = st.text_input(
    "Current Release",
    value="release-3"
)


if "release_loaded" not in st.session_state:
    st.session_state[
        "release_loaded"
    ] = False

if not st.session_state[
    "release_loaded"
]:
    if st.button(
        "Lets start .. 1st step is to load the release context"
        ):
        st.session_state[
            "jira_context"
        ] = get_release_jira_issues(
            target_release
        )

        st.session_state[
            "git_context"
        ] = get_release_git_context(
            repo_path=REPO_ROOT,
            base_ref=previous_release,
            target_ref=current_release
        )

        st.session_state[
            "release_loaded"
        ] = True

        st.session_state[
            "current_step"
        ] = "Jira"

        st.rerun()
if "current_step" not in st.session_state:
    st.session_state[
        "current_step"
    ] = "Jira"

if st.session_state[
    "current_step"
] == "Jira":

    st.subheader(
        "Jira Release Scope"
    )

    jira_context = st.session_state.get(
        "jira_context"
    )

    if not jira_context:
        st.info(
            "Load release context first."
        )
    else:
        if "excluded_jira_keys" not in st.session_state:
            st.session_state[
                "excluded_jira_keys"
            ] = set()

        for issue in jira_context[
            "issues"
        ]:
            issue_key = issue[
                "key"
            ]

            include_issue = st.checkbox(
                f"{issue_key} - "
                f"{issue['summary']}",
                value=(
                    issue_key
                    not in st.session_state[
                        "excluded_jira_keys"
                    ]
                ),
                key=f"jira_{issue_key}"
            )

            if include_issue:
                st.session_state[
                    "excluded_jira_keys"
                ].discard(
                    issue_key
                )
            else:
                st.session_state[
                    "excluded_jira_keys"
                ].add(
                    issue_key
                )

            st.write(
                f"Status: {issue['status']}"
            )

            st.write(
                issue["description"]
            )

            st.divider()

        if st.button(
            "Continue to Git Review"
        ):
            st.session_state[
                "current_step"
            ] = "Git"

            st.rerun()


if st.session_state[
    "current_step"
] == "Git":

    git_context = st.session_state.get(
        "git_context"
    )

    if not git_context:
        st.info(
            "Load release context first."
        )
    else:
        if "excluded_git_files" not in st.session_state:
            st.session_state[
                "excluded_git_files"
            ] = set()

        st.write(
            f"Commits: "
            f"{git_context['commit_count']}"
        )

        for file_name in git_context[
            "changed_files"
        ]:
            include_file = st.checkbox(
                file_name,
                value=(
                    file_name
                    not in st.session_state[
                        "excluded_git_files"
                    ]
                ),
                key=f"git_{file_name}"
            )

            if include_file:
                st.session_state[
                    "excluded_git_files"
                ].discard(
                    file_name
                )
            else:
                st.session_state[
                    "excluded_git_files"
                ].add(
                    file_name
                )

        if st.button(
    "Continue to Context"
):
            st.session_state[
                "current_step"
            ] = "Context"

            st.rerun()


if st.session_state[
    "current_step"
] == "Context":
    st.subheader(
        "AI Context Preview"
    )

    jira_context = st.session_state.get(
        "jira_context"
    )

    git_context = st.session_state.get(
        "git_context"
    )

    if not jira_context or not git_context:
        st.info(
            "Load and review Jira and Git context first."
        )
    else:
        excluded_jira_keys = st.session_state.get(
            "excluded_jira_keys",
            set()
        )

        excluded_git_files = st.session_state.get(
            "excluded_git_files",
            set()
        )

        reviewed_jira_context = {
            **jira_context,
            "issues": [
                issue
                for issue in jira_context["issues"]
                if issue["key"]
                not in excluded_jira_keys
            ]
        }

        reviewed_jira_context[
            "issue_count"
        ] = len(
            reviewed_jira_context["issues"]
        )

        reviewed_git_context = {
            **git_context,
            "changed_files": [
                file_name
                for file_name
                in git_context["changed_files"]
                if file_name
                not in excluded_git_files
            ]
        }
        reviewed_git_context[
            "diff"
        ] = get_files_diff(
            repo_path=REPO_ROOT,
            base_ref=git_context["base_ref"],
            target_ref=git_context["target_ref"],
            files=reviewed_git_context[
                "changed_files"
            ]
        )

        master_cases = load_master_cases()

        release_context = build_release_context(
            jira_context=reviewed_jira_context,
            git_context=reviewed_git_context,
            master_cases=master_cases
        )

        st.write(
            f"Jira issues included: "
            f"{reviewed_jira_context['issue_count']}"
        )

        st.write(
            f"Git files included: "
            f"{len(reviewed_git_context['changed_files'])}"
        )

        st.write(
            "Jira context:"
        )

        st.json(
            reviewed_jira_context
        )

        st.write(
            "Git context:"
        )

        st.json(
            reviewed_git_context
        )

        st.write(
            f"Master cases included: "
            f"{len(release_context['testrail_master_cases'])}"
        )

        if st.button(
            "Confirm Context"
        ):
            st.session_state[
                "release_context"
            ] = release_context

            st.session_state[
                "master_cases"
            ] = master_cases

            st.success(
                "Final AI context saved."
            )


        if "release_context" in st.session_state:
            if st.button(
                "Analyze Release"
            ):
                with st.spinner(
                    "Analyzing release..."
                ):
                    ai_result = analyze_release(
                        st.session_state[
                            "release_context"
                        ]
                    )

                    regression_plan = build_regression_plan(
                        ai_result=ai_result,
                        master_cases=st.session_state[
                            "master_cases"
                        ]
                    )

                    st.session_state[
                        "ai_result"
                    ] = ai_result

                    st.session_state[
                        "regression_plan"
                    ] = regression_plan

                    st.session_state[
                        "current_step"
                    ] = "Dynamic Plan"

                st.rerun()
if st.session_state[
    "current_step"
] == "Dynamic Plan":

    st.subheader(
        "Dynamic Regression Plan"
    )

    regression_plan = st.session_state.get(
        "regression_plan"
    )

    if not regression_plan:
        st.info(
            "Confirm the context and run release analysis first."
        )

    else:
        st.write(
            regression_plan[
                "release_summary"
            ]
        )

        st.write(
            f"Selected existing cases: "
            f"{len(regression_plan['selected_cases'])}"
        )

        st.write(
            f"Proposed new cases: "
            f"{len(regression_plan['proposed_new_cases'])}"
        )

        st.divider()


        if "excluded_plan_case_ids" not in st.session_state:
            st.session_state[
                "excluded_plan_case_ids"
            ] = set()

        for case in regression_plan[
            "selected_cases"
        ]:
            case_id = case[
                "case_id"
            ]

            include_case = st.checkbox(
                f"C{case_id} - "
                f"{case['section']} - "
                f"{case['title']}",
                value=(
                    case_id
                    not in st.session_state[
                        "excluded_plan_case_ids"
                    ]
                ),
                key=f"plan_case_{case_id}"
            )

            if include_case:
                st.session_state[
                    "excluded_plan_case_ids"
                ].discard(
                    case_id
                )
            else:
                st.session_state[
                    "excluded_plan_case_ids"
                ].add(
                    case_id
                )

            st.write(
                f"Reason: "
                f"{case['reason']}"
            )

            st.write(
                f"Impact: "
                f"{case['impact_type']}"
            )

            st.divider()

        final_selected_cases = [
            case
            for case in regression_plan[
                "selected_cases"
            ]
            if case["case_id"]
            not in st.session_state[
                "excluded_plan_case_ids"
            ]
        ]

        st.write(
            f"Final selected cases: "
            f"{len(final_selected_cases)}"
        )

        if st.button(
            "Approve Final Plan"
        ):
            approved_plan = {
                "release_summary": regression_plan[
                    "release_summary"
                ],
                "selected_cases": final_selected_cases,
                "proposed_new_cases": regression_plan[
                    "proposed_new_cases"
                ]
            }

            st.session_state[
                "approved_plan"
            ] = approved_plan

            case_ids = [
                case["case_id"]
                for case in final_selected_cases
            ]

            run_name = (
                f"Dynamic Regression - "
                f"{current_release}"
            )

            with st.spinner(
                "Creating TestRail run..."
            ):
                test_run = create_test_run(
                    run_name=run_name,
                    case_ids=case_ids
                )

            st.session_state[
                "testrail_run"
            ] = test_run

            st.success(
                f"TestRail run created successfully. "
                f"Run ID: {test_run['id']}"
            )