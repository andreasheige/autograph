from src.core.vocabulary import ConceptIndex, parse_vocabulary

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
