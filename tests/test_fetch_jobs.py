import unittest
from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from scripts import fetch_jobs as jobs


class JobNormalizationTests(unittest.TestCase):
    def test_unix_seconds_and_milliseconds_are_parsed(self):
        seconds = jobs.parse_date(1792004444)
        millis = jobs.parse_date(1792004444000)
        self.assertEqual(seconds, millis)
        self.assertEqual(seconds.tzinfo, timezone.utc)

    def test_url_normalization_removes_tracking_and_host_variants(self):
        self.assertEqual(jobs.normalize_url("http://www.example.com/jobs/1/?utm=abc#apply"), "https://example.com/jobs/1")

    def test_application_url_preserves_query_parameters(self):
        url = "https://example.com/apply?id=abc&token=xyz#form"
        self.assertEqual(jobs.safe_application_url(url), "https://example.com/apply?id=abc&token=xyz")

    def test_remote_jobs_restricted_to_other_regions_are_filtered(self):
        row = {"title":"Remote Junior DevOps Engineer", "company":"Example", "location":"Remote",
               "candidate_required_location":"United States only", "remote":True,
               "url":"https://example.com/jobs/remote", "description":"AWS Linux"}
        self.assertIsNone(jobs.normalize(row, "Test"))

    def test_duplicate_urls_keep_the_higher_scored_listing(self):
        rows = [{"url":"https://www.example.com/job/1?source=a", "score":42},
                {"url":"https://example.com/job/1#apply", "score":70}]
        result = jobs.deduplicate(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["score"], 70)

    def test_qa_is_kept_as_its_own_role_category(self):
        row = {"title":"Junior QA Engineer", "company":"Example", "location":"Pune, India",
               "url":"https://example.com/jobs/qa-1", "description":"Manual software testing, fresher"}
        result = jobs.normalize(row, "Test")
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "QA / Testing")

    def test_senior_and_out_of_region_jobs_are_filtered(self):
        base = {"company":"Example", "location":"London", "url":"https://example.com/1", "description":"AWS"}
        self.assertIsNone(jobs.normalize({**base, "title":"Senior DevOps Engineer"}, "Test"))
        self.assertIsNone(jobs.normalize({**base, "title":"Junior DevOps Engineer"}, "Test"))

    def test_matching_explains_score_and_gaps(self):
        row = {"id":"https://example.com/1", "title":"Junior Linux Support Engineer", "company":"A",
               "location":"Pune", "remote":False, "experience":"Fresher", "description":"Linux AWS EC2 SSH",
               "posted_at":jobs.NOW.isoformat(), "salary":None, "tags":[], "skills":[], "category":"Support / NOC / SRE",
               "source":"test", "url":"https://example.com/1", "status":"unverified", "first_seen_at":jobs.NOW.isoformat()}
        result = jobs.match(row)
        self.assertGreaterEqual(result["score"], 75)
        self.assertEqual(result["priority"], "Apply First")
        self.assertIn("Linux", result["match_reason"])
        self.assertTrue(result["missing_skills"])

    def test_all_source_failures_preserve_published_jobs(self):
        original = {"status":"ok", "updated_at":"2026-01-01T00:00:00+00:00", "jobs":[{"url":"https://example.com/job"}]}
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "jobs.json"
            history = Path(tmp) / "seen.json"
            output.write_text(json.dumps(original), encoding="utf-8")
            failure = lambda: ([], "Mock", "error: offline")
            with patch.object(jobs, "OUT", output), patch.object(jobs, "HISTORY_PATH", history), \
                 patch.object(jobs, "NOW", jobs.NOW), patch.object(jobs, "collect_adzuna", failure), \
                 patch.object(jobs, "collect_arbeitnow", failure), patch.object(jobs, "collect_remotive", failure):
                jobs.main()
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["jobs"], original["jobs"])
            self.assertEqual(result["updated_at"], original["updated_at"])
            self.assertEqual(result["refresh_status"], "error")

    def test_historically_seen_listing_is_not_counted_as_new_again(self):
        first_seen = "2026-10-01T00:00:00+00:00"
        listing = jobs.normalize({"title":"Junior DevOps Engineer", "company":"Example", "location":"Pune",
                                  "url":"https://example.com/jobs/1", "description":"Linux AWS",
                                  "posted_at":jobs.NOW.isoformat()}, "Mock")
        listing["first_seen_at"] = first_seen
        with TemporaryDirectory() as tmp:
            output, history_path = Path(tmp)/"jobs.json", Path(tmp)/"seen.json"
            output.write_text(json.dumps({"jobs": []}), encoding="utf-8")
            history_path.write_text(json.dumps({listing["id"]:{"first_seen_at":first_seen,"title":listing["title"],"company":listing["company"],"url":listing["url"]}}), encoding="utf-8")
            ok = lambda: ([listing], "Mock", "ok")
            fail = lambda: ([], "Other", "error: offline")
            with patch.object(jobs, "OUT", output), patch.object(jobs, "HISTORY_PATH", history_path), \
                 patch.object(jobs, "collect_adzuna", ok), patch.object(jobs, "collect_arbeitnow", fail), \
                 patch.object(jobs, "collect_remotive", fail):
                jobs.main()
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["new_count"], 0)
            self.assertEqual(result["jobs"][0]["first_seen_at"], first_seen)


if __name__ == "__main__":
    unittest.main()
