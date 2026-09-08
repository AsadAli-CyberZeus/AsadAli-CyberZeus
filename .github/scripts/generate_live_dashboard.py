import json
import os
import urllib.error
import urllib.parse
import urllib.request
from html import escape
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "AsadAliEngineer")
TOKEN = os.environ.get("DASHBOARD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DASHBOARD_TOKEN is required. Configure METRICS_TOKEN with repo access."
    )

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "github-profile-private-aware-dashboard",
    "X-GitHub-Api-Version": "2022-11-28",
}


def github(path):
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers=HEADERS,
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {error.code} for {path}: {body}") from error


def owned_repositories():
    repositories = []
    page = 1
    while True:
        batch = github(
            "/user/repos?affiliation=owner&visibility=all"
            f"&sort=updated&per_page=100&page={page}"
        )
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories
        page += 1


viewer = github("/user")
if viewer["login"].lower() != USERNAME.lower():
    raise RuntimeError(
        f"DASHBOARD_TOKEN belongs to {viewer['login']}, expected {USERNAME}."
    )

repositories = owned_repositories()
public_count = sum(not repository["private"] for repository in repositories)
private_count = sum(repository["private"] for repository in repositories)

language_repository_counts = {}
language_byte_totals = {}

for repository in repositories:
    if repository["fork"] or repository["name"].lower() == USERNAME.lower():
        continue

    languages = github(
        f"/repos/{repository['owner']['login']}/{repository['name']}/languages"
    )
    for language, byte_count in languages.items():
        language_repository_counts[language] = (
            language_repository_counts.get(language, 0) + 1
        )
        language_byte_totals[language] = (
            language_byte_totals.get(language, 0) + byte_count
        )

top_languages = sorted(
    language_repository_counts.items(),
    key=lambda item: (
        item[1],
        language_byte_totals.get(item[0], 0),
        item[0].lower(),
    ),
    reverse=True,
)[:10]

language_colors = {
    "Python": "#3572A5",
    "Jupyter Notebook": "#DA5B0B",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "Rust": "#dea584",
    "Dart": "#00B4AB",
    "CSS": "#563d7c",
    "Shell": "#89e051",
    "Solidity": "#AA6746",
    "C++": "#f34b7d",
    "C": "#555555",
    "Java": "#b07219",
    "Go": "#00ADD8",
    "MDX": "#fcb32c",
}
fallback_colors = ["#58a6ff", "#3fb950", "#d29922", "#bc8cff", "#f778ba"]

stats = [
    ("Owned repositories", len(repositories)),
    ("Public repositories", public_count),
    ("Private repositories", private_count),
    ("Languages detected", len(language_repository_counts)),
]

stat_cards = []
for index, (label, value) in enumerate(stats):
    x = 30 + index * 210
    stat_cards.append(
        f"""
      <g transform="translate({x} 104)">
        <rect width="195" height="82" rx="11" fill="#0b1320" stroke="#30363d" />
        <text x="18" y="37" class="metric">{value}</text>
        <text x="18" y="62" class="label">{escape(label)}</text>
      </g>"""
    )

max_repository_coverage = max(
    (repository_count for _, repository_count in top_languages), default=1
)
language_rows = []

for index, (language, repository_count) in enumerate(top_languages):
    column = 1 if index >= 5 else 0
    row = index % 5
    x = 52 + column * 410
    y = 246 + row * 38
    bar_width = max(4, (repository_count / max_repository_coverage) * 310)
    color = language_colors.get(
        language, fallback_colors[index % len(fallback_colors)]
    )
    repo_label = "repo" if repository_count == 1 else "repos"
    language_rows.append(
        f"""
      <g transform="translate({x} {y})">
        <circle cx="5" cy="-5" r="5" fill="{color}" />
        <text x="18" y="0" class="language">{escape(language)}</text>
        <text x="350" y="0" text-anchor="end" class="coverage">{repository_count} {repo_label}</text>
        <rect x="18" y="10" width="332" height="7" rx="3.5" fill="#21262d" />
        <rect x="18" y="10" width="{bar_width:.1f}" height="7" rx="3.5" fill="{color}" />
      </g>"""
    )

core_stack = [
    ("Python", "#3572A5"),
    ("Rust", "#dea584"),
    ("TypeScript", "#3178c6"),
    ("JavaScript", "#f1e05a"),
    ("React", "#61dafb"),
    ("Node.js", "#5fa04e"),
]
stack_chips = []
for index, (technology, color) in enumerate(core_stack):
    x = 42 + index * 139
    text_color = "#0d1117" if technology in {"JavaScript", "React"} else "#f0f6fc"
    stack_chips.append(
        f"""
      <g transform="translate({x} 494)">
        <rect width="126" height="38" rx="19" fill="{color}" fill-opacity="0.92" />
        <text x="63" y="25" text-anchor="middle" fill="{text_color}" class="stack">{escape(technology)}</text>
      </g>"""
    )

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="560" viewBox="0 0 900 560" role="img" aria-labelledby="title desc">
  <title id="title">{escape(USERNAME)} private-aware engineering profile</title>
  <desc id="desc">Owned public and private repository counts, language coverage, and core engineering stack generated from the official GitHub API.</desc>
  <defs>
    <linearGradient id="panel" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0d1117" />
      <stop offset="1" stop-color="#0a1220" />
    </linearGradient>
    <style>
      text {{ font-family: Inter, "Segoe UI", Arial, sans-serif; }}
      .title {{ fill: #f0f6fc; font-size: 25px; font-weight: 700; }}
      .subtitle {{ fill: #8b949e; font-size: 13px; }}
      .section {{ fill: #f0f6fc; font-size: 17px; font-weight: 650; }}
      .metric {{ fill: #58a6ff; font-size: 28px; font-weight: 750; }}
      .label {{ fill: #9da7b3; font-size: 12px; }}
      .language {{ fill: #c9d1d9; font-size: 13px; font-weight: 600; }}
      .coverage {{ fill: #9da7b3; font-size: 11px; }}
      .stack {{ font-size: 13px; font-weight: 700; }}
    </style>
  </defs>

  <rect x="1" y="1" width="898" height="558" rx="16" fill="url(#panel)" stroke="#30363d" stroke-width="2" />
  <circle cx="38" cy="41" r="8" fill="#3fb950" />
  <text x="58" y="49" class="title">Repository &amp; Technology Signal</text>
  <text x="58" y="74" class="subtitle">@{escape(USERNAME)} · private-aware · generated from the official GitHub API</text>

{''.join(stat_cards)}

  <rect x="30" y="208" width="840" height="230" rx="12" fill="#0b1320" stroke="#30363d" />
  <text x="52" y="232" class="section">Language coverage across public + private repositories · top {len(top_languages)}</text>
{''.join(language_rows)}

  <text x="42" y="475" class="section">Core Stack</text>
{''.join(stack_chips)}
</svg>
"""

output = Path("assets/live-engineering-signal.svg")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(svg, encoding="utf-8")

print(
    json.dumps(
        {
            "username": USERNAME,
            "ownedRepositories": len(repositories),
            "publicRepositories": public_count,
            "privateRepositories": private_count,
            "languagesDetected": len(language_repository_counts),
            "topLanguages": [
                {"name": language, "repositories": count}
                for language, count in top_languages
            ],
            "output": str(output),
        }
    )
)