from app.resources.github import (
    is_indexable_github_path,
    parse_github_repository_url,
    select_github_tree_entries,
)


def test_parse_github_repository_url_accepts_repository_roots() -> None:
    ref = parse_github_repository_url("https://github.com/morluto/rea")
    assert ref is not None
    assert ref.owner == "morluto"
    assert ref.repo == "rea"
    assert ref.full_name == "morluto/rea"

    git_ref = parse_github_repository_url("https://github.com/morluto/rea.git")
    assert git_ref is not None
    assert git_ref.repo == "rea"


def test_parse_github_repository_url_rejects_subpages_and_other_hosts() -> None:
    assert parse_github_repository_url("https://github.com/morluto/rea/issues") is None
    assert parse_github_repository_url("https://raw.githubusercontent.com/morluto/rea/main/README.md") is None
    assert parse_github_repository_url("https://example.org/morluto/rea") is None


def test_github_indexing_filters_generated_binary_and_bundled_license_paths() -> None:
    assert is_indexable_github_path("README.md")
    assert is_indexable_github_path("docs/architecture.md")
    assert is_indexable_github_path("src/main.ts")
    assert is_indexable_github_path("Dockerfile")
    # Keep a repository-level license available for explicit licensing questions,
    # but do not index large dependency/bundled license collections as RAG content.
    assert is_indexable_github_path("LICENSE.txt")
    assert not is_indexable_github_path("licenses/Node-22.19.0-LICENSE.txt")
    assert not is_indexable_github_path("third_party/licenses/dependency.txt")
    assert not is_indexable_github_path("node_modules/pkg/index.js")
    assert not is_indexable_github_path("dist/app.js")
    assert not is_indexable_github_path("package-lock.json")
    assert not is_indexable_github_path("assets/logo.png")


def test_github_tree_selection_prioritizes_docs_and_respects_bounds() -> None:
    tree = [
        {"type": "blob", "path": "src/z.ts", "size": 40, "sha": "1"},
        {"type": "blob", "path": "README.md", "size": 30, "sha": "2"},
        {"type": "blob", "path": "docs/guide.md", "size": 30, "sha": "3"},
        {"type": "blob", "path": "src/a.ts", "size": 40, "sha": "4"},
        {"type": "blob", "path": "node_modules/x.js", "size": 10, "sha": "5"},
        {"type": "blob", "path": "licenses/Node-LICENSE.txt", "size": 10, "sha": "6"},
    ]

    selected = select_github_tree_entries(
        tree,
        max_files=3,
        max_file_bytes=100,
        max_total_bytes=100,
    )

    assert [item["path"] for item in selected] == ["README.md", "docs/guide.md", "src/a.ts"]
