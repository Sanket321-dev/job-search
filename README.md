# Kartik's Hourly Job Dashboard

A static, GitHub Pages dashboard with a GitHub Actions workflow that refreshes `data/jobs.json` hourly. Designed for Pune-first early-career roles: DevOps, Cloud/AWS/Azure, Linux/System Administration, Technical Support, SRE/NOC, QA and testing.

## What it does

- Publishes a responsive job dashboard on GitHub Pages.
- Runs the job-fetch script hourly (`0 * * * *`) and also supports manual runs.
- Deduplicates results, estimates a resume fit score, and prioritizes Pune / nearby Maharashtra.
- Uses two no-key public feeds (Arbeitnow and Remotive) plus optional Adzuna for broader India/Pune coverage.
- Keeps job data in a public JSON file; **never put API keys in source files**.

## Setup on GitHub

1. Create a new **public** repository, e.g. `kartik-hourly-job-dashboard`.
2. Upload all files/folders from this ZIP to the repository's root (not the ZIP file itself). Keep `.github/workflows/hourly-jobs.yml` in place.
3. Open **Settings → Pages**. Under **Build and deployment → Source**, select **GitHub Actions**.
4. Optional but recommended for Pune/India coverage: register for an Adzuna API account and add the credentials at **Settings → Secrets and variables → Actions → New repository secret**:
   - `ADZUNA_APP_ID`
   - `ADZUNA_APP_KEY`
   The dashboard works without these, but Pune/India-specific results may be sparse because the no-key feeds focus on remote/global jobs. API availability and free-tier terms are controlled by the provider.
5. Go to **Actions → Refresh job dashboard → Run workflow** to trigger the first refresh. Approve Actions if GitHub asks.
6. When deployment completes, open **Settings → Pages** for the published URL. It is usually `https://YOUR-USERNAME.github.io/REPOSITORY-NAME/`.
7. Wait for the workflow to complete. The page shows the last refresh timestamp and the number of matching listings.

## Free-tier notes

- GitHub Pages and GitHub Actions have free usage for eligible public repositories, subject to GitHub's current limits.
- Scheduled workflows are not guaranteed to start at the exact minute and may be delayed. GitHub can disable scheduled workflows in inactive repositories.
- Job APIs may have rate limits, availability changes, or terms that limit how results can be reused. Review the providers' current terms.
- A source listing is not a guarantee the job is still open. Always verify on the source/employer page.
- This project does not apply to jobs, email recruiters, or collect personal data.

## Data sources

- Adzuna API (optional): https://developer.adzuna.com/
- Arbeitnow public API: https://www.arbeitnow.com/api/job-board-api
- Remotive remote jobs API: https://remotive.com/api/remote-jobs

## Troubleshooting

- **No jobs found:** add Adzuna secrets; check Actions logs; try again later. Public feeds may not have Pune-based jobs.
- **No website URL:** check Settings → Pages and the latest workflow run.
- **No hourly refresh:** check Actions is enabled and the workflow completed. GitHub scheduled jobs can be delayed.
- **Workflow can't push data:** ensure repository Actions permissions allow read and write (`Settings → Actions → General → Workflow permissions → Read and write permissions`).

## Personalization

The fit scoring is a lightweight keyword heuristic, not an AI assessment or hiring prediction. Review requirements before applying. Change target terms and skills in `scripts/fetch_jobs.py` to refine matching.
