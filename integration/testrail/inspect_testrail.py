from testrail_client import TestRailClient

client = TestRailClient()

project = client.get_project()

print("Project:")
print(project)

print("\nSuites:")

try:
    suites = client.get_suites()

    if isinstance(suites, dict):
        suites = suites.get("suites", [])

    for suite in suites:
        print(
            f"ID={suite.get('id')} "
            f"Name={suite.get('name')}"
        )

except Exception as exc:
    print("Could not retrieve suites:")
    print(exc)

print("\nExisting sections:")

try:
    sections = client.get_sections()

    for section in sections:
        print(
            f"ID={section.get('id')} "
            f"Name={section.get('name')}"
        )

except Exception as exc:
    print("Could not retrieve sections:")
    print(exc)