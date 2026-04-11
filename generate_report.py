#!/usr/bin/env python3
"""Generate personalised AI visibility report from the carlton-dental template."""

import re, os, sys, subprocess, json

TEMPLATE_PATH = "/home/nikunj19/Projects/aiscite/audit/carlton-dental/index.html"
REPO_DIR = "/home/nikunj19/Projects/aiscite"
AUDIT_DIR = os.path.join(REPO_DIR, "audit")

# ─── helpers ─────────────────────────────────────────────────────────────────

def slugify(name):
    return name.lower().replace(" ", "-").replace("&", "").replace("'", "").replace(".", "").replace(",", "").replace(" LLP", "").replace(" LLC", "").replace(" LLP", "")

def score_badge(score):
    if score <= 30: return "Significant gaps — clear opportunity"
    if score <= 45: return "Room to improve"
    if score <= 55: return "Average — below the noise"
    if score <= 65: return "Improving — gaps to close"
    if score <= 75: return "Strong — but not untouchable"
    if score <= 85: return "Well-positioned"
    return "Near ceiling"

def bar_label(score):
    if score <= 30: return "Needs work"
    if score <= 50: return "Below average"
    if score <= 70: return "Decent"
    if score <= 85: return "Good"
    return "Strong"

def generate(name, domain, city, biz_type, audit):
    slug = slugify(name)
    out_dir = os.path.join(AUDIT_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    score = audit["overall_score"]
    badge = score_badge(score)

    with open(TEMPLATE_PATH) as f:
        template = f.read()
    html = template

    # ── 1. Business name ───────────────────────────────────────────────────────
    html = html.replace("Carlton Dental", name)

    # ── 2. City replacements (BEFORE biz type, so "dental" is still in text) ──
    html = html.replace("a dental practice in Toronto", f"a {biz_type} in {city}")
    html = html.replace("across Toronto", f"across {city}")
    html = re.sub(r'the Toronto average', f'the {city} average', html)

    # ── 3. Biz type (after city, so phrases like "a dental practice" are gone) ─
    html = html.replace("dental practice", biz_type)
    html = html.replace("dentist", biz_type)
    html = html.replace("dental", biz_type)

    # ── 4. Score number ────────────────────────────────────────────────────────
    html = html.replace('<div class="score-number">78</div>', f'<div class="score-number">{score}</div>')

    # ── 5. Score badge ──────────────────────────────────────────────────────────
    html = re.sub(
        r'<div class="score-badge"[^>]*>Strong — but not untouchable — room to improve\.</div>',
        f'<div class="score-badge" style="margin-top:12px">{badge}</div>',
        html
    )
    html = html.replace(
        '<div class="score-badge" style="margin-top:12px">Strong — but not untouchable</div>',
        f'<div class="score-badge" style="margin-top:12px">{badge}</div>'
    )

    # ── 6. Bar widths ───────────────────────────────────────────────────────────
    # Template: AI_readability=20, Citation=100, Authority=100, Content=100, Positioning=60
    # audit: ai_readability, citation_signals, authority_trust, content_depth, positioning_clarity
    # Read actual bar values from template dynamically
    template_bars = dict(re.findall(
        r'<span class="bar-label">([^<]+)</span><div class="bar-track"><div class="bar-fill" style="width:\d+%"></div></div><span class="bar-val">(\d+)</span>',
        template
    ))
    subs = {
        "AI readability": audit["ai_readability"],
        "Citation signals": audit["citation_signals"],
        "Authority and trust": audit["authority_trust"],
        "Content depth": audit["content_depth"],
        "Positioning clarity": audit["positioning_clarity"],
    }
    for label, raw in subs.items():
        pct = round(raw / 20 * 100)
        # Replace using actual template value found above
        old = f'<span class="bar-label">{label}</span><div class="bar-track"><div class="bar-fill" style="width:{template_bars[label]}%"></div></div><span class="bar-val">{template_bars[label]}</span>'
        new = f'<span class="bar-label">{label}</span><div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div><span class="bar-val">{pct}</span>'
        html = html.replace(old, new)

    # ── 7. Section leads & hardcoded 78 ──────────────────────────────────────
    # Fix section-lead text that still references score 78
    html = re.sub(
        r'sits at \d+/100',
        f'sits at {score}/100',
        html
    )
    html = re.sub(
        r'scores \d+/100',
        f'scores {score}/100',
        html
    )
    # Fix PostHog capture
    html = re.sub(
        r'business: "carlton-law_firm", score: \d+',
        f'business: "{slug}", score: {score}',
        html
    )
    # Fix chart JS dataset: [benchmark, avg, score] — replace the score value
    # Template has [90, 40, 78]
    html = re.sub(
        r'data: \[(\d+),\s*\d+,\s*\d+\]',
        lambda m: f'data: [{m.group(1)}, 40, {score}]',
        html
    )

    # ── 7. Title tag ──────────────────────────────────────────────────────────
    html = re.sub(
        r'<title>.*?</title>',
        f'<title>Aiscite — {name} AI Visibility Audit</title>',
        html, flags=re.DOTALL
    )
    html = re.sub(r'<meta name="description" content=".*?">',
        f'<meta name="description" content="AI visibility audit for {name} — {biz_type} in {city}">', html)

    # ── 8. Canonical URL ──────────────────────────────────────────────────────
    html = re.sub(
        r'https://aiscite\.com/audit/[^/"]+/?',
        f'https://aiscite.com/audit/{slug}/',
        html
    )
    html = re.sub(r'"og:url" content=".*?"', f'"og:url" content="https://aiscite.com/audit/{slug}/"', html)

    # ── 9. JS variables ────────────────────────────────────────────────────────
    html = re.sub(r'var bizName = "[^"]+"', f'var bizName = "{name}"', html)
    html = re.sub(r'var bizType = "[^"]+"', f'var bizType = "{biz_type}"', html)
    # Add bizCity after bizType
    if "var bizCity" not in html:
        html = html.replace(
            f'var bizType = "{biz_type}"',
            f'var bizType = "{biz_type}"\n  var bizCity = "{city}"'
        )
    else:
        html = re.sub(r'var bizCity = "[^"]+"', f'var bizCity = "{city}"', html)

    # ── 10. "Prepared privately for" ──────────────────────────────────────────
    html = html.replace("Prepared privately for Carlton Dental", f"Prepared privately for {name}")

    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)

    print(f"  Generated: {out_path}")
    return slug, out_path


