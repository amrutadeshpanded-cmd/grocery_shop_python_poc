import subprocess


class GitClient:
    def __init__(self, repo_path="."):
        self.repo_path = repo_path

    def _run_git(self, args):
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Git command failed: git {' '.join(args)}\n"
                f"{result.stderr}"
            )

        return result.stdout.strip()

    def ref_exists(self, ref):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        return result.returncode == 0

    def get_file_at_ref(self, ref, file_path):
        """
        Return the complete contents of a file at a specific Git ref.
        """
        return self._run_git([
            "show",
            f"{ref}:{file_path}"
        ])

    def get_changed_file_context(self, base_ref, target_ref):
        """
        Return the current contents of changed files from the target ref.
        Deleted files are skipped.
        """

        changed_files = self.get_changed_files(
            base_ref,
            target_ref
        )

        context = {}

        for item in changed_files:
            status = item["status"]
            path = item["path"]

            # Deleted file does not exist in target ref
            if status.startswith("D"):
                continue

            try:
                context[path] = self.get_file_at_ref(
                    target_ref,
                    path
                )
            except Exception as exc:
                context[path] = (
                    f"Unable to read file context: {exc}"
                )

        return context

    def get_current_branch(self):
        return self._run_git(["branch", "--show-current"])

    def get_commits(self, base_ref, target_ref):
        output = self._run_git([
            "log",
            f"{base_ref}..{target_ref}",
            "--pretty=format:%H|%h|%an|%ad|%s",
            "--date=iso"
        ])

        commits = []

        if not output:
            return commits

        for line in output.splitlines():
            parts = line.split("|", 4)

            if len(parts) == 5:
                commits.append({
                    "sha": parts[0],
                    "short_sha": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                    "message": parts[4]
                })

        return commits

    def get_changed_files(self, base_ref, target_ref):
        output = self._run_git([
            "diff",
            "--name-status",
            base_ref,
            target_ref
        ])

        files = []

        if not output:
            return files

        for line in output.splitlines():
            parts = line.split("\t")

            if len(parts) >= 2:
                files.append({
                    "status": parts[0],
                    "path": parts[-1]
                })

        return files

    def get_diff_stat(self, base_ref, target_ref):
        return self._run_git([
            "diff",
            "--stat",
            base_ref,
            target_ref
        ])

    def get_diff(self, base_ref, target_ref):
        return self._run_git([
            "diff",
            "--no-ext-diff",
            "--unified=3",
            base_ref,
            target_ref
        ])

    def get_release_context(self, base_ref, target_ref):
        if not self.ref_exists(base_ref):
            raise ValueError(
                f"Base ref does not exist: {base_ref}"
            )

        if not self.ref_exists(target_ref):
            raise ValueError(
                f"Target ref does not exist: {target_ref}"
            )

        commits = self.get_commits(
            base_ref,
            target_ref
        )

        changed_files = self.get_changed_files(
            base_ref,
            target_ref
        )

        return {
            "base_ref": base_ref,
            "target_ref": target_ref,
            "commit_count": len(commits),
            "commits": commits,
            "changed_files": changed_files,
            "diff_stat": self.get_diff_stat(
                base_ref,
                target_ref
            ),
            "diff": self.get_diff(
                base_ref,
                target_ref
            ),
            "changed_file_context":
                self.get_changed_file_context(
                    base_ref,
                    target_ref
                )
        }
        