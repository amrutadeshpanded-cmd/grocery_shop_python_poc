import subprocess


def run_git_command(repo_path, *args):
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            *args
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return result.stdout.strip()


def get_release_git_context(
    repo_path,
    base_ref,
    target_ref
):
    commits_text = run_git_command(
        repo_path,
        "log",
        "--pretty=format:%H|%s",
        f"{base_ref}..{target_ref}"
    )

    changed_files_text = run_git_command(
        repo_path,
        "diff",
        "--name-only",
        base_ref,
        target_ref
    )

    diff_text = run_git_command(
        repo_path,
        "diff",
        base_ref,
        target_ref
    )

    commits = []

    if commits_text:
        for line in commits_text.splitlines():
            commit_hash, message = line.split(
                "|",
                1
            )

            commits.append({
                "hash": commit_hash,
                "message": message
            })

    changed_files = (
        changed_files_text.splitlines()
        if changed_files_text
        else []
    )

    return {
        "base_ref": base_ref,
        "target_ref": target_ref,
        "commit_count": len(commits),
        "commits": commits,
        "changed_files": changed_files,
        "diff": diff_text
    }

def get_files_diff(
    repo_path,
    base_ref,
    target_ref,
    files
):
    if not files:
        return ""

    return run_git_command(
        repo_path,
        "diff",
        base_ref,
        target_ref,
        "--",
        *files
    )