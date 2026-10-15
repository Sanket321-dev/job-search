"""Collect public job feeds, normalize listings, match to the candidate and retain history."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/jobs.json"
PROFILE_PATH = ROOT / "data/profile.json"
HISTORY_PATH = ROOT / "data/seen.json"
NOW = datetime.now(timezone.utc)
MAX_AGE_DAYS = 30
HISTORY_DAYS = 90

PROFILE = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
ROLES = PROFILE["target_roles"]
SKILLS = PROFILE["skills"]
LOCATIONS = PROFILE["preferred_locations"]
INDIA_LOCATIONS = ("india", "pune", "pimpri", "chinchwad", "maharashtra", "mumbai", "nashik", "nagpur",
                   "bengaluru", "bangalore", "hyderabad", "chennai", "delhi", "ncr", "gurugram", "gurgaon", "noida")
ROLE_RULES = {
    "DevOps": r"devops|platform engineer|ci/cd",
    "Cloud": r"cloud|aws|azure|gcp",
    "Linux / SysAdmin": r"linux|system administrator|sysadmin|red hat",
    "Support / NOC / SRE": r"technical support|it support|noc|site reliability|\bsre\b|network support",
    "QA / Testing": r"quality assurance|\bqa\b|software test|manual test|automation test|test engineer",
    "Graduate / Associate": r"graduate|trainee|associate engineer|entry.level",
}
ROLE_QUERIES = ROLES

def parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        try:
            n = float(value)
            return datetime.fromtimestamp(n / 1000 if n > 10**12 else n, timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except ValueError:
        return None

def clean(value):
    value = re.sub(r"<[^>]*>", " ", str(value or ""))
    value = re.sub(r"\s+", " ", value).strip()
    return value

def fetch_json(url, headers=None, attempts=3):
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "KartiksJobRadar/2.0 (public job feed)", **(headers or {})})
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise last

def normalize_url(url):
    try:
        p = urllib.parse.urlsplit(str(url or "").strip())
        if p.scheme not in ("http", "https") or not p.hostname:
            return ""
        host = p.hostname.lower().removeprefix("www.")
        path = re.sub(r"/+", "/", p.path).rstrip("/")
        return urllib.parse.urlunsplit(("https", host, path, "", ""))
    except ValueError:
        return ""

def safe_application_url(url):
    try:
        p = urllib.parse.urlsplit(str(url or "").strip())
        if p.scheme not in ("http", "https") or not p.hostname:
            return ""
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))
    except ValueError:
        return ""

def classify(text):
    for name, pattern in ROLE_RULES.items():
        if re.search(pattern, text, re.I):
            return name
    return ""

def location_rank(location, remote=False):
    value = location.lower()
    if any(x.lower() in value for x in LOCATIONS[:1]) or any(x in value for x in ("pimpri", "chinchwad")):
        return 0
    if any(x.lower() in value for x in LOCATIONS[1:2]) or any(x in value for x in ("mumbai", "nashik", "nagpur", "kolhapur", "satara")):
        return 1
    if remote or "remote" in value or "work from home" in value:
        return 2
    if any(x in value for x in ("india", "bengaluru", "bangalore", "hyderabad", "chennai", "gurugram", "gurgaon", "noida", "delhi")):
        return 3
    return 9

def india_eligible(location, remote=False, remote_scope=""):
    """Accept listed Indian locations or remote roles whose scope includes India."""
    loc = location.lower()
    scope = remote_scope.lower()
    if any(term in loc for term in INDIA_LOCATIONS):
        return True
    if not remote:
        return False
    # Unscoped remote roles can be restricted to any country; include only scopes
    # that explicitly accept India or are worldwide/anywhere.
    scope_text = scope or loc
    return bool(re.search(r"india|worldwide|anywhere|global|all countries", scope_text, re.I))

def normalize(row, source):
    title = clean(row.get("title"))
    company = clean(row.get("company") or row.get("company_name") or "Company not listed")
    location_obj = row.get("location")
    location = clean(location_obj.get("display_name", "") if isinstance(location_obj, dict) else location_obj)
    description = clean(row.get("description") or row.get("summary"))[:1200]
    url = safe_application_url(row.get("url") or row.get("redirect_url") or row.get("apply_url"))
    remote = bool(row.get("remote")) or bool(re.search(r"remote|work from home|worldwide|anywhere|global", location, re.I))
    text = " ".join([title, description, " ".join(map(str, row.get("tags") or []))]).lower()
    category = classify(text)
    remote_scope = clean(row.get("candidate_required_location"))
    if not title or not url or not category or not india_eligible(location, remote, remote_scope):
        return None
    senior_title = re.search(r"\b(senior|lead|principal|staff|director|head of)\b", title, re.I)
    excessive_experience = re.search(
        r"(?:minimum|min\.?|at least|required|requires?)\s*(?:of\s*)?([3-9]|[1-9]\d)\+?\s*(?:years?|yrs?)|"
        r"([3-9]|[1-9]\d)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+)?experience",
        description, re.I)
    if senior_title or excessive_experience:
        return None
    tags = row.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    found = [s for s in SKILLS if re.search(r"(?<!\w)" + re.escape(s) + r"(?!\w)", text, re.I)]
    posted = parse_date(row.get("posted_at") or row.get("created_at") or row.get("publication_date") or row.get("created"))
    if posted and posted > NOW + timedelta(days=1):
        posted = None
    age = (NOW - posted).total_seconds() / 86400 if posted else None
    if age is not None and age > MAX_AGE_DAYS:
        return None
    exp_patterns = [r"(?:0\s*(?:-|to)\s*2|1\s*[-–]\s*2)\s*years?", r"\b(?:fresher|entry.level|graduate|trainee|junior|associate|intern)\b", r"\d+\+?\s*years?"]
    experience = next((m.group(0) for pat in exp_patterns if (m := re.search(pat, description + " " + title, re.I))), "Not specified")
    if remote_scope and remote_scope.lower() not in ("worldwide", "anywhere"):
        location = location or remote_scope
    return {"id": normalize_url(url), "title": title, "company": company, "location": location or ("Remote" if remote else "Not specified"),
            "remote": remote, "experience": experience, "description": description,
            "posted_at": posted.isoformat() if posted else None, "salary": clean(row.get("salary") or row.get("salary_range")) or None,
            "tags": [clean(x) for x in tags if clean(x)][:10], "skills": found, "category": category,
            "source": source, "url": url, "status": "unverified", "first_seen_at": NOW.isoformat()}

def collect_adzuna():
    app_id, key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (app_id and key):
        return [], "Adzuna", "skipped: credentials not configured"
    jobs=[]
    try:
        # Rotate one query per hour to keep optional API use within typical free quotas.
        query = ROLE_QUERIES[int(NOW.strftime("%H")) % len(ROLE_QUERIES)]
        for where in ("Pune", "India"):
            params = urllib.parse.urlencode({"app_id": app_id, "app_key": key, "results_per_page": 50, "what": query, "where": where, "sort_by": "date"})
            payload = fetch_json("https://api.adzuna.com/v1/api/jobs/in/search/1?" + params)
            jobs.extend(filter(None, (normalize(x, "Adzuna") for x in payload.get("results", []))))
        return jobs, "Adzuna", "ok"
    except Exception as exc:
        return jobs, "Adzuna", "error: " + str(exc)[:220]

def collect_arbeitnow():
    try:
        payload = fetch_json("https://www.arbeitnow.com/api/job-board-api")
        jobs = [normalize({**x, "posted_at": x.get("created_at")}, "Arbeitnow") for x in payload.get("data", [])]
        return list(filter(None, jobs)), "Arbeitnow", "ok"
    except Exception as exc:
        return [], "Arbeitnow", "error: " + str(exc)[:220]

def collect_remotive():
    try:
        payload = fetch_json("https://remotive.com/api/remote-jobs?limit=500")
        jobs = [normalize({**x, "location": x.get("candidate_required_location") or "Remote", "posted_at": x.get("publication_date"), "tags": [x.get("category", "")]}, "Remotive") for x in payload.get("jobs", [])]
        return list(filter(None, jobs)), "Remotive", "ok"
    except Exception as exc:
        return [], "Remotive", "error: " + str(exc)[:220]

def match(job):
    text = " ".join([job["title"], job["description"], " ".join(job["tags"])]).lower()
    skills = [s for s in SKILLS if re.search(r"(?<!\w)" + re.escape(s) + r"(?!\w)", text, re.I)]
    role_score = 25
    junior = bool(re.search(r"fresher|entry.level|graduate|trainee|junior|associate|0\s*(?:-|to)\s*2", text, re.I))
    years = re.search(r"(\d+)\+?\s*years?", job["experience"], re.I)
    exp_score = 20 if junior or not years else max(0, 18 - int(years.group(1)) * 7)
    loc_scores = {0: 20, 1: 16, 2: 12, 3: 10, 9: 0}
    age = parse_date(job.get("posted_at"))
    age_hours = max(0, (NOW - age).total_seconds() / 3600) if age else None
    if age_hours is None:
        freshness = 0
    elif age_hours <= 1:
        freshness = 15
    elif age_hours <= 6:
        freshness = 13
    elif age_hours <= 24:
        freshness = 11
    else:
        freshness = max(0, 10 - int((age_hours - 24) / 24) * 2)
    skill_score = min(30, len(skills) * 6)
    score = min(100, skill_score + role_score + exp_score + loc_scores[location_rank(job["location"], job["remote"])] + freshness)
    missing = [s for s in SKILLS if s not in skills][:6]
    why = []
    if skills: why.append("Skill overlap: " + ", ".join(skills[:6]))
    why.append("Relevant role category: " + job["category"])
    if junior: why.append("Entry-level wording found in listing")
    if location_rank(job["location"], job["remote"]) <= 1: why.append("Preferred location")
    job.update({"score": score, "priority": "Apply First" if score >= 75 else "Good Match" if score >= 55 else "Stretch Role",
                "match_reason": "; ".join(why), "missing_skills": missing, "score_estimated": True})
    return job

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default

def deduplicate(listings):
    unique = {}
    for job in listings:
        key = normalize_url(job.get("url") or job.get("id"))
        if key:
            previous = unique.get(key)
            if previous is None or (job.get("score") or 0) > (previous.get("score") or 0):
                unique[key] = job
    return list(unique.values())

def main():
    prev = load_json(OUT, {"jobs": []})
    history = load_json(HISTORY_PATH, {})
    collectors = (collect_adzuna, collect_arbeitnow, collect_remotive)
    all_new, source_results = [], []
    for collector in collectors:
        rows, name, status = collector()
        source_results.append({"name": name, "status": status, "count": len(rows)})
        all_new.extend(rows)
    # If every feed failed or was skipped, preserve published data and timestamp of last success.
    successes = [s for s in source_results if s["status"] == "ok"]
    if not successes:
        prev["last_attempt_at"] = NOW.isoformat()
        prev["source_status"] = source_results
        prev["refresh_status"] = "error"
        OUT.write_text(json.dumps(prev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("No source succeeded; preserved existing job data")
        return
    current = {j.get("id") or normalize_url(j.get("url")): j for j in deduplicate(prev.get("jobs", []))
               if j.get("url") and india_eligible(j.get("location", ""), j.get("remote", False))}
    all_new = deduplicate(all_new)
    seen = history if isinstance(history, dict) else {}
    fresh_ids = set()
    for job in all_new:
        key = job["id"]
        old = current.get(key)
        if old:
            job["first_seen_at"] = old.get("first_seen_at", job["first_seen_at"])
        elif isinstance(seen.get(key), dict):
            historical = seen[key]
            job["first_seen_at"] = historical.get("first_seen_at", job["first_seen_at"])
        else:
            fresh_ids.add(key)
        current[key] = job
        seen.setdefault(key, {"first_seen_at": job["first_seen_at"], "title": job["title"], "company": job["company"], "url": job["url"]})
    for job in jobs_from_previous(prev):
        if not india_eligible(job.get("location", ""), job.get("remote", False)):
            continue
        key = job.get("id") or normalize_url(job.get("url"))
        if key:
            seen.setdefault(key, {"first_seen_at": job.get("first_seen_at") or NOW.isoformat(), "title": job.get("title", ""), "company": job.get("company", ""), "url": job.get("url", "")})
    cutoff = NOW - timedelta(days=MAX_AGE_DAYS)
    jobs=[]
    for job in current.values():
        posted = parse_date(job.get("posted_at"))
        first = parse_date(job.get("first_seen_at"))
        if posted and posted < cutoff and not any(s["status"] != "ok" and s["name"] == job.get("source") for s in source_results):
            continue
        if not posted and first and first < cutoff:
            continue
        jobs.append(match(job))
    jobs.sort(key=lambda j: (location_rank(j["location"], j["remote"]), -j["score"], j["title"].lower()))
    for key, val in list(seen.items()):
        when = parse_date(val.get("first_seen_at")) if isinstance(val, dict) else None
        if when and when < NOW - timedelta(days=HISTORY_DAYS):
            del seen[key]
    payload = {"status": "ok", "refresh_status": "ok" if len(successes) == len(source_results) else "partial",
               "updated_at": NOW.isoformat(), "last_successful_refresh_at": NOW.isoformat(),
               "last_attempt_at": NOW.isoformat(), "source_status": source_results,
               "sources": [s["name"] for s in successes], "new_count": len(fresh_ids),
               "message": "No new matches found; existing valid listings are retained." if not fresh_ids else f"{len(fresh_ids)} newly discovered matches.",
               "jobs": jobs[:500], "seen_jobs": list(seen.values()), "note": "Listings are unverified unless the source confirms current availability."}
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    HISTORY_PATH.write_text(json.dumps(seen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Refresh complete: {len(jobs)} listings, {len(fresh_ids)} new; {len(successes)}/{len(source_results)} sources succeeded")

def jobs_from_previous(payload):
    return payload.get("jobs", []) if isinstance(payload, dict) and isinstance(payload.get("jobs"), list) else []

if __name__ == "__main__":
    main()
