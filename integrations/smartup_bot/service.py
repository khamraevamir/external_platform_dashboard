from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from integrations.models import SmartupAttendanceRow, SmartupAttendanceSync
from integrations.smartup.parsers.route_analysis_parser import RouteAnalysisParser


@dataclass
class RouteAnalysisResult:
    title: str
    html: str
    run_url: str
    metadata: dict[str, Any]


def clean_number(value: Any) -> int:
    text = str(value or "").replace(" ", "").replace("\xa0", "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def build_attendance_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, dict[str, int | str]] = {}

    for row in rows:
        staff = " ".join(str(row.get("staff") or "").split()).strip()
        if not staff:
            continue

        p_value = clean_number(row.get("p"))
        pd_value = clean_number(row.get("pd"))

        if staff not in summary:
            summary[staff] = {"staff": staff, "p": 0, "pd": 0, "total": 0}

        summary[staff]["p"] += p_value
        summary[staff]["pd"] += pd_value
        summary[staff]["total"] += p_value + pd_value

    result_rows = sorted(summary.values(), key=lambda item: str(item["staff"]).lower())
    totals = {
        "staff": "ИТОГО",
        "p": sum(int(item["p"]) for item in result_rows),
        "pd": sum(int(item["pd"]) for item in result_rows),
        "total": sum(int(item["total"]) for item in result_rows),
    }

    return {
        "rows": result_rows,
        "totals": totals,
    }


class SmartupAttendanceStorage:
    def __init__(self) -> None:
        self.base_dir = Path(settings.BASE_DIR) / "var" / "smartup_bot"
        self.state_dir = self.base_dir / "state"
        self.reports_dir = self.base_dir / "reports"
        self.logs_dir = self.base_dir / "logs"

        for path in (self.base_dir, self.state_dir, self.reports_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def storage_state_path(self) -> Path:
        return self.state_dir / "storage_state.json"

    def build_html_report_path(self, date_from: str, date_to: str) -> Path:
        stamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        return self.reports_dir / f"route_analysis_{date_from}_{date_to}_{stamp}.html"


class SmartupAttendanceBot:
    USERNAME_SELECTORS = [
        "#login",
        'input[name="username"]',
        'input[name="login"]',
        'input[name="user"]',
        'input[type="email"]',
        'input[type="text"]',
    ]
    PASSWORD_SELECTORS = [
        "#password",
        'input[name="password"]',
        'input[type="password"]',
    ]
    SUBMIT_SELECTORS = [
        'button:has-text("ВОЙТИ")',
        'button:has-text("Войти")',
        'text=ВОЙТИ',
        'button[type="submit"]',
        'input[type="submit"]',
        "button",
    ]

    def __init__(self) -> None:
        self.storage = SmartupAttendanceStorage()
        self.login_url = getattr(settings, "SMARTUP_LOGIN_URL", "") or "https://smartup.online"
        self.route_analysis_url = (
            getattr(settings, "SMARTUP_ROUTE_ANALYSIS_URL", "")
            or "https://smartup.online/#/!4km6nkksz/trade/rep/route_analysis"
        )
        self.base_origin = "https://smartup.online"
        self.username = (
            getattr(settings, "SMARTUP_API_LOGIN", "")
            or getattr(settings, "SMARTUP_USERNAME", "")
        )
        self.password = (
            getattr(settings, "SMARTUP_API_PASSWORD", "")
            or getattr(settings, "SMARTUP_PASSWORD", "")
        )
        self.project_code = getattr(settings, "SMARTUP_PROJECT_CODE", "") or "trade"
        self.project_hash = getattr(settings, "SMARTUP_PROJECT_HASH", "") or "01"
        self.filial_id = str(getattr(settings, "SMARTUP_FILIAL_ID", "") or "")
        self.user_id = str(getattr(settings, "SMARTUP_REPORT_USER_ID", "") or "")
        self.lang_code = "ru"
        self.headless = str(getattr(settings, "SMARTUP_PLAYWRIGHT_HEADLESS", "True")).lower() == "true"

    def _first_visible(self, page, selectors: list[str]):
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                if locator.count() and locator.is_visible():
                    return locator
            except Exception:
                continue
        return None

    def _wait_for_login_form(self, page) -> tuple[Any, Any]:
        username_input = None
        password_input = None

        for _ in range(30):
            username_input = self._first_visible(page, self.USERNAME_SELECTORS)
            password_input = self._first_visible(page, self.PASSWORD_SELECTORS)
            if username_input and password_input:
                break
            page.wait_for_timeout(500)

        return username_input, password_input

    def _perform_login(self, page, context) -> None:
        if not self.username or not self.password:
            raise ValueError("SMARTUP_API_LOGIN and SMARTUP_API_PASSWORD must be configured for Smartup bot.")

        page.goto(self.login_url, wait_until="load", timeout=60000)
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        username_input, password_input = self._wait_for_login_form(page)

        if not username_input or not password_input:
            raise ValueError("Smartup login form was not found.")

        username_input.fill(self.username)
        password_input.fill(self.password)

        submit = self._first_visible(page, self.SUBMIT_SELECTORS)
        if submit:
            submit.click(timeout=10000)
        else:
            password_input.press("Enter")

        page.wait_for_timeout(5000)
        context.storage_state(path=str(self.storage.storage_state_path))

    def _ensure_authenticated(self, page, context) -> None:
        page.goto(self.route_analysis_url, wait_until="load", timeout=60000)
        page.wait_for_timeout(5000)

        if "login.html" in page.url or page.locator("#login").count():
            self._perform_login(page, context)
            page.goto(self.route_analysis_url, wait_until="load", timeout=60000)
            page.wait_for_timeout(5000)

    def _refresh_session(self) -> None:
        # Imported lazily to avoid forcing Playwright import on every Django startup.
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, slow_mo=100 if not self.headless else 0)

            context_kwargs: dict[str, Any] = {}
            if self.storage.storage_state_path.exists():
                context_kwargs["storage_state"] = str(self.storage.storage_state_path)

            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            self._ensure_authenticated(page, context)

            context.storage_state(path=str(self.storage.storage_state_path))
            browser.close()

    def _build_requests_session(self) -> requests.Session:
        if not self.storage.storage_state_path.exists():
            raise ValueError("Smartup storage_state.json not found.")

        state = json.loads(self.storage.storage_state_path.read_text(encoding="utf-8"))

        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        })

        for cookie in state.get("cookies", []):
            session.cookies.set(
                cookie.get("name"),
                cookie.get("value"),
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )

        return session

    def _raise_for_status_with_body(self, response: requests.Response) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body = (response.text or "").strip()
            if len(body) > 1200:
                body = body[:1200] + "..."
            raise requests.HTTPError(
                f"{exc}. Response body: {body or '<empty>'}",
                response=response,
            ) from exc

    def _fetch_route_analysis_via_http(self, date_from: str, date_to: str) -> RouteAnalysisResult:
        metadata: dict[str, Any] = {
            "requests": [],
            "responses": [],
        }
        session = self._build_requests_session()

        model_url = f"{self.base_origin}/b/trade/rep/route_analysis:model"
        run_url = f"{self.base_origin}/b/trade/rep/route_analysis:run"

        model_headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{self.base_origin}/",
            "formurl": "/trade/rep/route_analysis?",
            "project_code": self.project_code,
            "filial_id": self.filial_id,
            "user_id": self.user_id,
            "lang_code": self.lang_code,
        }
        metadata["requests"].append({
            "method": "POST",
            "url": model_url,
            "headers": model_headers,
            "post_data": "{}",
        })
        model_response = session.post(model_url, headers=model_headers, json={}, timeout=60)
        self._raise_for_status_with_body(model_response)
        metadata["responses"].append({
            "status": model_response.status_code,
            "url": model_response.url,
            "headers": dict(model_response.headers),
            "body_preview": model_response.text[:2000],
        })

        params = {
            "rt": "html",
            "url": "/trade/rep/route_analysis:run_redirect",
            "begin_date": date_from,
            "end_date": date_to,
            "person_group_id": "",
            "person_kind": "",
            "report_state": "A",
            "show_mml": "Y",
            "mml_type": "P",
            "show_mml_to_sku": "N",
            "-project_code": self.project_code,
            "-project_hash": self.project_hash,
            "-filial_id": self.filial_id,
            "-user_id": self.user_id,
            "-lang_code": self.lang_code,
        }
        metadata["requests"].append({
            "method": "GET",
            "url": run_url,
            "headers": {"Referer": f"{self.base_origin}/"},
            "params": params,
        })
        run_response = session.get(
            run_url,
            params=params,
            headers={"Referer": f"{self.base_origin}/"},
            timeout=180,
        )
        self._raise_for_status_with_body(run_response)
        metadata["responses"].append({
            "status": run_response.status_code,
            "url": run_response.url,
            "headers": dict(run_response.headers),
            "body_preview": run_response.text[:3000],
        })

        parsed = RouteAnalysisParser.parse(run_response.text)
        return RouteAnalysisResult(
            title=parsed["title"] or "Анализ маршрута",
            html=run_response.text,
            run_url=run_response.url,
            metadata=metadata,
        )

    def fetch_route_analysis(self, date_from: str, date_to: str) -> RouteAnalysisResult:
        if not self.storage.storage_state_path.exists():
            self._refresh_session()

        try:
            return self._fetch_route_analysis_via_http(date_from=date_from, date_to=date_to)
        except requests.HTTPError as exc:
            message = str(exc)
            if "HttpSession.getAttribute" in message or "401" in message or "403" in message:
                self._refresh_session()
                return self._fetch_route_analysis_via_http(date_from=date_from, date_to=date_to)
            raise


