from integration.release_planner.testrail_service import (
    load_master_cases
)


cases = load_master_cases()

print(
    f"Master cases loaded: "
    f"{len(cases)}"
)

print()

for case in cases[:5]:
    print(
        f"C{case['case_id']} - "
        f"{case['section']} - "
        f"{case['title']}"
    )