"""Bounded read-only workflows composed from the low-level Canvas tools."""
from collections import Counter
from datetime import timedelta
import re
import unicodedata
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

from .client import origin, valid_id
from .config import BridgeError
from .content import clean_url
from .dates import now_utc, optional_date


COMPLETED = {"submitted", "graded", "excused", "marked_complete"}


def submission_status(submission):
    if not isinstance(submission, dict):
        return "unknown"
    if submission.get("excused"):
        return "excused"
    state = submission.get("workflow_state")
    if state == "graded" and (submission.get("submitted_at") or not submission.get("missing")):
        return "graded"
    if submission.get("submitted_at") or state in ("submitted", "pending_review"):
        return "submitted"
    if submission.get("missing"):
        return "missing"
    if state in ("unsubmitted", "ungraded"):
        return "pending" if state == "unsubmitted" else "unknown"
    return "unknown"


def _coverage_entry(source, course_id=None, result=None, error=None):
    entry = {"source": source, "status": "error" if error else "ok"}
    if course_id is not None:
        entry["course_id"] = str(course_id)
    if error:
        entry["error"] = str(error)
    elif result is not None:
        entry.update({"count": result.get("count"), "truncated": bool(result.get("truncated")),
                      "partial": bool(result.get("partial"))})
        if result.get("query_range"):
            entry["query_range"] = result["query_range"]
        if result.get("warnings"):
            entry["warnings"] = result["warnings"]
    return entry


def _partial(coverage):
    return any(e["status"] != "ok" or e.get("truncated") or e.get("partial") for e in coverage)


