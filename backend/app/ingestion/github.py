import os
import re
import json
import base64
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
from app.core.errors import ContinuityException
from app.schemas.enums import ErrorCode

GITHUB_URL_REGEX = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$")


class GitHubClient:
    def __init__(self, mode: Optional[str] = None, token: Optional[str] = None):
        self.mode = mode or settings.GITHUB_MODE
        self.token = token or settings.GITHUB_TOKEN

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ContinuityAI-Ingestion",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def validate_and_parse_url(self, repo_url: str) -> Tuple[str, str]:
        url = repo_url.strip()
        if url.endswith(".git"):
            url = url[:-4]
        match = GITHUB_URL_REGEX.match(url)
        if not match:
            raise ContinuityException(
                code=ErrorCode.GITHUB_URL_INVALID,
                message="Use a public repository URL like https://github.com/owner/repo.",
                status_code=422,
            )
        owner, repo = match.group(1), match.group(2)
        return owner, repo

    def fetch_repo_files(self, repo_url: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Returns commit_sha and list of {path, size, content_bytes}"""
        owner, repo = self.validate_and_parse_url(repo_url)

        if self.mode == "fixture":
            fixture_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "tests", "fixtures", "github"
            )
            fixture_file = os.path.join(fixture_dir, f"{owner}_{repo}.json")
            default_fixture = os.path.join(fixture_dir, "default_repo.json")

            target_file = fixture_file if os.path.exists(fixture_file) else default_fixture
            if not os.path.exists(target_file):
                # Return synthetic repo data for demo/tests
                return "a1b2c3d4e5f67890abcdef1234567890abcdef12", [
                    {
                        "path": "README.md",
                        "size": 120,
                        "content": b"# Project Roomiez\nRoomiez is a room sharing application.\n",
                    },
                    {
                        "path": "docs/architecture.md",
                        "size": 250,
                        "content": b"# Architecture\nAuthentication is implemented with JWT sessions.\n",
                    },
                ]
            with open(target_file, "r") as f:
                data = json.load(f)
                files = []
                for item in data.get("files", []):
                    content = item["content"].encode("utf-8") if isinstance(item["content"], str) else base64.b64decode(item["content_base64"])
                    files.append({
                        "path": item["path"],
                        "size": len(content),
                        "content": content,
                    })
                return data.get("commit_sha", "fixture_commit_sha"), files

        # Live GitHub REST API mode
        headers = self._get_headers()
        timeout = float(settings.LLM_TIMEOUT_SECONDS if hasattr(settings, "LLM_TIMEOUT_SECONDS") else 10.0)

        with httpx.Client(timeout=10.0) as client:
            try:
                # 1. Fetch repo metadata
                repo_resp = client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
                if repo_resp.status_code == 404:
                    raise ContinuityException(
                        code=ErrorCode.GITHUB_URL_INVALID,
                        message="Repository not found or private",
                        status_code=422,
                    )
                elif repo_resp.status_code == 403:
                    raise ContinuityException(
                        code=ErrorCode.GITHUB_RATE_LIMITED,
                        message="GitHub API rate limit exceeded",
                        status_code=429,
                    )
                elif repo_resp.status_code >= 500:
                    raise ContinuityException(
                        code=ErrorCode.GITHUB_UNAVAILABLE,
                        message="GitHub is currently unavailable",
                        status_code=502,
                    )
                elif repo_resp.status_code != 200:
                    raise ContinuityException(
                        code=ErrorCode.GITHUB_UNAVAILABLE,
                        message=f"GitHub error {repo_resp.status_code}",
                        status_code=502,
                    )

                repo_info = repo_resp.json()
                default_branch = repo_info.get("default_branch", "main")

                # 2. Get commit sha of default branch head
                branch_resp = client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/commits/{default_branch}",
                    headers=headers,
                )
                if branch_resp.status_code != 200:
                    raise ContinuityException(
                        code=ErrorCode.GITHUB_UNAVAILABLE,
                        message="Failed to retrieve default branch commit",
                        status_code=502,
                    )
                commit_sha = branch_resp.json()["sha"]

                # 3. List recursive git tree
                tree_resp = client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1",
                    headers=headers,
                )
                if tree_resp.status_code != 200:
                    raise ContinuityException(
                        code=ErrorCode.GITHUB_UNAVAILABLE,
                        message="Failed to retrieve repository tree",
                        status_code=502,
                    )
                tree_entries = tree_resp.json().get("tree", [])

                # Filter entries: blob, .md or .txt, size <= 200 KB
                candidate_files = []
                for entry in tree_entries:
                    if entry.get("type") != "blob":
                        continue
                    path = entry.get("path", "")
                    size = entry.get("size", 0)
                    lower = path.lower()
                    if lower.endswith(".md") or lower.endswith(".txt"):
                        if size <= 200 * 1024:
                            candidate_files.append((path, size, entry.get("sha")))

                # Sort: README first, then alphabetical
                def sort_key(item):
                    p = item[0]
                    is_readme = 0 if "readme" in os.path.basename(p).lower() else 1
                    return (is_readme, p.lower())

                candidate_files.sort(key=sort_key)
                selected_files = candidate_files[:15]

                result_files = []
                for path, size, sha in selected_files:
                    blob_resp = client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}",
                        headers=headers,
                    )
                    if blob_resp.status_code == 200:
                        blob_json = blob_resp.json()
                        raw_content = base64.b64decode(blob_json["content"])
                        result_files.append({
                            "path": path,
                            "size": len(raw_content),
                            "content": raw_content,
                        })

                return commit_sha, result_files

            except httpx.TimeoutException:
                raise ContinuityException(
                    code=ErrorCode.GITHUB_UNAVAILABLE,
                    message="GitHub request timed out",
                    status_code=502,
                )
            except httpx.RequestError:
                raise ContinuityException(
                    code=ErrorCode.GITHUB_UNAVAILABLE,
                    message="Failed to connect to GitHub",
                    status_code=502,
                )
