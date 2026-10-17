import unittest
from datetime import datetime,timezone,timedelta
from office_runtime.scripts.run_editorial_publication_health import assess

HEADERS=["candidate_id","draft_editable","decision","editor_note","target_surface","publisher_status","scheduled_for","published_ref","updated_at","schema_version"]

class HealthTests(unittest.TestCase):
    now=datetime(2026,10,17,21,0,tzinfo=timezone.utc)

    def queue(self,decision="APPROVE",status="",hours=1):
        return [HEADERS,["cand:a","draft",decision,"","X",status,(self.now+timedelta(hours=hours)).isoformat(),"",""]]

    def test_scheduled_even_when_last_run_empty(self):
        runs=[["run_id","profile_id","started_at","finished_at","inventory_status","candidate_count"],["r1","dev","2026-10-17T15:00Z","","DEGRADED_INVENTORY","0"]]
        result=assess("dev",self.queue(),self.now,runs)
        self.assertEqual((result["state"],result["upstream"]),("SCHEDULED","UPSTREAM_EMPTY"))
        self.assertFalse(result["alert"])

    def test_empty_old_queue_requires_attention(self):
        result=assess("argentina_econ",[HEADERS],self.now)
        self.assertEqual(result["state"],"NO_ELIGIBLE_CONTENT")
        self.assertTrue(result["alert"])

    def test_awaiting_review_is_observable(self):
        result=assess("dev",self.queue(decision="REVIEW"),self.now)
        self.assertEqual(result["state"],"AWAITING_APPROVAL")
        self.assertEqual(result["review"],1)

    def test_recent_publication_is_counted(self):
        raw=[HEADERS,["cand:a","draft","APPROVE","","X","PUBLISHED","","https://x.com/example","2026-10-17T20:00:00Z"]]
        result=assess("argentina_econ",raw,self.now)
        self.assertEqual(result["state"],"PUBLISHED")
        self.assertFalse(result["alert"])

if __name__=="__main__":unittest.main()
