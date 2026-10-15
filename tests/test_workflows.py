from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from canvas_bridge.config import BridgeError, Settings
from canvas_bridge.service import CanvasService
from canvas_bridge.workflows import submission_status


NOW = datetime(2026, 10, 15, 8, tzinfo=timezone.utc)


def listing(items, truncated=False):
    return {"items": items, "count": len(items), "truncated": truncated}


def assignment(aid, due="2026-10-16T15:59:00Z", state="unsubmitted", **submission):
    return {"id": str(aid), "name": "Task " + str(aid), "due_at": due,
            "html_url": f"https://canvas.example.edu/courses/1/assignments/{aid}",
            "submission": {"workflow_state": state, **submission} if state else None}


class UpcomingTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.service = CanvasService(Settings("https://canvas.example.edu", "fake-token"), self.client)
        self.service.list_courses = Mock(return_value=listing([{"id": "1", "name": "Course One"}, {"id": "2", "name": "Course Two"}]))
        self.service.list_assignments = Mock(return_value=listing([]))
        self.client.list.return_value = listing([])
        self.clock = patch("canvas_bridge.workflows.now_utc", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_deduplication_and_authoritative_submission(self):
        self.service.list_assignments.side_effect = [listing([assignment(10, state="graded", submitted_at="2026-10-14T08:00:00Z")]),
                                                    listing([assignment(10)])]
        self.client.list.return_value = listing([{"course_id": "1", "plannable_type": "assignment", "plannable_id": "10",
            "plannable_date": "2026-10-16T15:59:00Z", "plannable": {"title": "Task 10"}, "submissions": {"submitted": False}}])
        value = self.service.get_upcoming_work(include_completed=True)
        self.assertEqual(value["count"], 2)
        first = next(i for i in value["items"] if i["course_id"] == "1")
        self.assertEqual(first["status"], "graded")
        self.assertEqual(first["sources"], ["assignments", "planner"])
        params = self.client.list.call_args.args[1]
        self.assertEqual(params["start_date"], "2026-10-08T00:00:00+08:00")
        self.assertEqual(params["end_date"], "2026-10-29T00:00:00+08:00")

    def test_unknown_is_not_unsubmitted_and_manual_completion_is_distinct(self):
        items = [assignment(1, due="2026-10-14T08:00:00Z"),
                 assignment(2, due="2026-10-14T08:00:00Z", state=None),
                 assignment(3, state="submitted"), assignment(4, state="graded", missing=True), assignment(5)]
        self.service.list_assignments.return_value = listing(items)
        self.client.list.return_value = listing([{"course_id": "1", "plannable_type": "assignment", "plannable_id": "5",
            "plannable": {"title": "Task 5"}, "planner_override": {"marked_complete": True}, "submissions": False}])
        value = self.service.get_upcoming_work(course_ids=["1"])
        statuses = {i["id"]: i["status"] for i in value["items"]}
        self.assertEqual(statuses, {"1": "overdue", "2": "unknown", "4": "missing", "5": "pending"})
        self.assertTrue(next(i for i in value["items"] if i["id"] == "5")["marked_complete"])

    def test_boundary_dates_and_undated_assignment(self):
        self.service.list_assignments.return_value = listing([
            assignment(1, due="2026-10-28T15:59:59Z"), assignment(2, due="2026-10-28T16:00:00Z"),
            assignment(3, due=None), assignment(4, due="2026-10-07T15:59:59Z")])
        self.client.list.return_value = listing([{"course_id": "1", "plannable_type": "assignment", "plannable_id": "3",
            "plannable_date": "2026-10-17T08:00:00Z", "plannable": {"title": "Task 3"}}])
        value = self.service.get_upcoming_work(course_ids=["1"])
        self.assertEqual([i["id"] for i in value["items"]], ["1"])
        self.assertEqual([i["id"] for i in value["undated_items"]], ["3"])

    def test_permission_failure_and_truncation_remain_visible(self):
        self.service.list_assignments.side_effect = [listing([assignment(1)], truncated=True), BridgeError("HTTP 403：denied")]
        self.client.list.side_effect = BridgeError("HTTP 403：planner denied")
        value = self.service.get_upcoming_work()
        self.assertEqual(value["count"], 1)
        self.assertTrue(value["partial"])
        self.assertTrue(value["truncated"])
        self.assertEqual(sum(e["status"] == "error" for e in value["coverage"]), 2)

    def test_planner_quiz_and_complete_flag(self):
        self.client.list.return_value = listing([
            {"course_id": "1", "plannable_type": "quiz", "plannable_id": "42", "plannable_date": "2026-10-17T08:00:00Z",
             "plannable": {"title": "Quiz"}, "submissions": {"submitted": False}},
            {"course_id": "1", "plannable_type": "planner_note", "plannable_id": "43", "plannable_date": "2026-10-17T08:00:00Z",
             "plannable": {"title": "Read"}, "planner_override": {"marked_complete": True}}])
        value = self.service.get_upcoming_work(course_ids=["1"], include_completed=True)
        self.assertEqual({i["status"] for i in value["items"]}, {"pending", "marked_complete"})
        self.assertEqual(len(value["items"]), 2)

    def test_result_limit_does_not_hide_match_count(self):
        self.service.list_assignments.return_value = listing([assignment(1), assignment(2), assignment(3, due=None)])
        value = self.service.get_upcoming_work(course_ids=["1"], limit=1)
        self.assertEqual(value["count"], 1)
        self.assertEqual(value["matched_count"], 3)
        self.assertTrue(value["truncated"])

    def test_invalid_ranges_do_not_make_requests(self):
        for args in [{"days": 0}, {"overdue_days": -1}, {"course_ids": []}, {"course_ids": ["../1"]}]:
            with self.assertRaises(BridgeError):
                self.service.get_upcoming_work(**args)
        self.service.list_courses.assert_not_called()


class AnnouncementTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.service = CanvasService(Settings("https://canvas.example.edu", "fake-token"), self.client)
        self.client.list.return_value = listing([])

    def test_term_start_is_used_instead_of_two_week_api_default(self):
        self.client.get.return_value = ({"start_at": None, "term": {"start_at": "2026-09-01T00:00:00Z"}}, {})
        with patch("canvas_bridge.service.now_utc", return_value=NOW):
            value = self.service.list_announcements("1")
        params = self.client.list.call_args.args[1]
        self.assertEqual(params["start_date"], "2026-09-01T00:00:00+00:00")
        self.assertEqual(value["query_range"]["policy"], "term_start")

    def test_explicit_date_range_and_end_of_local_day(self):
        value = self.service.list_announcements("1", start_date="2026-09-01", end_date="2026-10-15")
        self.assertEqual(value["query_range"]["end"], "2026-10-15T23:59:59.999999+08:00")
        self.client.get.assert_not_called()
        with self.assertRaises(BridgeError):
            self.service.list_announcements("1", start_date="2026-10-16", end_date="2026-10-15")

    def test_missing_course_dates_report_fallback(self):
        self.client.get.side_effect = BridgeError("HTTP 403：denied")
        with patch("canvas_bridge.service.now_utc", return_value=NOW):
            value = self.service.list_announcements("1")
        self.assertEqual(value["query_range"]["policy"], "last_180_days_fallback")
        self.assertTrue(value["warnings"])
        self.assertEqual(value["count"], 0)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.base = "https://canvas.example.edu"
        self.client = Mock()
        self.service = CanvasService(Settings(self.base, "fake-token"), self.client)
        self.assignment = {**assignment(10), "name": "Group Report", "rubric": [{"description": "Analysis"}],
            "description": {"text": "Read the attachment", "links": [self.base + "/courses/1/files/42",
                self.base + "/courses/1/pages/instructions", "https://video.example/watch?v=abc"]}}
        self.service.get_assignment = Mock(return_value={"assignment": self.assignment})
        self.service.list_announcements = Mock(return_value={**listing([
            {"id": "100", "title": "Updated", "posted_at": "2026-09-15T08:00:00Z", "html_url": self.base + "/announcements/100",
             "content": {"text": "New attachment", "links": [self.base + "/courses/1/assignments/10", self.base + "/files/43"]}},
            {"id": "101", "title": "Group Report discussion", "content": {"text": "Candidate", "links": [self.base + "/files/44"]}},
            {"id": "102", "title": "Other course topic", "content": {"text": "Unrelated", "links": []}}]),
            "source_url": self.base + "/api/v1/announcements", "query_range": {"start": "2026-09-01", "end": "2026-10-15"}})
        self.service.list_modules = Mock(return_value=listing([{"id": "20", "name": "Projects"}, {"id": "21", "name": "Other"}]))
        self.service.list_module_items = Mock(side_effect=[listing([
            {"type": "Assignment", "content_id": "10"}, {"type": "File", "content_id": "45", "title": "Reference"},
            {"type": "File", "content_id": "42", "title": "Direct also in module"},
            {"type": "Page", "page_url": "reference", "title": "Background"}]),
            listing([{"type": "File", "content_id": "99", "title": "Unrelated file"}])])
        self.service.get_page = Mock(return_value={"page": {"title": "Instructions"},
            "content": {"text": "Details", "links": [self.base + "/files/46"]}})
        self.client.get.side_effect = lambda path: ({"id": path.rsplit("/", 1)[1], "filename": "data.pdf"}, {})

    def test_evidence_separates_direct_links_from_candidates(self):
        value = self.service.get_assignment_context("1", "10")
        ids = [f["id"] for f in value["attachments"]]
        self.assertEqual(ids, ["42", "43", "46", "45"])
        self.assertNotIn("44", ids)
        self.assertNotIn("99", ids)
        self.assertEqual(len(next(f for f in value["attachments"] if f["id"] == "42")["evidence"]), 2)
        self.assertEqual({a["relationship"] for a in value["related_announcements"]}, {"assignment_link", "title_match_candidate"})
        self.assertEqual(value["external_links"], ["https://video.example/watch?v=abc"])
        self.service.get_page.assert_called_once_with("1", "instructions")
        self.assertTrue(all(f["read_status"] == "metadata_only" for f in value["attachments"]))

    def test_attachment_failure_preserves_assignment_and_marks_partial(self):
        def metadata(path):
            if path.endswith("43"):
                raise BridgeError("HTTP 403：denied")
            return {"id": path.rsplit("/", 1)[1], "filename": "data.pdf"}, {}
        self.client.get.side_effect = metadata
        value = self.service.get_assignment_context("1", "10")
        self.assertEqual(value["assignment"]["id"], "10")
        self.assertTrue(value["partial"])
        self.assertEqual(next(f for f in value["attachments"] if f["id"] == "43")["read_status"], "unavailable")

    def test_preview_is_explicit_and_bounded(self):
        self.service.read_material = Mock(return_value={"file": {"id": "42"}, "units": [{"number": 1, "text": "preview"}],
                                                       "next_cursor": {"start": 3, "offset": 0}})
        value = self.service.get_assignment_context("1", "10", max_related=1, read_attachments=True)
        self.service.read_material.assert_called_once_with("42", count=2, max_chars=5000)
        self.assertEqual(value["attachments"][0]["read_status"], "preview")
        self.assertTrue(value["truncated"])
        self.assertTrue(any("前两页" in w for w in value["warnings"]))

    def test_optional_sources_and_missing_requirements_are_visible(self):
        self.assignment.update(due_at=None, rubric=[], description={"text": "", "links": []})
        self.service.list_announcements.side_effect = BridgeError("HTTP 403：denied")
        self.service.list_modules.side_effect = BridgeError("HTTP 403：denied")
        value = self.service.get_assignment_context("1", "10")
        self.assertEqual(len(value["missing_information"]), 3)
        self.assertTrue(value["partial"])
        self.assertEqual(value["attachments"], [])


if __name__ == "__main__":
    unittest.main()
