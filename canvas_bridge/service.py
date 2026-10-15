from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote
from zoneinfo import ZoneInfo

from .client import CanvasClient, valid_id
from .config import BridgeError, load_settings
from .content import clean_url, extract, html_content
from .dates import now_utc, optional_date, parse_date


def picked(data, *keys):
    return {key: data.get(key) for key in keys}


class CanvasService:
    def __init__(self, settings=None, client=None):
        self.settings = settings or load_settings()
        self.client = client or CanvasClient(self.settings)

    def _result(self, path, **values):
        result = {"source_url": clean_url(path, self.settings.base_url),
                  "fetched_at": datetime.now(timezone.utc).isoformat(),
                  "timezone": self.settings.timezone, **values}
        # A final boundary check prevents credentials from appearing in MCP/CLI responses.
        serialized = json.dumps(result, ensure_ascii=False, default=str)
        return json.loads(serialized.replace(self.settings.token, "[REDACTED]"))

    def _list(self, path, params, limit, transform):
        result = self.client.list(path, params, limit)
        result["items"] = [transform(item) for item in result["items"]]
        return self._result(path, **result)

    def _local_date(self, value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
                ZoneInfo(self.settings.timezone)).isoformat()
        except (ValueError, TypeError):
            return None

    def _assignment(self, data, full=False):
        result = picked(data, "id", "course_id", "name", "due_at", "unlock_at", "lock_at",
                        "points_possible", "submission_types", "allowed_extensions", "locked_for_user",
                        "updated_at", "is_quiz_assignment")
        result["html_url"] = clean_url(data.get("html_url") or "", self.settings.base_url)
        result["due_at_local"] = self._local_date(data.get("due_at"))
        submission = data.get("submission")
        result["submission"] = (picked(submission, "workflow_state", "submitted_at", "late", "missing",
                                       "attempt", "score", "grade", "excused") if isinstance(submission, dict) else None)
        if full:
            result["description"] = html_content(data.get("description"), self.settings.base_url)
            result["rubric"] = data.get("rubric", [])
            result["rubric_settings"] = data.get("rubric_settings")
            result["lock_explanation"] = html_content(data.get("lock_explanation"))["text"]
        return result

    def list_courses(self, search="", limit=100):
        path = "/api/v1/courses"
        # Search after fetching; Canvas does not offer a student course-name search parameter.
        result = self.client.list(path, {"enrollment_state": "active"}, limit)
        items = [picked(c, "id", "name", "course_code", "workflow_state", "start_at", "end_at")
                 for c in result["items"] if c.get("name")]
        if search:
            items = [c for c in items if search.casefold() in (c["name"] + " " + (c["course_code"] or "")).casefold()]
        for item in items:
            item["html_url"] = self.settings.base_url + "/courses/" + str(item["id"])
        return self._result(path, items=items, count=len(items), truncated=result["truncated"])

    def get_course(self, course_id):
        path = f"/api/v1/courses/{valid_id(course_id)}"
        data, _ = self.client.get(path, {"include[]": ["syllabus_body"]})
        return self._result(path, course=picked(data, "id", "name", "course_code", "time_zone", "start_at", "end_at"),
                            syllabus=html_content(data.get("syllabus_body"), self.settings.base_url))

    def list_assignments(self, course_id, limit=100):
        path = f"/api/v1/courses/{valid_id(course_id)}/assignments"
        return self._list(path, {"include[]": ["submission"]}, limit, self._assignment)

    def get_assignment(self, course_id, assignment_id):
        path = f"/api/v1/courses/{valid_id(course_id)}/assignments/{valid_id(assignment_id)}"
        data, _ = self.client.get(path, {"include[]": ["submission"]})
        return self._result(path, assignment=self._assignment(data, full=True))

    def list_modules(self, course_id, limit=100):
        path = f"/api/v1/courses/{valid_id(course_id)}/modules"
        return self._list(path, {}, limit, lambda m: picked(m, "id", "name", "position", "items_count",
                                                           "state", "unlock_at", "prerequisite_module_ids"))

    def list_module_items(self, course_id, module_id, limit=100):
        path = f"/api/v1/courses/{valid_id(course_id)}/modules/{valid_id(module_id)}/items"
        def item(data):
            result = picked(data, "id", "title", "type", "position", "content_id", "page_url", "indent")
            result["html_url"] = clean_url(data.get("html_url") or "", self.settings.base_url)
            result["external_url"] = clean_url(data.get("external_url") or "")
            result["content_details"] = data.get("content_details")
            return result
        return self._list(path, {"include[]": ["content_details"]}, limit, item)

    def list_pages(self, course_id, search="", limit=100):
        path = f"/api/v1/courses/{valid_id(course_id)}/pages"
        return self._list(path, {"search_term": search} if search else {}, limit,
                          lambda p: picked(p, "page_id", "url", "title", "updated_at", "front_page"))

    def get_page(self, course_id, page_url):
        if not page_url or len(page_url) > 500 or page_url in (".", ".."):
            raise BridgeError("请提供 list_pages 或模块项目返回的页面标识。")
        path = f"/api/v1/courses/{valid_id(course_id)}/pages/{quote(page_url, safe='')}"
        data, _ = self.client.get(path)
        return self._result(path, page=picked(data, "page_id", "title", "url", "updated_at", "locked_for_user"),
                            content=html_content(data.get("body"), self.settings.base_url))

    def list_announcements(self, course_id, limit=50, start_date="", end_date=""):
        course_id = valid_id(course_id)
        zone = self.settings.timezone
        end = parse_date(end_date, zone, end_of_day=True) if end_date else now_utc()
        warnings = []
        if start_date:
            start, policy = parse_date(start_date, zone), "explicit"
        else:
            start, policy = None, "last_180_days_fallback"
            try:
                course, _ = self.client.get(f"/api/v1/courses/{course_id}", {"include[]": ["term"]})
                term = course.get("term") or {}
                for value, label in ((course.get("start_at"), "course_start"), (term.get("start_at"), "term_start")):
                    candidate = optional_date(value, zone)
                    if candidate is not None and candidate <= end:
                        start, policy = candidate, label
                        break
            except BridgeError:
                warnings.append("无法读取课程起始日期。")
            if start is None:
                start = end - timedelta(days=180)
                warnings.append("未取得有效课程或学期起始日期，默认查询过去 180 天；更早公告需显式指定 start_date。")
        if start > end:
            raise BridgeError("start_date 不能晚于 end_date。")
        path = "/api/v1/announcements"
        result = self._list(path, {"context_codes[]": ["course_" + course_id],
                                  "start_date": start.isoformat(), "end_date": end.isoformat()}, limit,
                            lambda a: {**picked(a, "id", "title", "posted_at", "is_announcement"),
                                       "html_url": clean_url(a.get("html_url") or "", self.settings.base_url),
                                       "content": html_content(a.get("message"), self.settings.base_url)})
        return self._result(path, **{k: v for k, v in result.items() if k not in ("source_url", "fetched_at", "timezone")},
                            query_range={"start": start.isoformat(), "end": end.isoformat(), "end_inclusive": True,
                                         "policy": policy}, warnings=warnings)

    def _file(self, data):
        result = picked(data, "id", "display_name", "filename", "size", "content-type", "updated_at",
                        "locked_for_user", "hidden_for_user")
        result["html_url"] = self.settings.base_url + "/files/" + valid_id(data["id"])
        return result

    def list_course_materials(self, course_id, search="", limit=100):
        path = f"/api/v1/courses/{valid_id(course_id)}/files"
        try:
            return self._list(path, {"search_term": search} if search else {}, limit, self._file)
        except BridgeError as error:
            if not str(error).startswith("HTTP 403"):
                raise
        # A disabled Files tab can prevent folder enumeration while files linked
        # in modules remain readable. Every individual file still uses Canvas ACLs.
        if not 1 <= limit <= 1000:
            raise BridgeError("limit 应为 1–1000。")
        warnings = ["课程 Files 列表不可访问，以下仅为模块中发现的可读文件，不能视为课程全部文件。"]
        modules = self.list_modules(course_id, limit=100)
        linked_files, skipped = {}, 0
        discovery_truncated = modules["truncated"]
        for module in modules["items"]:
            try:
                result = self.list_module_items(course_id, module["id"], limit=1000)
                discovery_truncated |= result["truncated"]
                for item in result["items"]:
                    if item["type"] == "File" and item.get("content_id"):
                        linked_files.setdefault(str(item["content_id"]), item)
            except BridgeError:
                skipped += 1
        files = []
        truncated = discovery_truncated
        for fid, item in linked_files.items():
            title = item.get("title") or ""
            if search and search.casefold() not in title.casefold():
                continue
            if len(files) == limit:
                truncated = True
                break
            files.append({"id": fid, "display_name": title, "filename": None,
                          "html_url": self.settings.base_url + "/files/" + valid_id(fid),
                          "metadata_available": False})
        warnings.append("此索引按模块标题搜索；实际文件名和下载权限需调用 read_material 或 download_material 核验。")
        if skipped:
            warnings.append(f"另有 {skipped} 个模块或文件无法读取，未将其视为空内容。")
        return self._result(path, items=files, count=len(files), truncated=truncated,
                            partial=True, discovery="module_links", warnings=warnings)

    def download_material(self, file_id):
        file_id = valid_id(file_id)
        path = f"/api/v1/files/{file_id}"
        data, _ = self.client.get(path)
        # hidden_for_user also means "only available with link". The Files
        # listing visibility is separate from access to a linked assignment file.
        if data.get("locked_for_user"):
            raise BridgeError("该文件当前对账号锁定。")
        max_bytes = self.settings.max_download_mb * 1024 * 1024
        if data.get("size", 0) > max_bytes:
            raise BridgeError("文件超过配置的下载大小限制。")
        name = Path(data.get("filename") or data.get("display_name") or "file.bin").name
        name = re.sub(r"[^\w.\- ()\u4e00-\u9fff]", "_", name)[-150:]
        folder = self.settings.cache_dir / "files"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (file_id + "-" + name)
        meta_path = folder / (file_id + ".json")
        if target.is_symlink() or meta_path.is_symlink():
            raise BridgeError("缓存文件不能是符号链接。")
        cached = False
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if (target.is_file() and data.get("updated_at") and meta.get("updated_at") == data["updated_at"]
                    and target.stat().st_size <= max_bytes):
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                cached = digest == meta.get("sha256")
        except (OSError, ValueError):
            pass
        if not cached:
            if not data.get("url"):
                raise BridgeError("Canvas 未提供可下载的文件地址。")
            content = self.client.download(data["url"], expected_size=data.get("size"))
            digest = hashlib.sha256(content).hexdigest()
            with tempfile.NamedTemporaryFile(dir=folder, delete=False) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            try:
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            meta = {**self._file(data), "sha256": digest,
                    "downloaded_at": datetime.now(timezone.utc).isoformat()}
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return self._result(path, file=self._file(data), local_path=str(target), sha256=digest, cached=cached)

    def read_material(self, file_id, start=1, count=5, max_chars=20000, offset=0, expected_sha256=""):
        if expected_sha256 and not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
            raise BridgeError("expected_sha256 必须是返回的 SHA256 值。")
        result = self.download_material(file_id)
        if expected_sha256 and expected_sha256 != result["sha256"]:
            raise BridgeError("课件内容已更新，无法沿用旧续读位置；请从第一页重新读取。")
        text = extract(Path(result["local_path"]), start, count, max_chars, offset)
        if text["next_cursor"] is not None:
            text["next_cursor"]["expected_sha256"] = result["sha256"]
        return self._result(result["source_url"], **{k: v for k, v in result.items()
                            if k not in ("source_url", "fetched_at", "timezone")}, **text)

    def get_upcoming_work(self, days=14, course_ids=None, include_completed=False, overdue_days=7, limit=100):
        from .workflows import upcoming_work
        return upcoming_work(self, days, course_ids, include_completed, overdue_days, limit)

    def get_assignment_context(self, course_id, assignment_id, max_related=5,
                               read_attachments=False, announcement_start_date=""):
        from .workflows import assignment_context
        return assignment_context(self, course_id, assignment_id, max_related,
                                  read_attachments, announcement_start_date)
