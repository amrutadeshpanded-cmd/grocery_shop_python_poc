import streamlit as st
import json
import csv
import io


from integration.release_planner.ai_service import (
    analyze_release
)

from integration.release_planner.plan_service import (
    build_regression_plan
)

from integration.release_planner.git_service import (
    get_github_release_context,
    get_github_files_diff
)

from integration.release_planner.jira_service import (
    get_release_jira_issues
)

from integration.release_planner.testrail_service import (
    load_master_cases,
    create_test_run,
    create_test_case
)

from integration.release_planner.context_builder import (
    build_release_context
)

st.set_page_config(
    page_title="Change Based Regression Planner",
    layout="wide"
)

st.title(
    "Change Based Regression Planner"
)

st.subheader(
    "Release Inputs"
)

repository_url = st.text_input(
    "Repository URL",
    placeholder="https://github.com/company/repository.git",
    key="repository_url_input"
)

previous_release = st.text_input(
    "Previous Release",
    placeholder="Enter previous release name",
    key="previous_release_input"
)

current_release = st.text_input(
    "Current Release",
    placeholder="Enter current release name",
    key="current_release_input"
)

if "release_loaded" not in st.session_state:
    st.session_state[
        "release_loaded"
    ] = False

if not st.session_state["release_loaded"]:
    if st.button(
        "Lets start .. 1st step is to load the release context"
    ):
        repository_url = repository_url.strip()
        previous_release = previous_release.strip()
        current_release = current_release.strip()

        if (
            not repository_url
            or not previous_release
            or not current_release
        ):
            st.error(
                "Repository URL, Previous Release "
                "and Current Release are required."
            )
        else:
            st.session_state["repository_url"] = repository_url
            st.session_state["previous_release"] = previous_release
            st.session_state["current_release"] = current_release

            with st.spinner("Loading release context..."):
                git_context = get_github_release_context(
                    repository_url=repository_url,
                    base_ref=previous_release,
                    target_ref=current_release
                )

                jira_context = get_release_jira_issues(
                    current_release
                )

            st.session_state["git_context"] = git_context
            st.session_state["jira_context"] = jira_context
            st.session_state["release_loaded"] = True
            st.session_state["current_step"] = "Jira"

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
        ] = get_github_files_diff(
            repository_url=st.session_state[
                "repository_url"
            ],
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

        # ---------------------------------
        # Final AI Input Preview
        # ---------------------------------

        context_text = json.dumps(
            release_context,
            default=str
        )

        # Lightweight estimate for UI visibility.
        # This does not modify the actual AI input.
        estimated_tokens = max(
            1,
            len(context_text) // 4
        )

        title_col, token_col = st.columns(
            [4, 1]
        )

        with title_col:
            st.subheader(
                "Final AI Input Preview"
            )

        with token_col:
            st.metric(
                "Estimated tokens",
                f"~{estimated_tokens:,}"
            )

        st.caption(
            "Review the final release context that will be sent to AI."
        )

        # ---------------------------------
        # Jira scope
        # ---------------------------------

        st.markdown("### Jira Scope")

        st.write(
            f"**{reviewed_jira_context['issue_count']} "
            f"of {len(jira_context['issues'])} issues included**"
        )

        for issue in reviewed_jira_context[
            "issues"
        ]:
            st.write(
                f"**{issue['key']}** — "
                f"{issue['summary']}"
            )

        # ---------------------------------
        # Git scope
        # ---------------------------------

        st.markdown("### Git Scope")

        st.write(
            f"**{len(reviewed_git_context['changed_files'])} "
            f"of {len(git_context['changed_files'])} files included**"
        )

        for file_name in reviewed_git_context[
            "changed_files"
        ]:
            st.write(
                f"• `{file_name}`"
            )

        # The complete selected diff still goes to AI.
        # Expander only controls what the human sees.
        with st.expander(
            "View selected Git diff"
        ):
            if reviewed_git_context.get(
                "diff"
            ):
                st.code(
                    reviewed_git_context["diff"],
                    language="diff"
                )
            else:
                st.info(
                    "No Git diff available."
                )

        # ---------------------------------
        # TestRail scope
        # ---------------------------------

        st.markdown("### TestRail Scope")

        st.write(
            f"**{len(release_context['testrail_master_cases'])} "
            f"Master cases available to AI**"
        )

        st.caption(
            "The complete TestRail Master is provided to AI. "
            "Cases are not pre-filtered by Python."
        )

        st.divider()

        # ---------------------------------
        # Confirm context
        # ---------------------------------

        context_confirmed = (
            "release_context"
            in st.session_state
        )

        if not context_confirmed:
            if st.button(
                "Confirm Context",
                type="primary"
            ):
                st.session_state[
                    "release_context"
                ] = release_context

                st.session_state[
                    "master_cases"
                ] = master_cases

                st.rerun()

        else:
            st.success(
                "Context confirmed and ready for AI analysis."
            )

        # ---------------------------------
        # Analyze release
        # ---------------------------------

        if (
            "release_context"
            in st.session_state
        ):
            if st.button(
                "Analyze Release",
                type="primary"
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

    release_name = st.session_state.get(
        "current_release",
        current_release
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

        selected_cases = regression_plan[
            "selected_cases"
        ]

        proposed_cases = regression_plan[
            "proposed_new_cases"
        ]

        # ---------------------------------
        # Initialize reviewer exclusions
        # ---------------------------------

        if "excluded_plan_case_ids" not in st.session_state:
            st.session_state[
                "excluded_plan_case_ids"
            ] = set()

        if "excluded_proposed_case_indexes" not in st.session_state:
            st.session_state[
                "excluded_proposed_case_indexes"
            ] = set()

        # ---------------------------------
        # Plan summary
        # ---------------------------------

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Existing TestRail Cases",
                len(selected_cases)
            )

        with col2:
            st.metric(
                "Proposed New Cases",
                len(proposed_cases)
            )

        st.divider()

        # =================================
        # Existing TestRail cases
        # =================================

        st.markdown(
            "## Existing TestRail Cases"
        )

        st.caption(
            "Cases selected from the existing TestRail Master. "
            "Uncheck any case you do not want in the final regression run."
        )

        # Group existing cases using the authoritative
        # TestRail section already present in the plan.
        cases_by_section = {}

        for case in selected_cases:
            section = case.get(
                "section",
                "Other"
            )

            cases_by_section.setdefault(
                section,
                []
            ).append(case)

        for section, section_cases in cases_by_section.items():

            with st.expander(
                f"{section} ({len(section_cases)} cases)",
                expanded=True
            ):

                for case in section_cases:
                    case_id = case[
                        "case_id"
                    ]

                    include_case = st.checkbox(
                        f"C{case_id} - {case['title']}",
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

                    st.caption(
                        f"Impact: {case['impact_type']}"
                    )

                    st.write(
                        f"**Why selected:** "
                        f"{case['reason']}"
                    )

                    st.divider()

        # =================================
        # Proposed new cases
        # =================================

        st.markdown(
            "## Proposed New Cases"
        )

        st.caption(
            "These cases do not currently exist in the TestRail Master. "
            "They are recommendations only and will not automatically "
            "be added to TestRail."
        )

        if proposed_cases:

            # Short overall explanation using the AI's
            # existing proposal reasons.
            proposal_reasons = []

            for case in proposed_cases:
                reason = case.get(
                    "reason"
                )

                if reason:
                    proposal_reasons.append(
                        reason
                    )

            if proposal_reasons:
                st.info(
                    "Why new coverage is proposed: "
                    + " ".join(
                        proposal_reasons[:3]
                    )
                )

            for index, case in enumerate(
                proposed_cases
            ):

                include_proposed = st.checkbox(
                    case.get(
                        "title",
                        f"Proposed Case {index + 1}"
                    ),
                    value=(
                        index
                        not in st.session_state[
                            "excluded_proposed_case_indexes"
                        ]
                    ),
                    key=f"proposed_case_{index}"
                )

                if include_proposed:
                    st.session_state[
                        "excluded_proposed_case_indexes"
                    ].discard(
                        index
                    )
                else:
                    st.session_state[
                        "excluded_proposed_case_indexes"
                    ].add(
                        index
                    )

                reason = case.get(
                    "reason"
                )

                if reason:
                    st.write(
                        f"**Why proposed:** {reason}"
                    )

                impact_type = case.get(
                    "impact_type"
                )

                if impact_type:
                    st.caption(
                        f"Impact: {impact_type}"
                    )

                st.divider()

        else:
            st.info(
                "AI did not identify any missing regression coverage."
            )

        # ---------------------------------
        # Export proposed cases for later review
        # ---------------------------------

        if proposed_cases:

            csv_buffer = io.StringIO()

            writer = csv.writer(
                csv_buffer
            )

            writer.writerow([
                "Release",
                "Suggested Section",
                "Proposed Test Case",
                "Reason",
                "Selected for Current Plan"
            ])

            for index, case in enumerate(
                proposed_cases
            ):
                selected_now = (
                    index
                    not in st.session_state[
                        "excluded_proposed_case_indexes"
                    ]
                )

                writer.writerow([
                    release_name,
                    case.get(
                        "suggested_section",
                        ""
                    ),
                    case.get(
                        "title",
                        ""
                    ),
                    case.get(
                        "reason",
                        ""
                    ),
                    "Yes" if selected_now else "No"
                ])

            st.download_button(
                "Save Proposed Cases to CSV",
                data=csv_buffer.getvalue(),
                file_name=(
                    f"{release_name}_"
                    f"proposed_test_cases.csv"
                ),
                mime="text/csv"
            )

        # =================================
        # Final reviewer selections
        # =================================

        final_selected_cases = [
            case
            for case in selected_cases
            if case["case_id"]
            not in st.session_state[
                "excluded_plan_case_ids"
            ]
        ]

        final_proposed_cases = [
            case
            for index, case in enumerate(
                proposed_cases
            )
            if index
            not in st.session_state[
                "excluded_proposed_case_indexes"
            ]
        ]

        section_name_to_id = {
            case["section"]: case["section_id"]
            for case in st.session_state[
                "master_cases"
            ]
            if case.get("section")
            and case.get("section_id")
        }

        st.markdown(
            "### Final Reviewer Selection"
        )

        summary_col1, summary_col2 = st.columns(2)

        with summary_col1:
            st.write(
                f"Existing cases selected: "
                f"**{len(final_selected_cases)}**"
            )

        with summary_col2:
            st.write(
                f"New cases retained: "
                f"**{len(final_proposed_cases)}**"
            )

        st.divider()

        # =================================
        # Review actions
        # =================================

        approve_col, redo_col, start_col = st.columns(
            3
        )

        with approve_col:

            if "testrail_run" in st.session_state:
                st.success(
                    "Final plan already approved."
                )

            else:
                if st.button(
                    "Approve Final Plan",
                    type="primary"
                ):
                    created_new_cases = []

                    with st.spinner(
                        "Creating approved new TestRail cases..."
                    ):
                        for proposed_case in final_proposed_cases:

                            suggested_section = proposed_case[
                                "suggested_section"
                            ]

                            section_id = section_name_to_id.get(
                                suggested_section
                            )

                            if not section_id:
                                raise RuntimeError(
                                    f"TestRail section not found: "
                                    f"{suggested_section}"
                                )

                            new_case = create_test_case(
                                section_id=section_id,
                                title=proposed_case[
                                    "title"
                                ]
                            )

                            created_new_cases.append({
                                "case_id": new_case["id"],
                                "title": proposed_case[
                                    "title"
                                ],
                                "section": suggested_section
                            })

                    # Existing selected TestRail IDs
                    existing_case_ids = [
                        case["case_id"]
                        for case in final_selected_cases
                    ]

                    # Newly created TestRail IDs
                    new_case_ids = [
                        case["case_id"]
                        for case in created_new_cases
                    ]

                    # One final run containing both
                    all_case_ids = (
                        existing_case_ids
                        + new_case_ids
                    )

                    run_name = (
                        f"Dynamic Regression - "
                        f"{release_name}"
                    )

                    change_log_lines = [
                        f"AI Regression Plan Change Log - {current_release}",
                        "",
                        "Release Summary:",
                        regression_plan["release_summary"],
                        "",
                        "Regression Run Summary",
                        f"Existing cases selected: {len(existing_case_ids)}",
                        f"New cases added: {len(new_case_ids)}",
                        f"Total cases in run: {len(all_case_ids)}",
                        "",
                        "New Test Cases Added to Master"
                    ]

                    for case in created_new_cases:
                        change_log_lines.extend([
                            "",
                            f"C{case['case_id']} - {case['title']}",
                            f"Section: {case['section']}"
                        ])

                    run_description = "\n".join(
                        change_log_lines
                    )

                    with st.spinner(
                        "Creating TestRail regression run..."
                    ):
                        test_run = create_test_run(
                            run_name=run_name,
                            case_ids=all_case_ids,
                            description=run_description
                        )

                        approved_plan = {
                        "release_summary": regression_plan[
                            "release_summary"
                        ],
                        "selected_cases": final_selected_cases,
                        "proposed_new_cases": final_proposed_cases,
                        "created_new_cases": created_new_cases,
                        "run_description": run_description
                    }

                    st.session_state[
                        "approved_plan"
                    ] = approved_plan

                    st.session_state[
                        "testrail_run"
                    ] = test_run

                    st.success(
                        f"TestRail run created successfully. "
                        f"Run ID: {test_run['id']}"
                    )

                    st.rerun()

        with redo_col:

            # Redo is only available before
            # the final TestRail plan is created.
            if "testrail_run" not in st.session_state:

                if st.button(
                    "Redo Analysis"
                ):
                    # Keep the confirmed release context,
                    # but discard the current AI decision.
                    for key in [
                        "ai_result",
                        "regression_plan",
                        "approved_plan",
                        "testrail_run",
                        "excluded_plan_case_ids",
                        "excluded_proposed_case_indexes"
                    ]:
                        st.session_state.pop(
                            key,
                            None
                        )

                    with st.spinner(
                        "Re-analyzing release..."
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

                    st.rerun()

                # ---------------------------------
        # Persistent approved plan summary
        # ---------------------------------

        if (
            "testrail_run" in st.session_state
            and "approved_plan" in st.session_state
        ):
            test_run = st.session_state[
                "testrail_run"
            ]

            approved_plan = st.session_state[
                "approved_plan"
            ]

            created_new_cases = approved_plan.get(
                "created_new_cases",
                []
            )

            existing_cases = approved_plan.get(
                "selected_cases",
                []
            )

            st.divider()

            st.markdown(
                "## Plan Change Log"
            )

            st.success(
                f"Final regression plan created. "
                f"TestRail Run ID: {test_run['id']}"
            )

            st.write(
                f"**Existing cases selected:** "
                f"{len(existing_cases)}"
            )

            st.write(
                f"**New cases added:** "
                f"{len(created_new_cases)}"
            )

            st.write(
                f"**Total cases in run:** "
                f"{len(existing_cases) + len(created_new_cases)}"
            )

            if created_new_cases:
                st.markdown(
                    "### New Test Cases Added"
                )

                for case in created_new_cases:
                    st.write(
                        f"**C{case['case_id']} - "
                        f"{case['title']}**"
                    )

                    st.caption(
                        f"Section: {case['section']}"
                    )

        with start_col:

            if st.button(
                "Start Over"
            ):
                keys_to_clear = [
                    "release_loaded",
                    "jira_context",
                    "git_context",
                    "excluded_jira_keys",
                    "excluded_git_files",
                    "release_context",
                    "master_cases",
                    "ai_result",
                    "regression_plan",
                    "excluded_plan_case_ids",
                    "excluded_proposed_case_indexes",
                    "approved_plan",
                    "testrail_run"
                ]

                for key in keys_to_clear:
                    st.session_state.pop(
                        key,
                        None
                    )

                st.session_state[
                    "current_step"
                ] = "Jira"

                st.rerun()