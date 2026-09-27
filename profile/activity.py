"""Build the "Recent activity" card for the profile README.

Draws daily contributions for the last 90 days and where those contributions
went, as light and dark SVGs in this folder. Runs daily in
.github/workflows/profile-cards.yml; needs the GitHub CLI (`gh`) and a token in
GH_TOKEN.

Private repositories never appear by name. Contributions the token cannot see
(and private repositories without an area topic) are counted as "Private work".
A repository with a topic such as `area-agent-tooling` is counted under that
area ("Agent tooling") instead of its own name.
"""
import datetime as dt
import html
import json
import os
import pathlib
import subprocess

USER = os.environ.get("PROFILE_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Thakay"
OUT = pathlib.Path(__file__).parent
DAYS, MAX_ROWS = 90, 5
PRIVATE = "Private work"
ACRONYMS = {"ai": "AI", "llm": "LLM", "ml": "ML", "api": "API", "cli": "CLI", "devops": "DevOps", "mlops": "MLOps"}

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
      restrictedContributionsCount
      commits: commitContributionsByRepository(maxRepositories: 50) { contributions { totalCount } repository { ...Repo } }
      issues: issueContributionsByRepository(maxRepositories: 50) { contributions { totalCount } repository { ...Repo } }
      prs: pullRequestContributionsByRepository(maxRepositories: 50) { contributions { totalCount } repository { ...Repo } }
      reviews: pullRequestReviewContributionsByRepository(maxRepositories: 50) { contributions { totalCount } repository { ...Repo } }
    }
  }
}
fragment Repo on Repository { name isPrivate repositoryTopics(first: 20) { nodes { topic { name } } } }
"""

THEMES = {
    "dark": dict(bg=("#0b0f17", "#101829"), border="#30363d", title="#e6edf3", muted="#9198a1",
                 track="#21262d", stub="#30363d", accent=("#a78bfa", "#22d3ee"), glow="#7c3aed", glow_op=0.28),
    "light": dict(bg=("#ffffff", "#f6f8fa"), border="#d0d7de", title="#1f2328", muted="#59636e",
                  track="#eaeef2", stub="#d0d7de", accent=("#7c3aed", "#0891b2"), glow="#8b5cf6", glow_op=0.12),
}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"


def fetch(start, now):
    variables = {"login": USER, "from": f"{start.isoformat()}T00:00:00Z", "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    body = json.dumps({"query": QUERY, "variables": variables})
    out = subprocess.run(["gh", "api", "graphql", "--input", "-"], input=body.encode(), capture_output=True)
    if out.returncode:
        raise SystemExit(f"gh api graphql failed: {out.stderr.decode()} {out.stdout.decode()}")
    data = json.loads(out.stdout)
    if data.get("errors"):
        raise SystemExit(f"GraphQL errors: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]


def area_label(topic):
    label = " ".join(ACRONYMS.get(w, w) for w in topic.removeprefix("area-").split("-"))
    return label[:1].upper() + label[1:]


def bucket(repo):
    topics = [n["topic"]["name"] for n in repo["repositoryTopics"]["nodes"]]
    area = next((t for t in topics if t.startswith("area-")), None)
    if area:
        return area_label(area)
    return PRIVATE if repo["isPrivate"] else repo["name"]


def summarize(collection, start):
    days = [(dt.date.fromisoformat(d["date"]), d["contributionCount"])
            for w in collection["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    days = [(day, n) for day, n in days if day >= start]
    counts = {}
    for kind in ("commits", "issues", "prs", "reviews"):
        for item in collection[kind]:
            key = bucket(item["repository"])
            counts[key] = counts.get(key, 0) + item["contributions"]["totalCount"]
    if collection["restrictedContributionsCount"]:
        counts[PRIVATE] = counts.get(PRIVATE, 0) + collection["restrictedContributionsCount"]
    rows = sorted(counts.items(), key=lambda kv: -kv[1])
    if len(rows) > MAX_ROWS:
        rows = rows[:MAX_ROWS - 1] + [("Other", sum(v for _, v in rows[MAX_ROWS - 1:]))]
    values = [n for _, n in days]
    return dict(days=days, rows=rows, total=sum(values),
                active_days=sum(1 for n in values if n), busiest=max(values, default=0))


def pct(value, total):
    share = 100 * value / total if total else 0
    return "<1%" if 0 < share < 1 else f"{share:.0f}%"


def render(s, theme, now):
    t, e = THEMES[theme], html.escape
    w, h, pad = 900, 380, 32
    chart_x, chart_w, chart_top, chart_h = pad, 488, 150, 150
    base = chart_top + chart_h
    step = chart_w / max(len(s["days"]), 1)
    bar_w = step * 0.72
    top = max(s["busiest"], 1)

    bars, labels, last_label_x = [], [], -100.0
    for i, (day, value) in enumerate(s["days"]):
        x = chart_x + i * step
        if value:
            bh = max(3.0, chart_h * value / top)
            bars.append(f'<rect x="{x:.1f}" y="{base - bh:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="1.5" fill="url(#bar)">'
                        f'<title>{day.strftime("%b %d")}: {value}</title></rect>')
        else:
            bars.append(f'<rect x="{x:.1f}" y="{base - 2:.1f}" width="{bar_w:.1f}" height="2" rx="1" fill="{t["stub"]}"/>')
        if (day.day == 1 or (i == 0 and day.day <= 22)) and x - last_label_x > 30:
            labels.append(f'<text x="{x:.1f}" y="{base + 24}" font-size="13" fill="{t["muted"]}">{day.strftime("%b")}</text>')
            last_label_x = x

    rows, panel_x = [], 568
    panel_w = w - panel_x - pad
    recent_total = sum(v for _, v in s["rows"])
    for j, (name, value) in enumerate(s["rows"]):
        y = 188 + j * 40
        fill = max(4.0, panel_w * value / recent_total)
        rows.append(
            f'<text x="{panel_x}" y="{y}" font-size="14" fill="{t["title"]}">{e(name)}</text>'
            f'<text x="{panel_x + panel_w}" y="{y}" font-size="14" fill="{t["muted"]}" text-anchor="end">{e(f"{value} · {pct(value, recent_total)}")}</text>'
            f'<rect x="{panel_x}" y="{y + 9}" width="{panel_w}" height="8" rx="4" fill="{t["track"]}"/>'
            f'<rect x="{panel_x}" y="{y + 9}" width="{fill:.1f}" height="8" rx="4" fill="url(#accentH)"/>'
        )
    if not rows:
        rows.append(f'<text x="{panel_x}" y="188" font-size="14" fill="{t["muted"]}">No contributions yet</text>')

    stats = [(s["total"], "contributions"), (s["active_days"], "active days"), (s["busiest"], "on the busiest day")]
    stat_svg = "".join(
        f'<text x="{pad + k * 170}" y="104" font-size="26" font-weight="700" fill="{t["title"]}">{v:,}</text>'
        f'<text x="{pad + k * 170}" y="126" font-size="13" fill="{t["muted"]}">{e(label)}</text>'
        for k, (v, label) in enumerate(stats)
    )
    where = ", ".join(f"{n} {v}" for n, v in s["rows"]) or "none"
    desc = f"{s['total']} contributions in the last {DAYS} days across {s['active_days']} active days. By repository: {where}."
    updated = now.strftime("%b %d, %Y").replace(" 0", " ")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t d">
  <title id="t">Recent GitHub activity for {e(USER)}</title>
  <desc id="d">{e(desc)}</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['bg'][0]}"/><stop offset="1" stop-color="{t['bg'][1]}"/></linearGradient>
    <radialGradient id="glow" cx="0.9" cy="0.1" r="0.6"><stop offset="0" stop-color="{t['glow']}" stop-opacity="{t['glow_op']}"/><stop offset="1" stop-color="{t['glow']}" stop-opacity="0"/></radialGradient>
    <linearGradient id="bar" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{t['accent'][0]}"/><stop offset="1" stop-color="{t['accent'][1]}"/></linearGradient>
    <linearGradient id="accentH" gradientUnits="userSpaceOnUse" x1="{panel_x}" y1="0" x2="{panel_x + panel_w}" y2="0"><stop offset="0" stop-color="{t['accent'][0]}"/><stop offset="1" stop-color="{t['accent'][1]}"/></linearGradient>
    <clipPath id="card"><rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14"/></clipPath>
  </defs>
  <g clip-path="url(#card)">
    <rect width="{w}" height="{h}" fill="url(#bg)"/>
    <rect width="{w}" height="{h}" fill="url(#glow)"/>
  </g>
  <rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{t['border']}"/>
  <g font-family="{FONT}">
    <text x="{pad}" y="52" font-size="20" font-weight="700" fill="{t['title']}">Recent activity</text>
    <text x="{w - pad}" y="52" font-size="13" fill="{t['muted']}" text-anchor="end">Last {DAYS} days · updated {updated}</text>
    {stat_svg}
    {''.join(bars)}
    {''.join(labels)}
    <text x="{panel_x}" y="150" font-size="14" font-weight="700" fill="{t['title']}">Where it went</text>
    {''.join(rows)}
    <text x="{pad}" y="{h - 22}" font-size="12" fill="{t['muted']}">Daily contributions, including private ones. Generated daily by GitHub Actions.</text>
  </g>
</svg>
"""


def main():
    now = dt.datetime.now(dt.timezone.utc)
    start = now.date() - dt.timedelta(days=DAYS - 1)
    summary = summarize(fetch(start, now), start)
    for theme in THEMES:
        (OUT / f"activity-{theme}.svg").write_text(render(summary, theme, now), encoding="utf-8")
    print(f"days={len(summary['days'])} total={summary['total']} rows={summary['rows']}")


if __name__ == "__main__":
    main()
