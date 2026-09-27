"""Fill release markers in README.md with each repository's latest release.

A marker looks like `<!-- release:Thakay/sako -->...<!-- /release -->`; the text
between the comments is replaced with a link to the latest release and its date.
Runs daily in .github/workflows/profile-cards.yml; needs `gh` and GH_TOKEN.
"""
import datetime as dt
import json
import pathlib
import re
import subprocess

README = pathlib.Path(__file__).parent.parent / "README.md"
MARKER = re.compile(r"(<!-- release:([\w.-]+/[\w.-]+) -->).*?(<!-- /release -->)", re.S)


def latest(repo):
    out = subprocess.run(["gh", "api", f"repos/{repo}/releases/latest"], capture_output=True, text=True)
    if out.returncode:
        return None
    release = json.loads(out.stdout)
    day = dt.date.fromisoformat(release["published_at"][:10])
    return f'[{release["tag_name"]}]({release["html_url"]}), {day.strftime("%b %d, %Y").replace(" 0", " ")}'


def main():
    text = README.read_text(encoding="utf-8")

    def fill(m):
        found = latest(m.group(2))
        return f"{m.group(1)}{found}{m.group(3)}" if found else m.group(0)

    README.write_text(MARKER.sub(fill, text), encoding="utf-8")


if __name__ == "__main__":
    main()
