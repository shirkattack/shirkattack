#!/usr/bin/env python3
"""Render assets/stats.svg, the one-card GitHub summary for the profile README.

Pulls numbers from the GitHub GraphQL API (token from $GITHUB_TOKEN or `gh auth token`)
and draws one wide card in the Kanagawa palette used across the README. No third-party
card service, so nothing breaks when a public deployment gets paused.
"""
import json, os, subprocess, sys, urllib.request
from datetime import datetime, timezone
from html import escape

LOGIN = os.environ.get("PROFILE_LOGIN", "shirkattack")
INK, PRUSSIAN, WAVE, MIST, CREAM, SAND, OCHRE = (
    "#0B1F33", "#1B3F6B", "#2A5F8F", "#7C93AE", "#F3EBDD", "#D8CDB8", "#C9A464")
LANG_TINTS = ["#C9A464", "#F3EBDD", "#7C93AE", "#2A5F8F", "#D8CDB8", "#5B7EA6", "#1B3F6B", "#9BB0C9"]
FONT = "font-family=\"ui-monospace,'SF Mono',Menlo,Consolas,monospace\""
SERIF = "font-family=\"Georgia,'Times New Roman',serif\""

QUERY = """
query($login:String!, $from:DateTime!) {
  user(login:$login) {
    followers { totalCount }
    repositories(first:100, ownerAffiliations:OWNER, isFork:false, orderBy:{field:UPDATED_AT, direction:DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first:10, orderBy:{field:SIZE, direction:DESC}) { edges { size node { name color } } }
      }
    }
    contributionsCollection(from:$from) {
      totalCommitContributions restrictedContributionsCount
      totalPullRequestContributions totalIssueContributions totalPullRequestReviewContributions
    }
  }
}"""


def token():
    t = os.environ.get("GITHUB_TOKEN")
    if t:
        return t
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def fetch():
    year_start = datetime(datetime.now(timezone.utc).year, 1, 1, tzinfo=timezone.utc).isoformat()
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN, "from": year_start}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={"Authorization": f"bearer {token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL errors: {data['errors']}")
    return data["data"]["user"]


def card_open(w, h, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
            f'<rect width="{w}" height="{h}" rx="10" fill="{INK}"/>'
            f'<text x="26" y="36" {SERIF} font-size="19" font-weight="700" fill="{CREAM}">{escape(title)}</text>'
            f'<rect x="26" y="46" width="34" height="2" fill="{OCHRE}"/>')


def glance_card(u, c):
    """One wide card: three numbers that read without context, plus a compact language bar."""
    stars = sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
    numbers = [("stars", stars), ("public repos", u["repositories"]["totalCount"]),
               ("pull requests", c["totalPullRequestContributions"])]

    sizes = {}
    for n in u["repositories"]["nodes"]:
        for e in n["languages"]["edges"]:
            name = {"Jupyter Notebook": "Jupyter"}.get(e["node"]["name"], e["node"]["name"])
            sizes[name] = sizes.get(name, 0) + e["size"]
    ranked = sorted(sizes.items(), key=lambda kv: -kv[1])
    top, rest = ranked[:4], sum(v for _, v in ranked[4:])
    if rest:
        top.append(("other", rest))
    total = sum(v for _, v in top) or 1

    w, h = 860, 150
    out = [card_open(w, h, "GitHub at a glance")]
    # left: three tiles
    tile_w = 130
    for i, (label, val) in enumerate(numbers):
        x = 26 + i * tile_w
        out.append(f'<text x="{x}" y="104" {SERIF} font-size="40" font-weight="700" fill="{CREAM}">{val:,}</text>')
        out.append(f'<text x="{x}" y="124" {FONT} font-size="12" fill="{SAND}">{escape(label)}</text>')
    # divider
    out.append(f'<rect x="{26 + 3 * tile_w}" y="66" width="1" height="62" fill="{PRUSSIAN}"/>')
    # right: stacked language bar + legend
    x0 = 26 + 3 * tile_w + 30
    bar_w = w - 26 - x0
    out.append(f'<text x="{x0}" y="76" {FONT} font-size="12" fill="{SAND}">languages, by bytes</text>')
    x = x0
    for i, (name, size) in enumerate(top):
        seg = bar_w * size / total
        out.append(f'<rect x="{x:.1f}" y="86" width="{max(seg-2,1):.1f}" height="10" rx="2" fill="{LANG_TINTS[i % len(LANG_TINTS)]}"/>')
        x += seg
    for i, (name, size) in enumerate(top):
        col, row = i % 3, i // 3
        lx, ly = x0 + col * (bar_w / 3), 118 + row * 18
        label = f"{name} {100*size/total:.0f}%"
        out.append(f'<circle cx="{lx+4:.1f}" cy="{ly-4}" r="4" fill="{LANG_TINTS[i % len(LANG_TINTS)]}"/>')
        out.append(f'<text x="{lx+14:.1f}" y="{ly}" {FONT} font-size="12" fill="{SAND}">{escape(label)}</text>')
    out.append(f'<text x="{w-26}" y="36" {SERIF} font-style="italic" font-size="10" fill="{MIST}" text-anchor="end">updated {datetime.now(timezone.utc):%Y-%m-%d}</text></svg>')
    return "".join(out)


if __name__ == "__main__":
    u = fetch()
    root = os.path.join(os.path.dirname(__file__), "..", "assets")
    open(os.path.join(root, "stats.svg"), "w").write(glance_card(u, u["contributionsCollection"]))
    print("wrote assets/stats.svg")
