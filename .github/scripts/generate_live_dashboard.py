import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "AsadAliEngineer")
TOKEN = os.environ.get("DASHBOARD_TOKEN") or os.environ.get("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("DASHBOARD_TOKEN or GITHUB_TOKEN is required.")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": "github-profile-live-dashboard",
    "X-GitHub-Api-Version": "2022-11-28",
}


def github(path, payload=None, include_headers=False):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        data=data,
        headers=HEADERS,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response_data = json.load(response)
            if include_headers:
                return response_data, dict(response.headers.items())
            return response_data
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {error.code} for {path}: {body}") from error


def owned_public_repositories():
    repositories = []
    page = 1
    while True:
        batch = github(
            f"/users/{urllib.parse.quote(USERNAME)}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}"
        )
        repositories.extend(repo for repo in batch if not repo["private"])
        if len(batch) < 100:
            return repositories
        page += 1


def compact(value):
    number = int(value or 0)
    if number < 1000:
        return str(number)
    text = f"{number / 1000:.2f}".rstrip("0").rstrip(".")
    return f"{text}k"


def chart_paths(values, x, y, width, height):
    safe_values = values if len(values) > 1 else [0, 0]
    maximum = max(max(safe_values), 1)
    points = []
    for index, value in enumerate(safe_values):
        point_x = x + (index / (len(safe_values) - 1)) * width
        point_y = y + height - (value / maximum) * height
        points.append((point_x, point_y))
    line = " ".join(
        f"{'M' if index == 0 else 'L'}{point_x:.1f},{point_y:.1f}"
        for index, (point_x, point_y) in enumerate(points)
    )
    area = (
        f"{line} L{x + width:.1f},{y + height:.1f} "
        f"L{x:.1f},{y + height:.1f} Z"
    )
    return line, area, maximum


def repository_commit_count(repository):
    owner = repository["owner"]["login"]
    name = repository["name"]
    author = urllib.parse.quote(USERNAME)
    path = f"/repos/{owner}/{name}/commits?author={author}&per_page=1"
    try:
        commits, response_headers = github(path, include_headers=True)
    except RuntimeError as error:
        if "GitHub API 409" in str(error) or "Git Repository is empty" in str(error):
            return 0
        raise

    link_header = response_headers.get("Link", "")
    last_page = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link_header)
    return int(last_page.group(1)) if last_page else len(commits)


profile = github(f"/users/{urllib.parse.quote(USERNAME)}")
repositories = owned_public_repositories()