def push_to_github(slug):
    """Commit and push to aiscite GitHub Pages repo."""
    os.chdir(REPO_DIR)
    subprocess.run(["git", "add", f"audit/{slug}/"], check=True)
    result = subprocess.run(["git", "diff", "--staged", "--name-only"], capture_output=True, text=True)
    if not result.stdout.strip():
        print(f"  No changes to commit for {slug}")
        return False
    subprocess.run(["git", "commit", "-m", f"audit: add {slug} report"], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)
    print(f"  Pushed to https://aiscite.com/audit/{slug}/")
    return True


# ─── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    targets = [
        {"name": "Kormans LLP", "domain": "kormans.ca", "city": "Toronto", "biz_type": "law firm",
         "audit": {"overall_score": 62, "ai_readability": 8, "citation_signals": 14, "authority_trust": 11, "content_depth": 20, "positioning_clarity": 9}},
        {"name": "Phillips Barristers", "domain": "waddellphillips.com", "city": "Toronto", "biz_type": "law firm",
         "audit": {"overall_score": 49, "ai_readability": 10, "citation_signals": 0, "authority_trust": 5, "content_depth": 20, "positioning_clarity": 14}},
        {"name": "Westgate Law", "domain": "westgatelaw.ca", "city": "Toronto", "biz_type": "law firm",
         "audit": {"overall_score": 51, "ai_readability": 10, "citation_signals": 6, "authority_trust": 5, "content_depth": 15, "positioning_clarity": 15}},
    ]

    for t in targets:
        slug, path = generate(**t)
        push_to_github(slug)
        print(f"  Live at: https://aiscite.com/audit/{slug}/\n")