def upcoming_work(service, days, course_ids, include_completed, overdue_days, limit):
    if not 1 <= days <= 90 or not 0 <= overdue_days <= 90 or not 1 <= limit <= 500:
        raise BridgeError("days 应为 1–90，overdue_days 应为 0–90，limit 应为 1–500。")
    if course_ids is not None:
        if not isinstance(course_ids, list) or not 1 <= len(course_ids) <= 50:
            raise BridgeError("course_ids 必须是包含 1–50 个课程 ID 的列表。")
        course_ids = list(dict.fromkeys(valid_id(cid) for cid in course_ids))
    coverage = []
    try:
        roster = service.list_courses(limit=1000)
        coverage.append(_coverage_entry("courses", result=roster))
    except BridgeError as error:
        if course_ids is None:
            raise
        roster = {"items": []}
        coverage.append(_coverage_entry("courses", error=error))
    names = {str(c["id"]): c.get("name") for c in roster["items"]}
    selected = course_ids if course_ids is not None else list(names)
    if len(selected) > 50:
        selected = selected[:50]
        coverage.append({"source": "course_selection", "status": "ok", "truncated": True})
    zone = service.settings.timezone
    now = now_utc()
    today = now.astimezone(ZoneInfo(zone)).replace(hour=0, minute=0, second=0, microsecond=0)
    start, end = today - timedelta(days=overdue_days), today + timedelta(days=days)
    records = {}
    warnings = ["仅汇总 Canvas 结构化任务；公告、课件正文或外部平台中的任务仍需另外核对。",
                "无截止时间的作业放在 undated_items；手动标记完成不代表已提交。"]

    for cid in selected:
        try:
            result = service.list_assignments(cid, limit=1000)
            coverage.append(_coverage_entry("assignments", cid, result))
            for item in result["items"]:
                aid = str(item["id"])
                records[(cid, "assignment", aid)] = {
                    "id": aid, "course_id": cid, "course_name": names.get(cid),
                    "kind": "assignment", "title": item.get("name"), "due_at": item.get("due_at"),
                    "due_at_local": service._local_date(item.get("due_at")),
                    "status": submission_status(item.get("submission")), "submission": item.get("submission"),
                    "html_url": item.get("html_url"), "locked_for_user": item.get("locked_for_user"),
                    "sources": ["assignments"], "marked_complete": False,
                }
        except BridgeError as error:
            coverage.append(_coverage_entry("assignments", cid, error=error))

    if selected:
        try:
            planner = service.client.list("/api/v1/planner/items", {
                "start_date": start.isoformat(), "end_date": end.isoformat(),
                "context_codes[]": ["course_" + cid for cid in selected]}, limit=1000)
            coverage.append(_coverage_entry("planner", result=planner))
            for raw in planner["items"]:
                cid = str(raw.get("course_id") or "")
                if cid not in selected:
                    continue
                data = raw.get("plannable") or {}
                kind = str(raw.get("plannable_type") or "unknown").lower()
                if kind == "announcement":
                    continue
                aid = data.get("assignment_id") or (raw.get("plannable_id") if kind == "assignment" else None)
                key = (cid, "assignment" if aid else kind, str(aid or raw.get("plannable_id") or data.get("id")))
                flags = raw.get("submissions")
                override = raw.get("planner_override") or {}
                status = "unknown"
                if isinstance(flags, dict):
                    if flags.get("excused"):
                        status = "excused"
                    elif flags.get("submitted"):
                        status = "submitted"
                    elif flags.get("missing"):
                        status = "missing"
                    elif flags.get("graded"):
                        status = "graded"
                    elif flags.get("submitted") is False:
                        status = "pending"
                if status == "unknown" and override.get("marked_complete"):
                    status = "marked_complete"
                if kind in ("calendar_event", "planner_note") and status == "unknown":
                    status = "scheduled" if kind == "calendar_event" else "planned"
                due = data.get("due_at") or raw.get("plannable_date") or data.get("todo_date") or data.get("start_at")
                if key in records:
                    item = records[key]
                    item["sources"].append("planner")
                    item["marked_complete"] = bool(override.get("marked_complete"))
                    if item["status"] == "unknown" and status != "unknown":
                        item["status"] = status
                    # An explicit assignment due_at=null is authoritative. Planner
                    # dates can be "to-do" dates rather than submission deadlines.
                    if due and item["due_at"] and optional_date(due, zone) != optional_date(item["due_at"], zone):
                        item["planner_date"] = due
                        item["date_conflict"] = True
                else:
                    records[key] = {
                        "id": key[2], "course_id": cid, "course_name": names.get(cid),
                        "kind": key[1], "title": data.get("title") or data.get("name"),
                        "due_at": due, "due_at_local": service._local_date(due), "status": status,
                        "submission": None, "planner_submission_flags": flags if isinstance(flags, dict) else None,
                        "html_url": clean_url(raw.get("html_url") or "", service.settings.base_url),
                        "sources": ["planner"], "marked_complete": bool(override.get("marked_complete")),
                    }
        except BridgeError as error:
            coverage.append(_coverage_entry("planner", error=error))

    dated, undated = [], []
    for item in records.values():
        due = optional_date(item["due_at"], zone)
        if item["due_at"] and due is None:
            item["date_warning"] = "截止时间无法解析。"
        if due:
            if not start <= due < end:
                continue
            item["deadline_passed"] = due < now
            if item["status"] == "pending" and due < now:
                item["status"] = "overdue"
            if item["status"] in ("scheduled", "planned") and due < now:
                continue
        else:
            item["deadline_passed"] = None
        if not include_completed and item["status"] in COMPLETED:
            continue
        (dated if due else undated).append(item)
    dated.sort(key=lambda item: (optional_date(item["due_at"], zone), item["course_id"], item["id"]))
    undated.sort(key=lambda item: (item["course_id"], item["title"] or "", item["id"]))
    total = len(dated) + len(undated)
    returned = dated[:limit]
    returned_undated = undated[:max(0, limit - len(returned))]
    truncated = total > limit or any(e.get("truncated") for e in coverage)
    return service._result("/api/v1/planner/items", items=returned, undated_items=returned_undated,
        count=len(returned) + len(returned_undated), matched_count=total,
        summary=dict(Counter(i["status"] for i in returned + returned_undated)),
        undated_matched_count=len(undated), query_range={"start": start.isoformat(), "end": end.isoformat(),
            "end_exclusive": True, "days": days, "overdue_days": overdue_days},
        include_completed=include_completed, course_ids=selected, coverage=coverage,
        partial=_partial(coverage) or truncated, truncated=truncated, warnings=warnings)