class SmartupAttendanceSyncService:
    def __init__(self) -> None:
        self.storage = SmartupAttendanceStorage()
        self.bot = SmartupAttendanceBot()

    def sync(self, date_from: str, date_to: str) -> dict[str, Any]:
        sync = SmartupAttendanceSync.objects.create(
            date_from=date_from,
            date_to=date_to,
            status=SmartupAttendanceSync.STATUS_RUNNING,
            started_at=timezone.now(),
        )

        try:
            result = self.bot.fetch_route_analysis(date_from=date_from, date_to=date_to)
            parsed = RouteAnalysisParser.parse(result.html)
            summary = build_attendance_summary(parsed["rows"])

            html_path = self.storage.build_html_report_path(date_from, date_to)
            html_path.write_text(result.html, encoding="utf-8")

            with transaction.atomic():
                sync.report_title = result.title
                sync.html_report_path = str(html_path)
                sync.run_url = result.run_url
                sync.metadata = result.metadata
                sync.status = SmartupAttendanceSync.STATUS_SUCCESS
                sync.finished_at = timezone.now()
                sync.save(update_fields=[
                    "report_title",
                    "html_report_path",
                    "run_url",
                    "metadata",
                    "status",
                    "finished_at",
                    "updated_at",
                ])

                SmartupAttendanceRow.objects.bulk_create(
                    [
                        SmartupAttendanceRow(
                            sync=sync,
                            staff=str(row["staff"]),
                            p=int(row["p"]),
                            pd=int(row["pd"]),
                            total=int(row["total"]),
                        )
                        for row in summary["rows"]
                    ]
                )

            return {
                "sync_id": sync.id,
                "status": sync.status,
                "title": sync.report_title,
                "date_from": sync.date_from,
                "date_to": sync.date_to,
                "rows_count": len(summary["rows"]),
                "totals": summary["totals"],
                "html_report_path": sync.html_report_path,
            }
        except Exception as exc:
            sync.status = SmartupAttendanceSync.STATUS_ERROR
            sync.error_message = str(exc)
            sync.finished_at = timezone.now()
            sync.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
            raise

    def get_latest_summary(self, date_from: str, date_to: str) -> dict[str, Any] | None:
        sync = (
            SmartupAttendanceSync.objects
            .filter(
                date_from=date_from,
                date_to=date_to,
                status=SmartupAttendanceSync.STATUS_SUCCESS,
            )
            .order_by("-created_at")
            .prefetch_related("rows")
            .first()
        )

        if not sync:
            return None

        rows = [
            {
                "staff": row.staff,
                "p": row.p,
                "pd": row.pd,
                "total": row.total,
            }
            for row in sync.rows.all()
        ]

        totals = {
            "staff": "ИТОГО",
            "p": sum(row["p"] for row in rows),
            "pd": sum(row["pd"] for row in rows),
            "total": sum(row["total"] for row in rows),
        }

        return {
            "sync_id": sync.id,
            "title": sync.report_title or "Посещаемость",
            "date_from": sync.date_from,
            "date_to": sync.date_to,
            "rows": rows,
            "totals": totals,
            "last_synced_at": sync.finished_at,
            "html_report_path": sync.html_report_path,
        }
