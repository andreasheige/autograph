import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def render_frontmatter(fields: Dict[str, Any]) -> List[str]:
    """Render YAML properties Obsidian can query; strings are JSON-quoted."""
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            rendered = "[" + ", ".join(json.dumps(item) for item in value) + "]"
        elif isinstance(value, int) or ISO_DATE_PATTERN.match(str(value)):
            rendered = str(value)
        else:
            rendered = json.dumps(value)
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return lines


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


def agent_label(source: str) -> str:
    labels = {
        "claude": "Claude",
        "chatgpt": "ChatGPT",
        "claudedesktop": "Claude Desktop",
        "codexdesktop": "Codex Desktop",
        "codex": "Codex",
        "copilot": "Copilot",
        "ollama": "Ollama",
        "pi": "Pi",
        "shell": "Shell",
    }
    return labels.get(source.lower(), source.title())


def agent_note_link(source: str) -> str:
    label = agent_label(source)
    return f"[[agents/{label}|{label}]]"


def session_note_link(source: str, session_id: object) -> str:
    """Link a work unit to its session stub, when the id identifies one session."""
    if source.lower() == "git" or not isinstance(session_id, str):
        return ""
    if session_id == "unknown-session" or not SESSION_ID_PATTERN.match(session_id):
        return ""
    return f"[[sessions/{source.lower()}/{session_id}|{session_id[:8]}]]"


def model_list(models: object) -> str:
    if not isinstance(models, list):
        return ""
    return ", ".join(f"`{model}`" for model in models if isinstance(model, str))


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
    projects = {
        project
        for section in sections
        if isinstance((project := section.get("project")), str)
        and project != "unassigned"
    }
    projects.update(commit["project"] for commit in commits)
    models = {
        model
        for section in sections
        if isinstance(section.get("models"), list)
        for model in section["models"]
        if isinstance(model, str)
    }
    lines = render_frontmatter(
        {
            "type": "daily-note",
            "date": date,
            "projects": sorted(projects),
            "agents": sorted(
                {
                    agent_label(source)
                    for section in sections
                    if isinstance((source := section.get("source")), str)
                    and source.lower() != "git"
                }
            ),
            "models": sorted(models),
            "commits": len(commits),
            "tags": sorted(
                {
                    term
                    for section in sections
                    if isinstance(section.get("terms"), list)
                    for term in section["terms"]
                    if isinstance(term, str)
                }
            ),
            "generated_by": "autograph",
        }
    ) + [
        "",
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
            models = model_list(section.get("models"))
            if models:
                lines.extend(["", f"**Models:** {models}"])
            session_link = session_note_link(source, section.get("session_id"))
            if session_link:
                lines.extend(["", f"**Session:** {session_link}"])
        wiki_pages = section.get("wiki_pages")
        if isinstance(wiki_pages, list) and wiki_pages:
            links = [
                f"[[{target}|{_clean_link_text(title)}]]" for target, title in wiki_pages
            ]
            lines.extend(["", "**Related wiki:** " + ", ".join(links)])

    related_links = [daily_note_link(related_date) for related_date in related_dates]
    if related_links:
        lines.extend(["", "## Related notes"])
        lines.extend(f"- {link}" for link in related_links)

    if graph_connections:
        lines.extend(["", graph_connections])
    lines.extend(["", "---", "*Generated by Autograph Agent*"])
    return "\n".join(lines) + "\n"


FRONTMATTER_BLOCK = re.compile(r"\A---\n.*?\n---\n\n?", re.S)
PROJECT_LINK = re.compile(r"\*\*Related project:\*\* \[\[projects/[^|\]]+\|([^\]]+)\]\]")
COMMIT_LINK = re.compile(r"\[\[projects/([^/|\]]+)/commits/([A-Za-z0-9]+)\|")
AGENT_LINK = re.compile(r"\[\[agents/[^|\]]+\|([^\]]+)\]\]")
SECTION_METADATA = ("**Related ", "**Agent source:**", "**Models:**", "**Session:**")


def retrofit_daily_note(content: str, date: str, annotate) -> str:
    """Give an existing generated note the properties and wiki links of a new one.

    Everything is read back from the note itself, so old days whose sessions
    are no longer on disk need no regeneration and no model call. `annotate`
    is `ConceptIndex.annotate`. Prior Autograph frontmatter and **Related wiki**
    lines are replaced, so a rerun after a vocabulary edit refreshes them.
    """
    existing = FRONTMATTER_BLOCK.match(content)
    if existing:
        if 'generated_by: "autograph"' not in existing.group(0):
            raise ValueError("Daily note has frontmatter Autograph did not write")
        content = content[existing.end():]

    lines = [line for line in content.split("\n") if not line.startswith("**Related wiki:**")]
    output: List[str] = []
    tags = set()
    index = 0
    while index < len(lines):
        if not lines[index].startswith("### "):
            output.append(lines[index])
            index += 1
            continue
        end = index + 1
        while end < len(lines) and not lines[end].startswith(("### ", "## ")):
            end += 1
        body = lines[index:end]
        while len(body) > 1 and not body[-1].strip():
            body.pop()
        prose = []
        for line in body[1:]:
            if line.startswith(SECTION_METADATA):
                break
            if not (line.startswith("**") and line.endswith("**")):
                prose.append(line)
        section: Dict[str, Any] = {"title": body[0][4:], "work_done": " ".join(prose)}
        annotate(section)
        tags.update(section["terms"])
        output.extend(body)
        if section["wiki_pages"]:
            links = [
                f"[[{target}|{_clean_link_text(title)}]]"
                for target, title in section["wiki_pages"]
            ]
            output.extend(["", "**Related wiki:** " + ", ".join(links)])
        output.append("")
        index = end
    body_text = "\n".join(output)

    agents = {
        match
        for line in body_text.split("\n")
        if line.startswith("**Agent source:**")
        for match in AGENT_LINK.findall(line)
    }
    if not agents:
        # Notes from before per-section agent lines name them only here, next
        # to Ollama, which every note lists as its synthesizer.
        agents = {
            match
            for line in body_text.split("\n")
            if line.startswith("- **Agents:**")
            for match in AGENT_LINK.findall(line)
            if match != "Ollama"
        }
    commits = COMMIT_LINK.findall(body_text)
    projects = set(PROJECT_LINK.findall(body_text))
    projects.update(project for project, _ in commits)
    models = {
        model
        for line in body_text.split("\n")
        if line.startswith("**Models:**")
        for model in re.findall(r"`([^`]+)`", line)
    }
    frontmatter = render_frontmatter(
        {
            "type": "daily-note",
            "date": date,
            "projects": sorted(projects),
            "agents": sorted(agents),
            "models": sorted(models),
            "commits": len({commit_id for _, commit_id in commits}),
            "tags": sorted(tags),
            "generated_by": "autograph",
        }
    )
    return "\n".join(frontmatter) + "\n\n" + body_text


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
