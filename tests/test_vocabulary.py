from src.core.vocabulary import ConceptIndex, append_proposals, parse_vocabulary, sort_tags

VOCABULARY = """# Vocabulary

- [x] bff; alt: backend-for-frontend  <!-- 11 -->
- [x] entra
- [X] kubernetes; alt: k8s; broader: containers
- [x] design-system
- [x] design
- [ ] deployment
- [x] skill; alt: skills
- [x] setup; match: no
"""


def page(title, tags):
    return f'---\ntitle: "{title}"\ntype: concept\ntags: [{", ".join(tags)}]\n---\n\nBody.\n'


def write_vault(tmp_path):
    (tmp_path / "vocabulary.md").write_text(VOCABULARY, encoding="utf-8")
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "bff-login.md").write_text(
        page("BFF Entra login", ["entra", "bff", "kubernetes", "deployment"]), encoding="utf-8"
    )
    (concepts / "bff-mocks.md").write_text(page("BFF mocks", ["backend-for-frontend", "msw"]), encoding="utf-8")
    entities = tmp_path / "wiki" / "entities"
    entities.mkdir()
    (entities / "aks.md").write_text(page("AKS", ["k8s", "entra"]), encoding="utf-8")


def test_parse_vocabulary_reads_only_ticked_lines():
    labels = parse_vocabulary(VOCABULARY)

    assert labels["backend-for-frontend"] == "bff"
    assert labels["k8s"] == "kubernetes"
    assert labels["skills"] == "skill"
    assert "deployment" not in labels
    assert "containers" not in labels
    assert "setup" not in labels


def test_terms_match_whole_words_alt_labels_and_spaced_hyphens(tmp_path):
    write_vault(tmp_path)
    index = ConceptIndex.load(tmp_path)

    assert index.terms("Deployed the Backend-for-Frontend to K8s via Entra.") == {
        "bff", "kubernetes", "entra"
    }
    assert index.terms("Aligned the design system tokens.") == {"design-system"}
    assert index.terms("bffs, sub-entra, skillset and deployment") == set()


def test_annotate_links_pages_sharing_at_least_two_terms(tmp_path):
    write_vault(tmp_path)
    index = ConceptIndex.load(tmp_path)
    section = {
        "title": "BFF login",
        "work_done": "Fixed the Entra redirect on the Kubernetes cluster.",
        "learned": None,
    }

    index.annotate(section)

    assert section["terms"] == ["bff", "entra", "kubernetes"]
    assert section["wiki_pages"] == [
        ("wiki/concepts/bff-login", "BFF Entra login"),
        ("wiki/entities/aks", "AKS"),
    ]


def test_missing_vocabulary_adds_no_terms_or_links(tmp_path):
    section = {"title": "BFF", "work_done": "Entra and Kubernetes."}

    ConceptIndex.load(tmp_path).annotate(section)

    assert section == {
        "title": "BFF", "work_done": "Entra and Kubernetes.", "terms": [], "wiki_pages": []
    }


def test_retired_and_unticked_lines_never_match():
    labels = parse_vocabulary(
        "- [x] hooks; retired: collides with React hooks; use: claude-code-hooks\n"
        "- [ ] clientco; alt: client-alt; scheme: local; def: A client\n"
        "- [x] claude-code-hooks; scheme: claude-code; def: Hooks\n"
    )

    assert labels == {"claude-code-hooks": "claude-code-hooks"}


def test_sort_tags_accepts_ticked_terms_and_proposes_the_rest():
    text = (
        "- [x] software-testing; alt: testing; scheme: swebok KA05; def: Testing\n"
        "- [x] hooks; retired: too generic\n"
        "- [ ] clientco; alt: client-alt; scheme: local; def: A client\n"
    )

    assert sort_tags(["testing", "software-testing", "hooks", "client-alt", "new-thing"], text) == (
        ["software-testing"],
        ["client-alt", "new-thing"],
        ["new-thing"],
    )


def test_append_proposals_adds_the_heading_once(tmp_path):
    vocabulary = tmp_path / "vocabulary.md"
    vocabulary.write_text("# Vocabulary\n", encoding="utf-8")

    append_proposals(vocabulary, ["a-term"], "proposed by x")
    append_proposals(vocabulary, ["b-term"], "proposed by y")
    append_proposals(vocabulary, [], "nothing")

    assert vocabulary.read_text(encoding="utf-8") == (
        "# Vocabulary\n\n## Proposed by captures\n"
        "- [ ] a-term  <!-- proposed by x -->\n"
        "- [ ] b-term  <!-- proposed by y -->\n"
    )
