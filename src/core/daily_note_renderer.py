from pathlib import Path
from typing import Any, Dict, Iterable, List


def _clean_link_text(value: str) -> str:
    return value.replace("[", "").replace("]", "").replace("|", "-").strip()


def daily_note_link(date: str) -> str:
    return f"[[daily_notes/{date}|{date}]]"


def commit_note_link(commit: Dict[str, str]) -> str:
    project = commit["project"].replace(" ", "_").replace("/", "_")
    commit_id = commit["id"]
    title = _clean_link_text(commit["title"])
    return (
        f"[[projects/{project}/commits/{commit_id}|"
        f"{commit_id[:12]} {title}]]"
    )


def project_note_link(project: str) -> str:
    clean_project = _clean_link_text(project).replace(" ", "_").replace("/", "_")
    return f"[[projects/{clean_project}|{project}]]"


def agent_note_link(source: str) -> str:
    labels = {
        "claude": "Claude",
        "codex": "Codex",
        "copilot": "Copilot",
        "ollama": "Ollama",
        "pi": "Pi",
        "shell": "Shell",
    }
    label = labels.get(source.lower(), source.title())
    return f"[[agents/{label}|{label}]]"


def render_graph_connections(
    sources: Iterable[str], commits: Iterable[Dict[str, str]], existing: str = ""
) -> str:
    """Render only graph links that are not already present in a daily note."""
    source_links = [agent_note_link("ollama")]
    source_links.extend(
        agent_note_link(source)
        for source in sorted(set(sources))
        if source.lower() != "ollama"
    )
    new_source_links = [link for link in source_links if link not in existing]
    new_commit_links = [
        commit_note_link(commit)
        for commit in commits
        if commit_note_link(commit) not in existing
    ]
    if not new_source_links and not new_commit_links:
        return ""

    lines = ["## Connected graph"]
    if new_source_links:
        lines.append("- **Agents:** " + ", ".join(new_source_links))
    if new_commit_links:
        lines.append("- **Commits:**")
        lines.extend(f"  - {link}" for link in new_commit_links)
    return "\n".join(lines)


def render_daily_note(
    date: str,
    summary: str,
    sections: Iterable[Dict[str, Any]],
    commits: List[Dict[str, str]],
    related_dates: Iterable[str],
) -> str:
    """Render a technical daily note with stable links to related vault notes."""
    commits_by_id = {
        commit["id"]: commit for commit in commits
    }
    commits_by_id.update(
        {commit["id"][:12]: commit for commit in commits}
    )
    graph_connections = render_graph_connections(
        [
            source
            for section in sections
            if isinstance((source := section.get("source")), str)
        ],
        commits,
    )
    lines = [
        f"# Daily Journal: {date}",
        "",
        "## Day summary",
        summary.strip(),
    ]

    if commits:
        lines.extend(["", "## Commits"])
        lines.extend(f"- {commit_note_link(commit)}" for commit in commits)

    lines.extend(["", "## Technical notes"])
    for index, section in enumerate(sections, start=1):
        title = _clean_link_text(str(section.get("title") or f"Work item {index}"))
        lines.extend(
            [
                "",
                f"### {title}",
                "",
                "**What was done**",
                str(section.get("work_done") or "No implementation detail captured.").strip(),
                "",
                "**What went well**",
                str(section.get("went_well") or "Not recorded.").strip(),
                "",
                "**What we learned**",
                str(section.get("learned") or "Not recorded.").strip(),
                "",
                "**Worth remembering**",
                str(section.get("remember") or "Not recorded.").strip(),
            ]
        )
        section_commit_ids = section.get("commits")
        if not isinstance(section_commit_ids, list):
            section_commit_ids = []
        section_commits = [
            commits_by_id[commit_id]
            for commit_id in section_commit_ids
            if isinstance(commit_id, str) and commit_id in commits_by_id
        ]
        if section_commits:
            lines.extend(["", "**Related commits**"])
            lines.extend(f"- {commit_note_link(commit)}" for commit in section_commits)
        project = section.get("project")
        if not isinstance(project, str) and section_commits:
            project = section_commits[0]["project"]
        if isinstance(project, str) and project != "unassigned":
            lines.extend(["", f"**Related project:** {project_note_link(project)}"])
        source = section.get("source")
        if isinstance(source, str):
            lines.extend(["", f"**Agent source:** {agent_note_link(source)}"])

    related_links = [daily_note_link(related_date) for related_date in related_dates]
    if related_links:
        lines.extend(["", "## Related notes"])
        lines.extend(f"- {link}" for link in related_links)

    if graph_connections:
        lines.extend(["", graph_connections])
    lines.extend(["", "---", "*Generated by Autograph Agent*"])
    return "\n".join(lines) + "\n"


def related_daily_dates(notes_dir: Path, date: str) -> List[str]:
    """Find the immediately adjacent existing daily notes for navigation."""
    dates = sorted(
        note_path.stem
        for note_path in notes_dir.glob("*.md")
        if note_path.stem != date
    )
    previous = [candidate for candidate in dates if candidate < date]
    following = [candidate for candidate in dates if candidate > date]
    related = []
    if previous:
        related.append(previous[-1])
    if following:
        related.append(following[0])
    return related
