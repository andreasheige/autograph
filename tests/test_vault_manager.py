import pytest
from pathlib import Path
import os
from src.core.vault import VaultManager
from config.settings import Config

@pytest.fixture
def temp_vault(tmp_path):
    """Creates a temporary vault for testing."""
    return VaultManager(vault_root=tmp_path)

def test_entity_string_extraction(temp_vault):
    """Verifies that the entity extractor handles different types correctly."""
    assert temp_vault._extract_entity_string("Button") == "Button"
    assert temp_vault._extract_entity_string({"name": "Toast"}) == "Toast"
    assert temp_vault._extract_entity_string({"id": "123"}) == "123"
    assert temp_vault._extract_entity_string(42) == "42"

def test_write_event_creates_file(temp_vault, tmp_path):
    """Verifies that write_event actually creates a markdown file."""
    project_name = "TestProject"
    message = "Test Commit Message"
    data = {"entities": ["Entity1", {"name": "Entity2"}], "summary": "something happened"}
    
    temp_vault.write_event(project_name, message, data)
    
    # Check if the event directory exists
    event_dir = temp_vault.vault_root / "projects" / "TestProject" / "events"
    assert event_dir.exists()
    
    # Check if at least one .md file was created
    md_files = list(event_dir.glob("*.md"))
    assert len(md_files) == 1
    
    # Check if the content contains the message
    with open(md_files[0], 'r') as f:
        content = f.read()
        assert message in content
        assert "Entity1" in content
        assert "Entity2" in content

def test_find_all_git_roots_empty(temp_vault, tmp_path):
    """Verifies that searching an empty directory returns nothing."""
    # Using a temp directory with no git
    roots = temp_vault.find_all_git_roots(tmp_path)
    assert len(roots) == 0
