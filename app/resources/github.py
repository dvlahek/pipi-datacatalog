from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import httpx

from app.config import Settings


class GitHubResourceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GitHubRepositoryRef:
    owner: str
    repo: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def html_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


@dataclass(frozen=True, slots=True)
class GitHubRepositorySnapshot:
    owner: str
    repo: str
    full_name: str
    html_url: str
    description: str | None
    visibility: str
    default_branch: str
    head_sha: str
    pushed_at: str | None
    language: str | None
    license_spdx: str | None
    topics: tuple[str, ...]
    archived: bool
    size_kb: int | None


@dataclass(frozen=True, slots=True)
class GitHubTextFile:
    path: str
    blob_sha: str
    byte_size: int
    raw_url: str
    text: str


@dataclass(frozen=True, slots=True)
class GitHubRepositoryCorpus:
    repository: GitHubRepositorySnapshot
    files: tuple[GitHubTextFile, ...]
    tree_truncated: bool
    candidate_count: int
    selected_count: int
    fetched_bytes: int
    content_sha256: str


_TEXT_SUFFIXES = {
    ".c", ".cc", ".cfg", ".clj", ".cljs", ".cmake", ".conf", ".cpp", ".cs",
    ".css", ".dart", ".go", ".h", ".hpp", ".html", ".ini", ".java", ".js",
    ".jsx", ".json", ".kt", ".kts", ".lua", ".md", ".mdx", ".mjs", ".php",
    ".pl", ".properties", ".ps1", ".py", ".r", ".rb", ".rs", ".rst", ".scala",
    ".sh", ".sql", ".swift", ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml",
    ".yml",
}
_TEXT_FILENAMES = {
    "dockerfile", "gemfile", "makefile", "procfile", "rakefile", "readme",
}
_IGNORED_PARTS = {
    ".git", ".idea", ".next", ".nuxt", ".tox", ".venv", ".vscode", "__pycache__",
    "build", "coverage", "dist", "licenses", "node_modules", "target", "vendor",
}
_IGNORED_FILENAMES = {
    "bun.lock", "composer.lock", "package-lock.json", "pnpm-lock.yaml", "poetry.lock",
    "yarn.lock",
}


def parse_github_repository_url(url: str) -> GitHubRepositoryRef | None:
    """Recognize a GitHub repository root URL without treating sub-pages as repositories."""

    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if (parsed.hostname or "").lower() not in {"github.com", "www.github.com"}:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        return None

    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return GitHubRepositoryRef(owner=owner, repo=repo)


def is_indexable_github_path(path: str) -> bool:
    pure = PurePosixPath(path)
    lowered_parts = {part.lower() for part in pure.parts}
    if lowered_parts & _IGNORED_PARTS:
        return False
    name = pure.name.lower()
    if name in _IGNORED_FILENAMES or name.endswith(".min.js") or name.endswith(".min.css"):
        return False
    if name in _TEXT_FILENAMES or name.startswith("readme."):
        return True
    return pure.suffix.lower() in _TEXT_SUFFIXES


