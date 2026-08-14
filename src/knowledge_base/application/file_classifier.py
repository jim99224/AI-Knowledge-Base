from __future__ import annotations

from pathlib import PurePosixPath


class FileClassifier:
    """Allow known text inputs and reject generated or binary-like paths."""

    MARKDOWN_SUFFIXES = {".md", ".markdown"}
    TEXT_SUFFIXES = {
        ".txt",
        ".rst",
        ".py",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".sql",
        ".tpl",
    }
    EXCLUDED_PARTS = {
        ".git",
        ".venv",
        "node_modules",
        "vendor",
        "dist",
        "build",
        "__pycache__",
    }

    def classify(self, path: str) -> str | None:
        file_path = PurePosixPath(path)
        if any(part in self.EXCLUDED_PARTS for part in file_path.parts):
            return None
        name = file_path.name.lower()
        if name == "readme":
            return "markdown"
        if name == "dockerfile" or name.startswith("dockerfile."):
            return "plain_text"
        if file_path.suffix.lower() in self.MARKDOWN_SUFFIXES:
            return "markdown"
        if file_path.suffix.lower() in self.TEXT_SUFFIXES:
            return "plain_text"
        return None
