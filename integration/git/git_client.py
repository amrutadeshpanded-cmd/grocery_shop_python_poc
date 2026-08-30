import subprocess
from pathlib import Path


class GitClient:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path).resolve()

        if not (self.repo_path / ".git").exists():
            raise RuntimeError(
                f"{self.repo_path} is not a Git repository"
            )

    def _run_git(self, args):
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Git command failed:\n"
                f"git {' '.join(args)}\n\n"
                f"{result.stderr}"
            )

        return result.stdout.strip()

    def get_current_branch(self):
        return self._run_git(
            ["branch", "--show-current"]
        )

    def get_tags(self):
        output = self._run_git(
            ["tag", "--list"]
        )

        if not output:
            return []

        return output.splitlines()

    def ref_exists(self, ref):
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "--verify",
                "--quiet",
                ref,
            ],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )

        return result.returncode == 0

    def get_commits(self, base_ref, target_ref):
        output = self._run_git(
            [
                "log",
                f"{base_ref}..{target_ref}",
                "--pretty=format:%H|%h|%an|%ad|%s",
                "--date=iso",
            ]
        )

        if not output:
            return []

        commits = []

        for line in output.splitlines():
            parts = line.split("|", 4)

            if len(parts) != 5:
                continue

            commits.append(
                {
                    "commit_hash": parts[0],
                    "short_hash": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                }
            )

        return commits

    def get_changed_files(self, base_ref, target_ref):
        output = self._run_git(
            [
                "diff",
                "--name-status",
                base_ref,
                target_ref,
            ]
        )

        if not output:
            return []

        changed_files = []

        for line in output.splitlines():
            parts = line.split("\t")

            status = parts[0]

            if status.startswith("R") and len(parts) >= 3:
                changed_files.append(
                    {
                        "status": "R",
                        "old_path": parts[1],
                        "path": parts[2],
                    }
                )

            elif len(parts) >= 2:
                changed_files.append(
                    {
                        "status": status,
                        "path": parts[1],
                    }
                )

        return changed_files

    def get_diff(self, base_ref, target_ref):
        return self._run_git(
            [
                "diff",
                "--no-ext-diff",
                "--unified=3",
                base_ref,
                target_ref,
            ]
        )

    def get_diff_stat(self, base_ref, target_ref):
        return self._run_git(
            [
                "diff",
                "--stat",
                base_ref,
                target_ref,
            ]
        )

    def get_file_diff(
        self,
        base_ref,
        target_ref,
        file_path,
    ):
        return self._run_git(
            [
                "diff",
                "--unified=5",
                base_ref,
                target_ref,
                "--",
                file_path,
            ]
        )

    def get_commit_count(
        self,
        base_ref,
        target_ref,
    ):
        output = self._run_git(
            [
                "rev-list",
                "--count",
                f"{base_ref}..{target_ref}",
            ]
        )

        return int(output or 0)

    def get_release_context(
        self,
        base_ref,
        target_ref,
    ):
        if not self.ref_exists(base_ref):
            raise RuntimeError(
                f"Base Git ref does not exist: "
                f"{base_ref}"
            )

        if not self.ref_exists(target_ref):
            raise RuntimeError(
                f"Target Git ref does not exist: "
                f"{target_ref}"
            )

        return {
            "base_ref": base_ref,
            "target_ref": target_ref,
            "commit_count":
                self.get_commit_count(
                    base_ref,
                    target_ref,
                ),
            "commits":
                self.get_commits(
                    base_ref,
                    target_ref,
                ),
            "changed_files":
                self.get_changed_files(
                    base_ref,
                    target_ref,
                ),
            "diff_stat":
                self.get_diff_stat(
                    base_ref,
                    target_ref,
                ),
            "diff":
                self.get_diff(
                    base_ref,
                    target_ref,
                ),
        }