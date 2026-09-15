import requests
from urllib.parse import urlparse

def parse_github_repository_url(
    repository_url
):
    """
    Extract GitHub owner and repository name
    from a GitHub repository URL.
    """

    parsed_url = urlparse(
        repository_url
    )

    if parsed_url.netloc != "github.com":
        raise ValueError(
            "Only GitHub repository URLs are supported."
        )

    path_parts = [
        part
        for part in parsed_url.path.split("/")
        if part
    ]

    if len(path_parts) < 2:
        raise ValueError(
            "Invalid GitHub repository URL."
        )

    owner = path_parts[0]

    repo = path_parts[1].removesuffix(
        ".git"
    )

    return owner, repo

def get_github_compare(
    repository_url,
    base_ref,
    target_ref
):
    """
    Compare two GitHub refs and return
    changed files with their patches.
    """

    owner, repo = parse_github_repository_url(
        repository_url
    )

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/compare/"
        f"{base_ref}...{target_ref}"
    )

    response = requests.get(
        url,
        timeout=30
    )

    response.raise_for_status()

    return response.json()

def get_github_release_context(
    repository_url,
    base_ref,
    target_ref
):
    compare_data = get_github_compare(
        repository_url=repository_url,
        base_ref=base_ref,
        target_ref=target_ref
    )

    changed_files = []
    diff_parts = []

    for file in compare_data.get(
        "files",
        []
    ):
        filename = file.get(
            "filename"
        )

        changed_files.append(
            filename
        )

        patch = file.get(
            "patch",
            ""
        )

        if patch:
            diff_parts.append(
                f"File: {filename}\n{patch}"
            )

    return {
        "base_ref": base_ref,
        "target_ref": target_ref,
        "commit_count": compare_data.get(
            "total_commits",
            0
        ),
        "changed_files": changed_files,
        "diff": "\n\n".join(
            diff_parts
        )
    }


def get_github_files_diff(
    repository_url,
    base_ref,
    target_ref,
    files
):
    compare_data = get_github_compare(
        repository_url=repository_url,
        base_ref=base_ref,
        target_ref=target_ref
    )

    selected_files = set(files)

    diff_parts = []

    for file in compare_data.get(
        "files",
        []
    ):
        filename = file.get(
            "filename"
        )

        if filename not in selected_files:
            continue

        patch = file.get(
            "patch",
            ""
        )

        if patch:
            diff_parts.append(
                f"File: {filename}\n{patch}"
            )

    return "\n\n".join(
        diff_parts
    )