now = datetime.now(timezone.utc)
start = now - timedelta(days=364)
contribution_query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
          }
        }
      }
    }
  }
}
"""
contribution_response = github(
    "/graphql",
    {
        "query": contribution_query,
        "variables": {
            "login": USERNAME,
            "from": start.isoformat(),
            "to": now.isoformat(),
        },
    },
)
if contribution_response.get("errors"):
    raise RuntimeError(
        f"GitHub GraphQL error: {json.dumps(contribution_response['errors'])}"
    )

calendar = contribution_response["data"]["user"]["contributionsCollection"][
    "contributionCalendar"
]
weekly_contributions = [
    sum(day["contributionCount"] for day in week["contributionDays"])
    for week in calendar["weeks"]
]

public_authored_commits = sum(
    repository_commit_count(repository)
    for repository in repositories
    if not repository["fork"]
)

language_totals = {}
for repository in repositories:
    if repository["fork"] or repository["name"].lower() == USERNAME.lower():
        continue
    languages = github(
        f"/repos/{repository['owner']['login']}/{repository['name']}/languages"
    )
    for language, byte_count in languages.items():
        language_totals[language] = language_totals.get(language, 0) + byte_count

top_languages = sorted(
    language_totals.items(), key=lambda item: item[1], reverse=True
)[:10]
total_language_bytes = sum(language_totals.values()) or 1

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
}
fallback_colors = ["#58a6ff", "#3fb950", "#d29922", "#bc8cff", "#f778ba"]

line_path, area_path, weekly_peak = chart_paths(
    weekly_contributions, 58, 150, 500, 125
)
joined_year = datetime.fromisoformat(
    profile["created_at"].replace("Z", "+00:00")
).year
updated_date = now.date().isoformat()

stats = [
    ("Public repositories", profile["public_repos"]),
    ("Default-branch commits", public_authored_commits),
    ("Contributions · last year", calendar["totalContributions"]),
    ("Languages detected", len(language_totals)),
]

stat_cards = []
for index, (label, value) in enumerate(stats):
    column = index % 2
    row = index // 2
    x = 620 + column * 126
    y = 122 + row * 100
    stat_cards.append(
        f"""
      <g transform="translate({x} {y})">
        <rect width="116" height="86" rx="10" fill="#0b1320" stroke="#30363d" />
        <text x="12" y="33" class="metric">{escape(compact(value))}</text>
        <text x="12" y="59" class="label">{escape(label)}</text>
      </g>"""
    )

language_rows = []
for index, (language, byte_count) in enumerate(top_languages):
    column = 1 if index >= 5 else 0
    row = index % 5
    x = 52 + column * 410
    y = 402 + row * 38
    percentage = (byte_count / total_language_bytes) * 100
    bar_width = max(3, min(332, percentage * 7.5))
    color = language_colors.get(
        language, fallback_colors[index % len(fallback_colors)]
    )
    language_rows.append(
        f"""
      <g transform="translate({x} {y})">
        <circle cx="5" cy="-5" r="5" fill="{color}" />
        <text x="18" y="0" class="language">{escape(language)}</text>
        <text x="350" y="0" text-anchor="end" class="percent">{percentage:.1f}%</text>
        <rect x="18" y="10" width="332" height="7" rx="3.5" fill="#21262d" />
        <rect x="18" y="10" width="{bar_width:.1f}" height="7" rx="3.5" fill="{color}" />
      </g>"""
    )

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="620" viewBox="0 0 900 620" role="img" aria-labelledby="title desc">
  <title id="title">{escape(USERNAME)} live GitHub engineering signal</title>
  <desc id="desc">Public repositories, authored commits, last-year contributions, and languages generated from the official GitHub API.</desc>
  <defs>
    <linearGradient id="panel" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0d1117" />
      <stop offset="1" stop-color="#0a1220" />
    </linearGradient>
    <linearGradient id="activity" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#3fb950" stop-opacity="0.72" />
      <stop offset="1" stop-color="#3fb950" stop-opacity="0.04" />
    </linearGradient>
    <style>
      text {{ font-family: Inter, "Segoe UI", Arial, sans-serif; }}
      .title {{ fill: #f0f6fc; font-size: 25px; font-weight: 700; }}
      .subtitle {{ fill: #8b949e; font-size: 13px; }}
      .section {{ fill: #f0f6fc; font-size: 17px; font-weight: 650; }}
      .metric {{ fill: #58a6ff; font-size: 25px; font-weight: 750; }}
      .label {{ fill: #8b949e; font-size: 10.5px; }}
      .axis {{ fill: #8b949e; font-size: 10px; }}
      .language {{ fill: #c9d1d9; font-size: 13px; font-weight: 600; }}
      .percent {{ fill: #8b949e; font-size: 11px; }}
    </style>
  </defs>
  <rect x="1" y="1" width="898" height="618" rx="16" fill="url(#panel)" stroke="#30363d" stroke-width="2" />
  <circle cx="38" cy="41" r="8" fill="#3fb950" />
  <text x="58" y="49" class="title">Live Engineering Signal</text>
  <text x="58" y="74" class="subtitle">@{escape(USERNAME)} · joined {joined_year} · refreshed {updated_date} from the GitHub API</text>

  <rect x="30" y="101" width="560" height="229" rx="12" fill="#0b1320" stroke="#30363d" />
  <text x="52" y="130" class="section">Contribution activity · last 52 weeks</text>
  <line x1="58" y1="275" x2="558" y2="275" stroke="#30363d" />
  <line x1="58" y1="212.5" x2="558" y2="212.5" stroke="#21262d" />
  <line x1="58" y1="150" x2="558" y2="150" stroke="#21262d" />
  <path d="{area_path}" fill="url(#activity)" />
  <path d="{line_path}" fill="none" stroke="#3fb950" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />
  <text x="58" y="304" class="axis">{start.strftime('%Y-%m')}</text>
  <text x="558" y="304" text-anchor="end" class="axis">{now.strftime('%Y-%m')}</text>
  <text x="558" y="130" text-anchor="end" class="axis">peak {weekly_peak}/week</text>

  {''.join(stat_cards)}

  <rect x="30" y="350" width="840" height="240" rx="12" fill="#0b1320" stroke="#30363d" />
  <text x="52" y="382" class="section">Languages across owned public repositories · top {len(top_languages)}</text>
  {''.join(language_rows)}
</svg>
"""

output = Path("assets/live-engineering-signal.svg")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(svg, encoding="utf-8")

print(
    json.dumps(
        {
            "username": USERNAME,
            "publicRepositories": profile["public_repos"],
            "publicAuthoredCommits": public_authored_commits,
            "contributionsLastYear": calendar["totalContributions"],
            "languagesDetected": len(language_totals),
            "output": str(output),
        }
    )
)