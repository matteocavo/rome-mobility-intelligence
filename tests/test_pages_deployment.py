"""Pages deployment cannot publish a feature branch or leak backend build inputs."""

import re
from pathlib import Path

WORKFLOW = Path(".github/workflows/pages.yml").read_text()


def test_pages_only_main_and_explicit_dispatch_with_job_level_ref_guards():
    assert re.search(
        r"(?m)^on:\n  push:\n    branches: \[main\]\n  workflow_dispatch:\s*$", WORKFLOW
    )
    assert re.search(r"(?m)^permissions: \{\}\s*$", WORKFLOW)
    assert WORKFLOW.count("if: github.ref == 'refs/heads/main'") == 2
    assert re.search(r"(?m)^    needs: build\s*$", WORKFLOW)
    assert re.search(r"(?m)^      name: github-pages\s*$", WORKFLOW)


def test_pages_build_and_deploy_permissions_are_separate_and_minimal():
    assert re.search(r"(?ms)^    permissions:\n      contents: read\n      pages: read\n", WORKFLOW)
    assert re.search(
        r"(?ms)^    permissions:\n      pages: write\n      id-token: write\n", WORKFLOW
    )
    assert re.search(
        r"(?m)^      VITE_PUBLIC_API_URL: "
        r"https://rome-mobility-intelligence-matteocavo\.onrender\.com\s*$",
        WORKFLOW,
    )
    runs = re.findall(r"(?m)^      - run: (.+)$", WORKFLOW)
    assert runs == ["npm ci", "npm run lint", "npm run typecheck", "npm test", "npm run build"]
    assert re.search(
        r"(?ms)^      - uses: actions/upload-pages-artifact@[a-f0-9]{40}[^\n]*\n"
        r"        with:\n          path: frontend/dist$",
        WORKFLOW,
    )
    for action in re.findall(r"(?m)^      - uses: ([^\s]+)", WORKFLOW):
        assert re.fullmatch(r"actions/[a-z-]+@[a-f0-9]{40}", action)
    assert "secrets." not in WORKFLOW and "pull_request_target" not in WORKFLOW
