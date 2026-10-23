"""Match daily-note sections to the vault's controlled vocabulary and wiki pages.

`vocabulary.md` at the vault root is human-owned, and only its ticked lines
count, so nothing here invents a term. No model is involved: terms are matched
as whole words, and a wiki page is related when it shares enough terms.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# "- [x] term; alt: a, b; broader: parent", optionally followed by "<!-- n -->".
TERM_PATTERN = re.compile(r"^- \[[xX]\] ([a-z0-9-]+)((?:;[^;<]*)*)")
FRONTMATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n", re.S)
WIKI_PAGE_FOLDERS = ("concepts", "entities")
MIN_SHARED_TERMS = 2
MAX_PAGES_PER_SECTION = 3


def parse_vocabulary(text: str) -> Dict[str, str]:
    """Map every ticked, matchable term and alt label to its preferred term.

    `match: no` keeps a term valid as a wiki tag but out of prose matching, for
    common words ("setup", "process") that would otherwise tag every day.
    """
    labels = {}
    for line in text.splitlines():
        match = TERM_PATTERN.match(line)
        if not match:
            continue
        fields = {}
        for part in match.group(2).split(";"):
            key, _, value = part.partition(":")
            fields[key.strip()] = value.strip()
        if fields.get("match") == "no":
            continue
        term = match.group(1)
        labels[term] = term
        for label in fields.get("alt", "").split(","):
            if label.strip():
                labels[label.strip().lower()] = term
    return labels


def _frontmatter(text: str) -> Dict[str, object]:
    match = FRONTMATTER_PATTERN.match(text)
    meta: Dict[str, object] = {}
    if not match:
        return meta
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if not sep or line.startswith(" "):
            continue
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key.strip()] = [
                item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()
            ]
        else:
            meta[key.strip()] = value.strip("'\"")
    return meta


class ConceptIndex:
    """Ticked vocabulary terms plus the wiki pages tagged with them."""

    def __init__(self, labels: Dict[str, str], pages: List[Tuple[str, str, Set[str]]]):
        self.labels = labels
        self.pages = pages
        self.pattern: Optional[re.Pattern] = None
        if labels:
            # Longest first, so "design-system" wins over "design"; a hyphen in
            # a term also matches the space prose would use instead.
            alternatives = [
                re.escape(label).replace(r"\-", r"[-\s]")
                for label in sorted(labels, key=len, reverse=True)
            ]
            self.pattern = re.compile(
                r"(?<![\w-])(" + "|".join(alternatives) + r")(?![\w-])", re.I
            )

    @classmethod
    def load(cls, vault_root: Path) -> "ConceptIndex":
        vocabulary = Path(vault_root) / "vocabulary.md"
        if not vocabulary.is_file():
            return cls({}, [])
        labels = parse_vocabulary(vocabulary.read_text(encoding="utf-8", errors="replace"))
        pages = []
        for folder in WIKI_PAGE_FOLDERS:
            for page in sorted((Path(vault_root) / "wiki" / folder).glob("*.md")):
                meta = _frontmatter(page.read_text(encoding="utf-8", errors="replace"))
                tags = meta.get("tags")
                if not isinstance(tags, list):
                    continue
                terms = {labels[tag.lower()] for tag in tags if tag.lower() in labels}
                if terms:
                    title = str(meta.get("title") or page.stem)
                    pages.append((f"wiki/{folder}/{page.stem}", title, terms))
        return cls(labels, pages)

    def terms(self, text: str) -> Set[str]:
        if self.pattern is None:
            return set()
        labels = (re.sub(r"\s+", "-", match.lower()) for match in self.pattern.findall(text))
        return {self.labels[label] for label in labels if label in self.labels}

    def related_pages(self, terms: Set[str]) -> List[Tuple[str, str]]:
        scored = [
            (len(terms & page_terms), target, title)
            for target, title, page_terms in self.pages
            if len(terms & page_terms) >= MIN_SHARED_TERMS
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [(target, title) for _, target, title in scored[:MAX_PAGES_PER_SECTION]]

    def annotate(self, section: Dict[str, object]) -> None:
        """Add matched `terms` and `wiki_pages` to a synthesized section."""
        text = " ".join(
            str(section.get(key) or "")
            for key in ("title", "work_done", "went_well", "learned", "remember")
        )
        terms = self.terms(text)
        section["terms"] = sorted(terms)
        section["wiki_pages"] = self.related_pages(terms)
