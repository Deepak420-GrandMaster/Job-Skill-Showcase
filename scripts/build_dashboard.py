"""Build the job-hunt dashboard from the trackers.

Usage: python3 scripts/build_dashboard.py

Reads tracker/applications.csv, tracker/cold_email_contacts.csv and the dated
folders (tracker/<YYYY>/<MM-Month>/<YYYY-MM-DD>/contacts.csv, used to date each
contact), then writes:
  dashboard/stats.json    all numbers, for reuse
  dashboard/summary.svg   static summary rendered in the README
  README.md, SKILL.md     the block between the DASHBOARD markers
"""
import csv, glob, json, os, re
from collections import Counter, defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, "tracker")
D = os.path.join(ROOT, "dashboard")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def rows(path):
    with open(path, encoding="utf-8") as f:
        # header names are normalised ("Connect Request Sent" == "connect_request_sent") so edits
        # made in the GitHub web editor or a spreadsheet do not break the counts
        norm = lambda k: re.sub(r"[^a-z0-9]+", "_", k.strip().lower()).strip("_")
        lines = [l for l in f.read().splitlines() if l.strip()]  # tolerate blank lines (e.g. above the header)
        return [{norm(k): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(lines)
                if any((v or "").strip() for v in r.values() if isinstance(v, str))]


def low(s):
    return (s or "").lower()


# ---- classification rules (one place to tune) ----
def app_state(status):
    s = low(status)
    if "rejected" in s:
        return "rejected"
    if "submitted" in s or "applied" in s:
        return "applied"
    if "blocked" in s or "account" in s:
        return "blocked"
    return "in_progress"


def connected(v):
    s = low(v)
    return s.startswith("yes") or s.startswith("pending")


def messaged(v):
    return low(v).startswith("yes")


def email_sent(status):
    s = low(status)
    return "sent" in s and "deepak to send" not in s


def email_draft(status):
    return "draft" in low(status) and not email_sent(status)


def replied(*fields):
    return any("reply_received" in low(f) or "replied" in low(f) for f in fields)


def month_key(d):
    return d[:7] if re.match(r"\d{4}-\d{2}", d or "") else "unknown"


def month_label(k):
    if k == "unknown":
        return "Undated"
    y, m = k.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def build():
    apps = rows(os.path.join(T, "applications.csv"))
    contacts = rows(os.path.join(T, "cold_email_contacts.csv"))

    # date each contact from the first dated folder it appears in
    first_seen = {}
    for p in sorted(glob.glob(os.path.join(T, "*", "*", "*", "contacts.csv"))):
        day = os.path.basename(os.path.dirname(p))
        for r in rows(p):
            first_seen.setdefault((low(r.get("company")), low(r.get("contact_name"))), day)
    app_day = {}
    for a in apps:
        app_day.setdefault(low(a.get("company")).split(" (")[0], a.get("date", ""))

    for c in contacts:
        key = (low(c.get("company")), low(c.get("contact_name")))
        c["_date"] = first_seen.get(key) or app_day.get(low(c.get("company")).split(" (")[0], "")

    # ---- totals ----
    states = Counter(app_state(a.get("status")) for a in apps)
    tot = {
        "applied": states["applied"] + states["rejected"],  # rejected ones were submitted too
        "in_progress": states["in_progress"] + states["blocked"],
        "rejected": states["rejected"],
        "screened_applications": len(apps),
        "connections": sum(connected(c.get("connect_request_sent")) for c in contacts),
        "linkedin_messages": sum(messaged(c.get("linkedin_message_sent")) for c in contacts),
        "emails_sent": sum(email_sent(c.get("email_status")) for c in contacts),
        "email_drafts": sum(email_draft(c.get("email_status")) for c in contacts),
        "emails_found": sum(bool(c.get("email")) for c in contacts),
        "replies": sum(replied(c.get("email_status"), c.get("notes")) for c in contacts),
        "contacts": len(contacts),
    }
    tot["response_rate"] = round(100 * tot["replies"] / tot["connections"], 1) if tot["connections"] else 0

    # ---- monthly and daily ----
    blank = lambda: {"applied": 0, "connections": 0, "emails_sent": 0, "email_drafts": 0,
                     "linkedin_messages": 0, "rejected": 0, "in_progress": 0}
    monthly, daily = defaultdict(blank), defaultdict(blank)
    for a in apps:
        st = app_state(a.get("status"))
        cols = ["applied", "rejected"] if st == "rejected" else ["applied"] if st == "applied" else ["in_progress"]
        for col in cols:
            monthly[month_key(a.get("date"))][col] += 1
            daily[a.get("date") or "unknown"][col] += 1
    for c in contacts:
        for col, ok in (("connections", connected(c.get("connect_request_sent"))),
                        ("linkedin_messages", messaged(c.get("linkedin_message_sent"))),
                        ("emails_sent", email_sent(c.get("email_status"))),
                        ("email_drafts", email_draft(c.get("email_status")))):
            if ok:
                monthly[month_key(c["_date"])][col] += 1
                daily[c["_date"] or "unknown"][col] += 1

    months = [dict(key=k, label=month_label(k), **v) for k, v in sorted(monthly.items())]
    days = [dict(day=k, **v) for k, v in sorted(daily.items()) if k != "unknown"]

    # application list for the table (no personal data of contacts)
    app_list = [{
        "date": a.get("date", ""), "company": a.get("company", ""), "role": a.get("role", ""),
        "location": a.get("location", ""), "source": a.get("source", ""),
        "match": a.get("match_pct", ""), "state": app_state(a.get("status")), "status": a.get("status", ""),
        "connect": low(a.get("connect_sent")).startswith("yes"),
    } for a in apps]

    now = datetime.now(ZoneInfo("Europe/Paris"))
    stats = {"generated": now.date().isoformat(), "generated_at": now.strftime("%d %b %Y, %H:%M") + " (Paris time)", "totals": tot, "months": months,
             "days": days, "applications": app_list}
    os.makedirs(D, exist_ok=True)
    with open(os.path.join(D, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    return stats


# ---- outputs ----
# ---- outputs ----
# Pastel palette on a warm cream ground; darker "ink" tones keep text readable (WCAG AA on the pastels).
P = {"bg": "#fbf8f3", "card": "#ffffff", "line": "#ece6dc", "text": "#2b2a33", "muted": "#7a7680",
     "peach": "#ffc9b9", "peach_ink": "#b5452b", "mint": "#bfe8cf", "mint_ink": "#2f7a4f",
     "lavender": "#d9cdf7", "lav_ink": "#5b45a8", "butter": "#fae7a8", "butter_ink": "#8a6a10"}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def write_svg(stats):
    t = stats["totals"]
    by_key = {m["key"]: m for m in stats["months"] if m["key"] != "unknown"}
    end = max(list(by_key) + [stats["generated"][:7]])
    y, mo = int(end[:4]), int(end[5:7])
    keys = []
    for _ in range(6):
        keys.insert(0, f"{y:04d}-{mo:02d}")
        y, mo = (y - 1, 12) if mo == 1 else (y, mo - 1)
    zero = {"applied": 0, "connections": 0, "emails_sent": 0, "email_drafts": 0, "linkedin_messages": 0, "rejected": 0, "in_progress": 0}
    months = [by_key.get(k) or dict(zero, key=k, label=month_label(k)) for k in keys]
    table = [m for m in stats["months"] if m["key"] != "unknown"][::-1][:12]  # newest first, up to a year
    W, H = 880, 430 + 40 + 34 * (len(table) + 2) + 24
    sans = "ui-sans-serif,system-ui,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
    mono = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="Job hunt dashboard: {t["applied"]} applied, {t["connections"]} connection requests, {t["emails_sent"]} emails sent">',
           f"<style>.n{{font:700 42px {sans};font-variant-numeric:tabular-nums;letter-spacing:-.035em}}"
           f".l{{font:600 10.5px {mono};letter-spacing:.18em}}.s{{font:500 12.5px {sans}}}.v{{font:700 12px {sans};font-variant-numeric:tabular-nums}}"
           ".b{animation:g 1.1s cubic-bezier(.16,1,.3,1) both;transform-box:fill-box;transform-origin:bottom}"
           ".c{animation:r .8s cubic-bezier(.16,1,.3,1) both}"
           "@keyframes g{from{transform:scaleY(0)}}@keyframes r{from{opacity:0;transform:translateY(8px)}}"
           "@media (prefers-reduced-motion:reduce){.b,.c{animation:none}}</style>",
           f'<rect width="{W}" height="{H}" rx="22" fill="{P["bg"]}" stroke="{P["line"]}"/>',
           f'<text x="32" y="44" class="l" fill="{P["muted"]}">JOB HUNT · TILL DATE</text>',
           ]
    cards = [("APPLIED", t["applied"], P["peach"], P["peach_ink"], f'incl. {t["rejected"]} rejected · {t["in_progress"]} in progress'),
             ("CONNECTION REQUESTS", t["connections"], P["mint"], P["mint_ink"], f'{plural(t["linkedin_messages"], "LinkedIn message", "LinkedIn messages")} with CV'),
             ("EMAILS SENT", t["emails_sent"], P["lavender"], P["lav_ink"], f'{plural(t["email_drafts"], "draft", "drafts")} · {plural(t["replies"], "reply", "replies")}')]
    cw = (W - 64 - 32) / 3
    for i, (lab, val, fill, ink, sub) in enumerate(cards):
        x = 32 + i * (cw + 16)
        out += [f'<g class="c" style="animation-delay:{.08*i:.2f}s">',
                f'<rect x="{x:.0f}" y="64" width="{cw:.0f}" height="118" rx="16" fill="{fill}"/>',
                f'<text x="{x+22:.0f}" y="92" class="l" fill="{ink}">{lab}</text>',
                f'<text x="{x+22:.0f}" y="143" class="n" fill="{P["text"]}">{val}</text>',
                f'<text x="{x+22:.0f}" y="166" class="s" fill="{ink}">{esc(sub)}</text></g>']
    top, bot, left, right = 246, 380, 56, W - 32
    out += [f'<rect x="32" y="200" width="{W-64}" height="208" rx="16" fill="{P["card"]}" stroke="{P["line"]}"/>',
            f'<text x="52" y="226" class="l" fill="{P["muted"]}">MONTH BY MONTH</text>']
    series = [("applied", P["peach"], P["peach_ink"], "Applied"), ("connections", P["mint"], P["mint_ink"], "Connections"),
              ("emails_sent", P["lavender"], P["lav_ink"], "Emails sent")]
    lx = W - 52
    for key, fill, ink, name in reversed(series):
        lx -= 7 * len(name) + 30
        out += [f'<rect x="{lx:.0f}" y="217" width="11" height="11" rx="3" fill="{fill}"/>',
                f'<text x="{lx+17:.0f}" y="226" class="s" fill="{P["muted"]}">{name}</text>']
    vmax = max([1] + [m[k] for m in months for k, *_ in series])
    vmax = -(-vmax // 4) * 4  # round up so the 4 gridlines land on whole numbers
    left = 76
    for g in range(5):
        y = bot - (bot - top) * g / 4
        out.append(f'<line x1="{left}" x2="{right-20}" y1="{y:.1f}" y2="{y:.1f}" stroke="{P["line"]}"/>')
        out.append(f'<text x="{left-10}" y="{y+4:.1f}" class="s" fill="{P["muted"]}" text-anchor="end">{round(vmax*g/4)}</text>')
    gw = (right - 20 - left) / max(1, len(months))
    bw = min(36, gw / 4.2)
    for i, m in enumerate(months):
        cx = left + gw * i + gw / 2
        for j, (key, fill, ink, _) in enumerate(series):
            h = (bot - top) * m[key] / vmax
            x = cx + (j - 1.5) * (bw + 6) + 3
            out.append(f'<rect class="b" style="animation-delay:{.08*j+.1*i:.2f}s" x="{x:.1f}" y="{bot-h:.1f}" width="{bw:.1f}" height="{max(h,0):.1f}" rx="6" fill="{fill}"/>')
            if m[key]:
                out.append(f'<text x="{x+bw/2:.1f}" y="{bot-h-7:.1f}" class="v" fill="{ink}" text-anchor="middle">{m[key]}</text>')
        out.append(f'<text x="{cx:.1f}" y="{bot+20}" class="s" fill="{P["text"] if m["key"] in by_key else P["muted"]}" text-anchor="middle">{esc(m["label"])}</text>')
    # month-by-month table
    ty = 430
    cols = [("Month", None, 52), ("Applied", "applied", 340), ("Connections", "connections", 462),
            ("LinkedIn msgs", "linkedin_messages", 584), ("Drafts", "email_drafts", 706), ("Rejected", "rejected", 828)]
    th = 34 * (len(table) + 2) + 30
    out += [f'<rect x="32" y="{ty}" width="{W-64}" height="{th}" rx="16" fill="{P["card"]}" stroke="{P["line"]}"/>',
            f'<text x="52" y="{ty+26}" class="l" fill="{P["muted"]}">MONTH-WISE BREAKDOWN</text>']
    hy = ty + 56
    for name, key, x in cols:
        anchor = "start" if key is None else "end"
        out.append(f'<text x="{x}" y="{hy}" class="s" fill="{P["muted"]}" text-anchor="{anchor}">{name}</text>')
    out.append(f'<line x1="52" x2="{W-52}" y1="{hy+12}" y2="{hy+12}" stroke="{P["line"]}"/>')
    ink = {"applied": P["peach_ink"], "connections": P["mint_ink"], "emails_sent": P["lav_ink"]}
    rows_ = table + [dict({k: sum(m[k] for m in stats["months"]) for k in zero}, label="Total")]
    for i, m in enumerate(rows_):
        ry = hy + 34 * (i + 1)
        last = i == len(rows_) - 1
        if last:
            out.append(f'<line x1="52" x2="{W-52}" y1="{ry-22}" y2="{ry-22}" stroke="{P["line"]}"/>')
        elif i % 2 == 0:
            out.append(f'<rect x="44" y="{ry-21}" width="{W-88}" height="30" rx="8" fill="{P["bg"]}"/>')
        for name, key, x in cols:
            if key is None:
                out.append(f'<text x="{x}" y="{ry}" class="{"v" if last else "s"}" fill="{P["text"]}">{esc(m["label"])}</text>')
            else:
                out.append(f'<text x="{x}" y="{ry}" class="v" fill="{ink.get(key, P["text"])}" text-anchor="end">{m.get(key, 0)}</text>')
    out.append("</svg>")
    open(os.path.join(D, "summary.svg"), "w", encoding="utf-8").write("\n".join(out))


def dashboard_block(stats, full=True, img="dashboard/summary.svg"):
    t = stats["totals"]
    md = ["<!-- DASHBOARD:START (generated by scripts/build_dashboard.py; edits here are overwritten) -->",
          "## 📊 Dashboard" if full else "## Dashboard (till date)", "",
          f'<p align="center"><img src="{img}" alt="Job hunt dashboard: {t["applied"]} applied, {plural(t["connections"], "connection request", "connection requests")}, {plural(t["emails_sent"], "email sent", "emails sent")}" width="880"></p>', "",
          "| 🟠 Applied | 🟢 Connection requests | 🟣 Emails sent | LinkedIn messages | Replies | In progress | Rejected |",
          "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
          f"| **{t['applied']}** | **{t['connections']}** | **{t['emails_sent']}** | {t['linkedin_messages']} | {t['replies']} | {t['in_progress']} | {t['rejected']} |", ""]
    if full:
        md += ["### Month by month", "",
               "| Month | Applied | Connection requests | Emails sent | Email drafts | LinkedIn messages | Rejected |",
               "|---|:---:|:---:|:---:|:---:|:---:|:---:|"]
        for m in reversed(stats["months"]):
            md.append(f"| **{m['label']}** | {m['applied']} | {m['connections']} | {m['emails_sent']} | {m['email_drafts']} | {m['linkedin_messages']} | {m['rejected']} |")
        md.append("")
        lab = {"applied": "✅ Applied", "in_progress": "⏳ In progress", "blocked": "⛔ Blocked", "rejected": "❌ Rejected"}
        for m in reversed(stats["months"]):
            apps = [a for a in stats["applications"] if month_key(a["date"]) == m["key"]]
            md += [f"<details><summary><b>{m['label']}</b> · {plural(len(apps), 'application', 'applications')} tracked (click to expand)</summary>", "",
                   "| Date | Company | Role | Location | Match | Status |", "|---|---|---|---|:---:|---|"]
            for a in sorted(apps, key=lambda a: a["date"], reverse=True):
                cell = lambda s: esc(s).replace("|", "/")
                md.append(f"| {a['date']} | **{cell(a['company'])}** | {cell(a['role'])} | {cell(a['location'])} | "
                          f"{(a['match'] + '%') if a['match'] else '—'} | {lab[a['state']]} |")
            md += ["", "</details>", ""]
    md += [f"<sub>Updated {stats['generated']} from <code>tracker/</code>. A GitHub Action regenerates this block on every tracker push; "
           "locally: <code>python3 scripts/build_dashboard.py</code>.</sub>",
           "<!-- DASHBOARD:END -->"]
    return "\n".join(md)


def write_readme_only(stats):
    """README shows only the dashboard and when it was last updated (rewritten in full each run)."""
    t = stats["totals"]
    alt = (f'Job hunt dashboard: {t["applied"]} applied, '
           f'{plural(t["connections"], "connection request", "connection requests")}, '
           f'{plural(t["emails_sent"], "email sent", "emails sent")}')
    md = ["<!-- Generated by scripts/build_dashboard.py on every tracker update. Do not edit. -->",
          f'<p align="center"><img src="dashboard/summary.svg" alt="{alt}" width="880"></p>', "",
          f'<p align="center"><sub>Last updated: {stats["generated_at"]}</sub></p>', ""]
    open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8").write("\n".join(md))


def put_block(path, block, after_paragraphs):
    s = open(path, encoding="utf-8").read()
    if "<!-- DASHBOARD:START" in s:
        s = re.sub(r"<!-- DASHBOARD:START.*?<!-- DASHBOARD:END -->", lambda _: block, s, flags=re.S)
    else:
        parts = s.split("\n\n")
        s = "\n\n".join(parts[:after_paragraphs] + [block] + parts[after_paragraphs:])
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    st = build()
    write_svg(st)
    write_readme_only(st)
    # SKILL.md: compact block after the front matter + title, so the skill itself shows the numbers
    put_block(os.path.join(ROOT, "SKILL.md"), dashboard_block(st, full=False), 2)
    t = st["totals"]
    print(f"applied {t['applied']} | connections {t['connections']} | emails sent {t['emails_sent']} | months {len(st['months'])}")