def assignment_context(service, course_id, assignment_id, max_related, read_attachments, announcement_start_date):
    cid, aid = valid_id(course_id), valid_id(assignment_id)
    if not 1 <= max_related <= 10:
        raise BridgeError("max_related 应为 1–10。")
    assignment = service.get_assignment(cid, aid)["assignment"]
    coverage = [_coverage_entry("assignment", cid)]
    warnings = ["同模块资料和名称匹配公告属于候选参考资料，不代表老师指定的必读材料。"]
    files, pages, external_links, modules, announcements = {}, {}, [], [], []
    base = service.settings.base_url

    def discover(links, relationship, source):
        for link in links:
            parsed = urlsplit(link)
            if origin(link) != origin(base):
                if link not in external_links:
                    external_links.append(link)
                continue
            file_match = re.search(r"/files/([1-9][0-9]*)(?:/|$)", parsed.path)
            page_match = re.fullmatch(r"/courses/" + cid + r"/pages/([^/]+)", parsed.path)
            evidence = {"relationship": relationship, "source_url": source}
            if file_match:
                fid = file_match[1]
                files.setdefault(fid, {"id": fid, "evidence": []})["evidence"].append(evidence)
            elif page_match:
                slug = unquote(page_match[1])
                pages.setdefault(slug, {"page_url": slug, "evidence": []})["evidence"].append(evidence)

    assignment_url = assignment.get("html_url") or base + f"/courses/{cid}/assignments/{aid}"
    discover(assignment.get("description", {}).get("links", []), "assignment_link", assignment_url)
    try:
        result = service.list_announcements(cid, limit=100, start_date=announcement_start_date)
        coverage.append(_coverage_entry("announcements", cid, result))
        phrase = unicodedata.normalize("NFKC", assignment.get("name") or "").casefold().strip()
        for item in result["items"]:
            content = item.get("content") or {}
            links = content.get("links", [])
            direct = any(origin(link) == origin(base) and urlsplit(link).path.rstrip("/") ==
                         f"/courses/{cid}/assignments/{aid}" for link in links)
            text = unicodedata.normalize("NFKC", (item.get("title") or "") + " " + content.get("text", "")).casefold()
            if direct or (len(phrase) >= 4 and phrase in text):
                relationship = "assignment_link" if direct else "title_match_candidate"
                announcements.append({**item, "relationship": relationship})
                if direct:
                    discover(links, "linked_announcement", item.get("html_url") or result["source_url"])
        announcements.sort(key=lambda item: (item["relationship"] != "assignment_link", item.get("posted_at") or ""))
    except BridgeError as error:
        coverage.append(_coverage_entry("announcements", cid, error=error))

    try:
        result = service.list_modules(cid, limit=10)
        coverage.append(_coverage_entry("modules", cid, result))
        for module in result["items"]:
            try:
                items = service.list_module_items(cid, module["id"], limit=200)
                coverage.append(_coverage_entry("module_items:" + str(module["id"]), cid, items))
                if not any(i.get("type") == "Assignment" and str(i.get("content_id")) == aid for i in items["items"]):
                    continue
                siblings = [i for i in items["items"] if i.get("type") in ("File", "Page", "ExternalUrl", "ExternalTool")]
                modules.append({"id": module["id"], "name": module.get("name"),
                                "relationship": "same_module_candidate", "items": siblings[:max_related],
                                "truncated": len(siblings) > max_related or items["truncated"]})
                source = base + f"/courses/{cid}/modules/{module['id']}"
                for item in siblings:
                    if item.get("type") == "File" and item.get("content_id"):
                        fid = valid_id(item["content_id"])
                        files.setdefault(fid, {"id": fid, "evidence": []})["evidence"].append(
                            {"relationship": "same_module_candidate", "source_url": source})
                    if item.get("type") == "Page" and item.get("page_url"):
                        slug = item["page_url"]
                        pages.setdefault(slug, {"page_url": slug, "evidence": []})["evidence"].append(
                            {"relationship": "same_module_candidate", "source_url": source})
            except BridgeError as error:
                coverage.append(_coverage_entry("module_items:" + str(module["id"]), cid, error=error))
    except BridgeError as error:
        coverage.append(_coverage_entry("modules", cid, error=error))

    def direct(item):
        return any(e["relationship"] != "same_module_candidate" for e in item["evidence"])

    page_results = []
    page_candidates = sorted(pages.values(), key=lambda item: not direct(item))
    for item in page_candidates[:max_related]:
        entry = dict(item)
        if direct(item):
            try:
                result = service.get_page(cid, item["page_url"])
                entry.update(page=result["page"], content=result["content"], read_status="read")
                source = base + f"/courses/{cid}/pages/{item['page_url']}"
                discover(result["content"]["links"], "linked_page", source)
                coverage.append(_coverage_entry("page:" + item["page_url"], cid))
            except BridgeError as error:
                entry.update(read_status="unavailable", error=str(error))
                coverage.append(_coverage_entry("page:" + item["page_url"], cid, error=error))
        else:
            entry["read_status"] = "candidate_not_read"
        page_results.append(entry)

    attachments = []
    candidates = sorted(files.values(), key=lambda item: not direct(item))
    for item in candidates[:max_related]:
        entry = dict(item)
        try:
            if read_attachments:
                preview = service.read_material(item["id"], count=2, max_chars=5000)
                entry.update(file=preview["file"], preview=preview, read_status="preview")
            else:
                data, _ = service.client.get("/api/v1/files/" + item["id"])
                entry.update(file=service._file(data), read_status="metadata_only")
            coverage.append(_coverage_entry("file:" + item["id"], cid))
        except BridgeError as error:
            entry.update(read_status="unavailable", error=str(error))
            coverage.append(_coverage_entry("file:" + item["id"], cid, error=error))
        attachments.append(entry)

    truncated = (len(external_links) > max_related or len(candidates) > max_related or len(page_candidates) > max_related or
                 len(announcements) > max_related or any(m["truncated"] for m in modules) or
                 any(e.get("truncated") for e in coverage))
    missing = []
    if not assignment.get("description", {}).get("text"):
        missing.append("作业正文没有可提取的文字，可能仅包含图片或外部链接。")
    if not assignment.get("rubric"):
        missing.append("API 未提供评分标准；评分标准可能位于附件或其他课程材料。")
    if not assignment.get("due_at"):
        missing.append("API 未提供截止时间；需核对公告、附件或外部教学平台。")
    if not read_attachments and attachments:
        warnings.append("附件仅核对元数据，尚未读取正文；可设置 read_attachments=true 获取前两页预览。")
    if read_attachments and attachments:
        warnings.append("附件仅预览前两页或幻灯片，不代表全文；请按 preview.next_cursor 继续读取。")
    if truncated:
        warnings.append("关联检索达到上限，请参考 coverage 并使用底层工具继续查询。")
    return service._result(f"/api/v1/courses/{cid}/assignments/{aid}", assignment=assignment,
        attachments=attachments, related_pages=page_results, related_modules=modules,
        related_announcements=announcements[:max_related], external_links=external_links[:max_related],
        attachment_candidates_found=len(candidates), coverage=coverage, missing_information=missing,
        partial=_partial(coverage) or truncated, truncated=truncated, warnings=warnings)
