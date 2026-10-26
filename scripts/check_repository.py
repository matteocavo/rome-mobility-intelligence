"""Small tracked-file secret / artifact checks, also run in CI."""

import re
import subprocess
from pathlib import Path


def main():
    paths = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    patterns = [
        r"dapi[a-f0-9]{20,}",
        r"gh[pousr]_[A-Za-z0-9]{20,}",
        r"AKIA[A-Z0-9]{16}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    ]
    for name in paths:
        p = Path(name)
        if name == ".env" or (name.startswith("artifacts/") and name != "artifacts/.gitkeep"):
            raise ValueError(f"Forbidden tracked file: {name}")
        if p.suffix in {".joblib", ".parquet", ".arrow", ".csv"}:
            raise ValueError(f"Runtime data/artifact cannot be tracked: {name}")
        content = p.read_text(encoding="utf-8")
        if any(re.search(pattern, content) for pattern in patterns):
            raise ValueError(f"Potential secret in {name}")
        if p.suffix == ".md":
            for link in re.findall(r"\]\(([^)]+)\)", content):
                if "://" not in link and not link.startswith("#"):
                    target = link.split("#")[0]
                    if target and not (p.parent / target).exists():
                        raise ValueError(f"Broken relative link: {name}: {link}")
    print(
        f"UTF-8, relative links, secret patterns and tracked-file checks PASS ({len(paths)} files)"
    )


if __name__ == "__main__":
    main()
