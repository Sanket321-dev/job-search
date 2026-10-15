import json, os, re, html, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/jobs.json")
NOW = datetime.now(timezone.utc)
TARGETS = [
    "junior devops", "devops engineer", "cloud support", "aws support",
    "azure support", "linux administrator", "system administrator",
    "qa engineer", "qa tester", "software tester", "test engineer",
    "technical support", "noc engineer", "site reliability", "sre",
    "platform engineer", "cloud engineer", "associate cloud"
]
SKILL_WORDS = ["linux", "aws", "azure", "docker", "terraform", "jenkins", "git",
               "ci/cd", "cloudwatch", "rhel", "red hat", "qa", "testing", "sql",
               "network", "support", "devops", "sre", "prometheus", "nagios"]
PUNE_WORDS = ["pune", "pimpri", "chinchwad", "maharashtra"]
INDIA_WORDS = ["india", "bengaluru", "bangalore", "hyderabad", "chennai",
               "mumbai", "nashik", "nagpur", "gurugram", "gurgaon", "noida", "delhi"]
EARLY_WORDS = ["fresher", "entry level", "entry-level", "junior", "graduate",
               "associate", "0-2 years", "0 to 2 years", "1 year", "trainee", "intern"]

def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent":"KartikJobRadar/1.0 contact: repository owner", **(headers or {})})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def clean(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def score_job(title, company, location, desc, tags):
    text = " ".join([title, company, location, desc, " ".join(tags)]).lower()
    score = 28
    skill_hits = [x for x in SKILL_WORDS if x in text]
    score += min(30, len(skill_hits) * 5)
    if any(x in text for x in PUNE_WORDS): score += 22
    elif any(x in text for x in INDIA_WORDS) or "remote" in text: score += 12
    if any(x in text for x in EARLY_WORDS): score += 12
    if any(x in text for x in ["senior", "lead ", "principal", "staff engineer", "5+ years", "8+ years"]): score -= 25
    if any(x in text for x in ["devops", "cloud", "linux", "quality assurance", " qa ", "testing", "support", "sre", "noc"]): score += 8
    score = max(15, min(98, score))
    reason = "Relevant keywords: " + (", ".join(skill_hits[:5]) if skill_hits else "role-family match")
    gaps = "Confirm hands-on requirements and experience level"
    return score, reason, gaps

def normalize(title, company, location, url, description="", posted=None, tags=None, experience=None, remote=False):
    title, company, location = clean(title), clean(company), clean(location)
    description = clean(description)[:650]
    tags = [clean(x) for x in (tags or []) if clean(x)]
    url = str(url or "").strip()
    if not title or not url or not url.startswith("http"): return None
    txt = (title + " " + description + " " + " ".join(tags)).lower()
    if not any(k in txt for k in ["devops", "cloud", "aws", "azure", "linux", "sysadmin",
                                  "system administrator", "quality assurance", " qa ", "tester",
                                  "testing", "technical support", "noc", "site reliability", "sre",
                                  "platform engineer", "network support"]):
        return None
    if not (any(x in (location + " " + description).lower() for x in PUNE_WORDS + INDIA_WORDS)
            or remote or "remote" in location.lower()):
        return None
    score, reason, gaps = score_job(title, company, location, description, tags)
    exp = experience or ("Early career mentioned" if any(x in txt for x in EARLY_WORDS) else "Check listing")
    return {"title":title, "company":company or "Company not listed", "location":location or ("Remote" if remote else "Location not specified"),
            "url":url, "description":description, "posted_at":posted, "tags":tags[:8],
            "experience":clean(exp), "score":score, "match_reason":reason, "missing_skills":gaps,
            "remote":bool(remote)}

def fetch_adzuna():
    app_id, key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not app_id or not key: return [], "Adzuna skipped (API secrets not configured)"
    out=[]
    # Adzuna India API supports location and keyword queries; keep requests modest for free-tier limits.
    for where, what in [("Pune", "junior devops OR cloud OR linux"), ("India", "fresher QA OR software testing OR technical support")]:
        params=urllib.parse.urlencode({"app_id":app_id,"app_key":key,"results_per_page":50,"what":what,"where":where,"content-type":"application/json","sort_by":"date"})
        try:
            data=get_json("https://api.adzuna.com/v1/api/jobs/in/search/1?"+params)
            for x in data.get("results",[]):
                loc=x.get("location",{}).get("display_name","")
                item=normalize(x.get("title"), x.get("company",{}).get("display_name",""), loc,
                    x.get("redirect_url"), x.get("description",""), x.get("created"), [what],
                    remote="remote" in loc.lower())
                if item: out.append(item)
        except Exception as e: print("Adzuna request failed:", str(e)[:200])
    return out, "Adzuna API"

def fetch_arbeitnow():
    out=[]
    try:
        data=get_json("https://www.arbeitnow.com/api/job-board-api")
        rows=data.get("data",[]) if isinstance(data,dict) else []
        for x in rows:
            tags=x.get("tags") or []
            item=normalize(x.get("title"), x.get("company_name"), x.get("location"),
                x.get("url"), x.get("description",""), x.get("created_at"), tags,
                remote=x.get("remote",False))
            if item: out.append(item)
        return out, "Arbeitnow public API"
    except Exception as e:
        print("Arbeitnow request failed:", str(e)[:200])
        return [], "Arbeitnow unavailable"

def fetch_remotive():
    out=[]
    try:
        data=get_json("https://remotive.com/api/remote-jobs?limit=100")
        for x in data.get("jobs",[]):
            item=normalize(x.get("title"), x.get("company_name"), x.get("candidate_required_location") or "Remote",
                x.get("url"), x.get("description",""), x.get("publication_date"), [x.get("category","")],
                remote=True)
            if item: out.append(item)
        return out, "Remotive remote API"
    except Exception as e:
        print("Remotive request failed:", str(e)[:200])
        return [], "Remotive unavailable"

def main():
    jobs=[]; sources=[]
    for fn in (fetch_adzuna, fetch_arbeitnow, fetch_remotive):
        items, source=fn(); sources.append(source); jobs.extend(items)
    # Deduplicate on canonical URL and title/company combination.
    unique={}
    for j in jobs:
        key=re.sub(r"[?#].*$","",j["url"]).rstrip("/").lower()
        if key not in unique or j["score"]>unique[key]["score"]: unique[key]=j
    jobs=list(unique.values())
    # Pune-first and higher-fit first.
    jobs.sort(key=lambda j: (not any(x in j["location"].lower() for x in PUNE_WORDS), -j["score"], j["title"].lower()))
    # Cap output to keep dashboard fast and avoid publishing low-relevance noise.
    jobs=jobs[:250]
    payload={"status":"ok" if jobs else "empty","updated_at":NOW.isoformat(),"sources":sources,"jobs":jobs,
             "note":"Availability is not guaranteed; confirm each opening on its source page."}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Wrote {len(jobs)} deduplicated matches from {', '.join(sources)}")

if __name__=="__main__": main()