def select_github_tree_entries(
    tree: list[dict[str, object]],
    *,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = str(entry.get("path") or "")
        if not path or not is_indexable_github_path(path):
            continue
        size = int(entry.get("size") or 0)
        if size <= 0 or size > max_file_bytes:
            continue
        candidates.append(entry)

    def priority(entry: dict[str, object]) -> tuple[int, int, str]:
        path = str(entry.get("path") or "")
        lower = path.lower()
        if lower.startswith("readme"):
            group = 0
        elif lower.startswith("docs/") or "/docs/" in lower:
            group = 1
        elif lower.endswith((".md", ".mdx", ".rst", ".txt")):
            group = 2
        else:
            group = 3
        return (group, path.count("/"), lower)

    candidates.sort(key=priority)
    selected: list[dict[str, object]] = []
    total = 0
    for entry in candidates:
        if len(selected) >= max_files:
            break
        size = int(entry.get("size") or 0)
        if total + size > max_total_bytes:
            continue
        selected.append(entry)
        total += size
    return selected


def _headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PiPi-Data-Catalog/0.1 github-adapter",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_api_token:
        headers["Authorization"] = f"Bearer {settings.github_api_token}"
    return headers


async def _github_json(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> dict[str, object]:
    try:
        response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise GitHubResourceError(f"GitHub request failed: {exc}") from exc

    if response.status_code == 404:
        raise GitHubResourceError("GitHub repository or revision was not found or is not publicly accessible.")
    if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
        raise GitHubResourceError("GitHub API rate limit reached. Configure GITHUB_API_TOKEN for a higher limit.")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise GitHubResourceError(f"GitHub API returned HTTP {response.status_code}.") from exc

    payload = response.json()
    if not isinstance(payload, dict):
        raise GitHubResourceError("GitHub API returned an unexpected response.")
    return payload


async def fetch_github_repository_snapshot(
    source_url: str,
    settings: Settings,
) -> GitHubRepositorySnapshot:
    ref = parse_github_repository_url(source_url)
    if ref is None:
        raise GitHubResourceError("URL is not a GitHub repository root URL.")

    timeout = httpx.Timeout(settings.github_timeout_seconds)
    headers = _headers(settings)
    api_repo = f"https://api.github.com/repos/{quote(ref.owner, safe='')}/{quote(ref.repo, safe='')}"

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        repository = await _github_json(client, api_repo, headers)
        if bool(repository.get("private")):
            raise GitHubResourceError(
                "Private GitHub repositories are not supported by the public repository adapter yet."
            )

        default_branch = str(repository.get("default_branch") or "")
        if not default_branch:
            raise GitHubResourceError("GitHub repository has no default branch.")
        commit = await _github_json(
            client,
            f"{api_repo}/commits/{quote(default_branch, safe='')}",
            headers,
        )

    head_sha = str(commit.get("sha") or "")
    if not head_sha:
        raise GitHubResourceError("GitHub did not return a HEAD commit SHA.")

    license_payload = repository.get("license")
    license_spdx = None
    if isinstance(license_payload, dict):
        value = license_payload.get("spdx_id")
        if value and value != "NOASSERTION":
            license_spdx = str(value)

    topics_raw = repository.get("topics")
    topics = tuple(str(item) for item in topics_raw) if isinstance(topics_raw, list) else ()

    return GitHubRepositorySnapshot(
        owner=str((repository.get("owner") or {}).get("login") if isinstance(repository.get("owner"), dict) else ref.owner),
        repo=str(repository.get("name") or ref.repo),
        full_name=str(repository.get("full_name") or ref.full_name),
        html_url=str(repository.get("html_url") or ref.html_url),
        description=str(repository["description"]) if repository.get("description") else None,
        visibility=str(repository.get("visibility") or "public"),
        default_branch=default_branch,
        head_sha=head_sha,
        pushed_at=str(repository["pushed_at"]) if repository.get("pushed_at") else None,
        language=str(repository["language"]) if repository.get("language") else None,
        license_spdx=license_spdx,
        topics=topics,
        archived=bool(repository.get("archived")),
        size_kb=int(repository["size"]) if repository.get("size") is not None else None,
    )


async def fetch_github_repository_corpus(
    snapshot: GitHubRepositorySnapshot,
    settings: Settings,
) -> GitHubRepositoryCorpus:
    """Fetch a bounded, text-only view of one repository at an immutable commit SHA."""

    timeout = httpx.Timeout(settings.github_timeout_seconds)
    headers = _headers(settings)
    api_repo = f"https://api.github.com/repos/{quote(snapshot.owner, safe='')}/{quote(snapshot.repo, safe='')}"

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        tree_payload = await _github_json(
            client,
            f"{api_repo}/git/trees/{quote(snapshot.head_sha, safe='')}?recursive=1",
            headers,
        )
        tree = tree_payload.get("tree")
        if not isinstance(tree, list):
            raise GitHubResourceError("GitHub repository tree is unavailable.")

        candidate_count = sum(
            1
            for entry in tree
            if isinstance(entry, dict)
            and entry.get("type") == "blob"
            and is_indexable_github_path(str(entry.get("path") or ""))
            and 0 < int(entry.get("size") or 0) <= settings.github_index_max_file_bytes
        )
        selected = select_github_tree_entries(
            [entry for entry in tree if isinstance(entry, dict)],
            max_files=settings.github_index_max_files,
            max_file_bytes=settings.github_index_max_file_bytes,
            max_total_bytes=settings.github_index_max_total_bytes,
        )

        files: list[GitHubTextFile] = []
        digest = hashlib.sha256()
        fetched_bytes = 0
        for entry in selected:
            path = str(entry.get("path") or "")
            blob_sha = str(entry.get("sha") or "")
            raw_path = "/".join(quote(part, safe="") for part in path.split("/"))
            raw_url = (
                f"https://raw.githubusercontent.com/{quote(snapshot.owner, safe='')}/"
                f"{quote(snapshot.repo, safe='')}/{quote(snapshot.head_sha, safe='')}/{raw_path}"
            )
            try:
                response = await client.get(
                    raw_url,
                    headers={"User-Agent": "PiPi-Data-Catalog/0.1 github-indexer"},
                )
                response.raise_for_status()
            except httpx.HTTPError:
                continue

            content = response.content
            if len(content) > settings.github_index_max_file_bytes or b"\x00" in content:
                continue
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                continue
            text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
            if not text:
                continue

            path_bytes = path.encode("utf-8")
            digest.update(len(path_bytes).to_bytes(4, "big"))
            digest.update(path_bytes)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
            fetched_bytes += len(content)
            files.append(
                GitHubTextFile(
                    path=path,
                    blob_sha=blob_sha,
                    byte_size=len(content),
                    raw_url=raw_url,
                    text=text,
                )
            )

    if not files:
        raise GitHubResourceError("No bounded text/code files could be fetched from the GitHub repository.")

    return GitHubRepositoryCorpus(
        repository=snapshot,
        files=tuple(files),
        tree_truncated=bool(tree_payload.get("truncated")),
        candidate_count=candidate_count,
        selected_count=len(files),
        fetched_bytes=fetched_bytes,
        content_sha256=digest.hexdigest(),
    )
