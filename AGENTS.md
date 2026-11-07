# Instructions for any AI agent (ChatGPT, Codex, Claude…)

This repo is Deepak's job-hunt skill and the **shared brain** for every agent that runs it.
Two agents (Claude and ChatGPT) work on it at the same time.

1. Follow `SKILL.md` — especially the section **TWO AGENTS, ONE BRAIN**.
2. Before doing anything: `git pull --rebase`, then read `brain/memory.md`, the newest entries of `brain/handoff.md`, and `brain/claims.csv`.
3. Claim a job in `brain/claims.csv` (and push) before working on it; never work on a company someone else has claimed or already applied to.
4. Prefix commit messages with your name: `[chatgpt]` or `[claude]`. Trackers are append-only; never rename or reorder columns.
5. `README.md` is generated (dashboard only). Do not edit it by hand; it updates automatically when `tracker/` changes.
6. Every ~10 minutes during a run, the LinkedIn-lane agent sweeps for matching jobs posted in the last 10 minutes and applies to them first (`SKILL.md` → "FRESH-POST SWEEP", URLs from `python3 scripts/fresh_urls.py`).
7. Every LinkedIn message, email and connection note uses the templates in `SKILL.md` → "MESSAGE + NOTE TEMPLATES" (with the tailored CV attached). One first contact + one follow-up per person, then a different person at that organisation.

**LinkedIn:** follow the LINKEDIN SAFETY section of SKILL.md. Agents do not operate LinkedIn in the browser, and never add delays or anything else to avoid detection.
