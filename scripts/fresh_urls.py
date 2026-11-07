"""Print the LinkedIn search URLs for the fresh-post sweep (SKILL.md -> FRESH-POST SWEEP).

Usage: python3 scripts/fresh_urls.py            # posted in the last 10 minutes
       python3 scripts/fresh_urls.py 3600       # any window, in seconds (e.g. last hour)

f_TPR=r<seconds> is LinkedIn's "posted within" filter; sortBy=DD puts the newest first.
No salary filter: brand-new postings often have no salary yet and the filter would hide them,
so salary is checked in the job text instead (SKILL.md section 3).
"""
import sys
from urllib.parse import urlencode

FRANCE = "105015875"
KEYWORDS = ["data", "AI engineer", "LLM", "IA"]

window = int(sys.argv[1]) if len(sys.argv) > 1 else 600
for kw in KEYWORDS:
    q = urlencode({"keywords": kw, "geoId": FRANCE, "f_TPR": f"r{window}", "sortBy": "DD"})
    print(f"https://www.linkedin.com/jobs/search/?{q}")
