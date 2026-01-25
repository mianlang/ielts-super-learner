#!/usr/bin/env python3
"""Validate that references in CLAUDE.md still exist in the codebase."""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"

# Patterns to check: (regex, file_path_hint, description)
CHECKS = [
    (r"get_llm\(\)", "ielts_agent/llm/client.py", "LLM client function"),
    (r"get_llm_for_scoring\(\)", "ielts_agent/llm/client.py", "Scoring LLM function"),
    (r"init_db\(\)", "ielts_agent/db/schema.py", "Database init function"),
    (r"update_progress\(", "ielts_agent/db/schema.py", "Progress update function"),
    (r"python -m ielts_agent", "ielts_agent/main.py", "CLI entry point"),
]


def check_file_exists(filepath: str) -> bool:
    """Check if a file exists relative to project root."""
    return (PROJECT_ROOT / filepath).exists()


def check_function_exists(filepath: str, pattern: str) -> bool:
    """Check if a pattern exists in a file."""
    full_path = PROJECT_ROOT / filepath
    if not full_path.exists():
        return False
    content = full_path.read_text()
    return bool(re.search(pattern, content))


def main():
    content = CLAUDE_MD.read_text()
    issues = []

    for pattern, filepath, desc in CHECKS:
        # Check referenced in CLAUDE.md
        if pattern not in content and not any(p in content for p in [pattern.replace("\\", ""), pattern]):
            issues.append(f"Warning: '{desc}' not mentioned in CLAUDE.md")

        # Check actually exists in codebase
        if not check_file_exists(filepath):
            issues.append(f"Error: Referenced file '{filepath}' does not exist")
        elif "def " in pattern or pattern.startswith("python "):
            # For functions, check if pattern exists in file
            func_pattern = pattern.replace("(", r"\(").replace(")", r"\)")
            if not check_function_exists(filepath, func_pattern.replace(r"\(", "").replace(r"\)", "")):
                # Try looser check
                if not check_function_exists(filepath, pattern.split("(")[0]):
                    issues.append(f"Warning: '{desc}' ({filepath}) may not exist")

    if issues:
        print("CLAUDE.md validation issues:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print("CLAUDE.md: All references validated")
        return 0


if __name__ == "__main__":
    exit(main())
