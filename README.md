# Kartik's Job Radar

A static, responsive job dashboard for early-career engineering opportunities. Python collects public feeds and scores listings; GitHub Actions runs the collector hourly, commits generated JSON, and deploys the site to GitHub Pages. No server or paid hosting is required.

## Repository map

- `index.html`, `styles.css`, `app.js`: accessible responsive dashboard and browser interactions.
- `data/profile.json`: editable skills, preferred locations, experience level, and target roles.
- `data/jobs.json`: generated published listings and refresh/source status.
- `data/seen.json`: 90-day listing history used to deduplicate discovery.
- `scripts/fetch_jobs.py`: fetch, normalize, filter, score, deduplicate, and retain listings.
- `.github/workflows/hourly-jobs.yml`: hourly/manual collect, commit, and Pages deployment.
- `tests/`: standard-library Python unit tests.

## Local use

Requires Python 3.10 or newer; the collector and tests use only the Python standard library.

```sh
python -m http.server 8000
```

Open `http://localhost:8000`. To refresh data locally, run `python scripts/fetch_jobs.py`; network access and optionally Adzuna credentials are needed. Run checks with `python -m unittest discover -s tests -v` and `python -m py_compile scripts/fetch_jobs.py`.

## GitHub Pages setup

1. Create or use a public GitHub repository and push this project to its default branch. Keep `.github/workflows/hourly-jobs.yml` at that exact path.
2. In **Settings → Pages**, choose **GitHub Actions** as the build and deployment source.
3. In **Settings → Actions → General → Workflow permissions**, allow **Read and write permissions** so the workflow can commit refreshed JSON and history.
4. Optional: create an Adzuna API application and add `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` as repository **Actions secrets** under **Settings → Secrets and variables → Actions**. `.env.example` documents the names; never commit actual credentials.
5. In **Actions → Refresh and deploy job dashboard**, choose **Run workflow**. The first run can take several minutes while it fetches feeds and deploys the site.
6. Open **Settings → Pages** for the published URL. The workflow deploys the checked-out site and generated JSON together, so a successful run publishes the newly generated data.

The dashboard's **Check for updates** button reloads the published feed. It cannot start a GitHub Actions workflow because GitHub requires a credential for workflow dispatch, and placing one in a public static site would expose it. Use **Actions → Run workflow** for an immediate collection.

## Sources and collection behavior

- Arbeitnow public job-board API.
- Remotive public remote-jobs API.
- Adzuna India API when both optional secrets exist. It rotates target-role queries hourly and checks Pune and India, limiting API usage compared with requesting every role every hour.

The collector uses timeouts and retries transient failures. It records each source's status and count. If all sources fail or are skipped, the previous job dataset and last successful refresh timestamp are preserved. When at least one source succeeds, valid prior listings remain available for up to 30 days; the seen history is retained for 90 days. Listings missing a posting date age out based on first discovery. Duplicate URLs are canonicalized by host/path, dropping query parameters and fragments.

Only Pune, Maharashtra, India-wide, and remote listings are considered. Senior/lead/principal listings and explicit 5+ year requirements are excluded. QA is an independent role category and is not suppressed by DevOps/cloud searching. A job with an unavailable posting date is marked as such in the dashboard. All source listings are labeled **Availability unverified** because feed inclusion alone does not establish that an employer still accepts applications. Salary appears only when supplied by the source.

Match scores are estimates based on role family, candidate skill overlap, entry-level wording, location, and posting freshness. The “potential skill gaps” section compares the listing text with the profile skills; gaps are not asserted job requirements. Edit `data/profile.json` to adjust the profile. The target-role list also drives Adzuna's rotating searches.

Saved jobs and application statuses (Interested, Applied, Interview, Rejected) use browser `localStorage`. They remain on that browser/profile only, do not synchronize across devices, and can be lost if browser storage is cleared. The application does not send applications or collect personal information.

## Free-tier and operational limits

- GitHub Pages and Actions availability/quotas depend on GitHub's current plan and repository settings.
- Scheduled workflows can be delayed and are not guaranteed to start exactly on the hour. GitHub may pause schedules in inactive repositories.
- Public feeds and Adzuna can change availability, API quotas, schemas, or terms. Adzuna results may be sparse without credentials. Check each provider's current terms before relying on it.
- A GitHub Pages static site cannot securely dispatch workflows without a server-side credential. Manual refresh is available in Actions; the dashboard button only fetches the latest published JSON.
- The collector makes no authenticated or restricted-site requests and does not bypass access controls.

## Troubleshooting

- **No jobs:** inspect the latest Actions logs and `source_status` in `data/jobs.json`. Public feeds may not have India-specific roles; configure Adzuna secrets for additional coverage.
- **Workflow cannot push:** enable workflow read/write permissions in repository settings.
- **Pages not publishing:** set Pages source to GitHub Actions and inspect the deploy step in Actions.
- **No hourly run:** confirm Actions is enabled and the workflow is on the default branch. Scheduled runs can be delayed.
- **Saved items missing:** browser-local data is not shared between devices and can be removed by clearing site storage.

## Checks

```sh
python -m unittest discover -s tests -v
python -m py_compile scripts/fetch_jobs.py
```
