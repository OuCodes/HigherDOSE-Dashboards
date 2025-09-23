import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from .config import load_auth, NorthbeamAuth


DEFAULT_POLL_INTERVAL_SEC = 2.0
DEFAULT_POLL_TIMEOUT_SEC = 300.0


@dataclass
class ExportResult:
	status: str
	export_id: Optional[str]
	location: Optional[str]
	payload: Dict[str, Any]


class NorthbeamClient:
	def __init__(self, auth: Optional[NorthbeamAuth] = None) -> None:
		self.auth = auth or load_auth()
		self.base = self.auth.base_url.rstrip("/")
		# Per docs, use Authorization and Data-Client-ID
		self.headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": self.auth.api_key,
			"Data-Client-ID": self.auth.account_id,
		}

	def _request(self, method: str, path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		url = f"{self.base}{path}"
		body = None
		if data is not None:
			body = json.dumps(data).encode("utf-8")
		req = urllib.request.Request(url, data=body, method=method.upper())
		for k, v in self.headers.items():
			req.add_header(k, v)
		try:
			with urllib.request.urlopen(req) as resp:
				raw = resp.read().decode("utf-8")
				return json.loads(raw) if raw else {}
		except urllib.error.HTTPError as e:
			msg = e.read().decode("utf-8", errors="ignore")
			raise RuntimeError(f"Northbeam HTTP {e.code} {e.reason}: {msg}") from None

	# Metadata
	def list_metrics(self) -> List[Dict[str, Any]]:
		return self._request("GET", "/v1/exports/metrics").get("metrics", [])

	def list_breakdowns(self) -> List[Dict[str, Any]]:
		return self._request("GET", "/v1/exports/breakdowns").get("breakdowns", [])

	def list_attribution_models(self) -> List[Dict[str, Any]]:
		return self._request("GET", "/v1/exports/attribution-models").get("attribution_models", [])

	# Data export
	def create_export(self, *, start_date: Optional[str] = None, end_date: Optional[str] = None,
					  accounting_mode: Optional[str] = None, attribution_model: Optional[str] = None,
					  attribution_window: Optional[str] = None, metrics: Optional[List[str]] = None,
					  breakdowns: Optional[List[Union[str, Dict[str, Any]]]] = None, level: str = "ad",
					  time_granularity: str = "DAILY",
					  period_type: Optional[str] = None) -> str:
		"""Create an export per docs.
		If period_type not provided, use CUSTOM with start/end at top level.
		Breakdowns may be list of keys or full dicts with key and values.
		"""
		# Build metrics array of objects
		metrics_objs: List[Dict[str, Any]] = []
		if metrics:
			for m in metrics:
				metrics_objs.append({"id": m})
		else:
			metrics_objs = [{"id": "spend"}, {"id": "rev"}]

		# Attribution options per docs: arrays
		attr_opts: Dict[str, Any] = {}
		if attribution_model:
			attr_opts["attribution_models"] = [attribution_model]
		if accounting_mode:
			attr_opts["accounting_modes"] = [accounting_mode]
		if attribution_window:
			attr_opts["attribution_windows"] = [str(attribution_window)]

		payload: Dict[str, Any] = {
			"level": level,
			"time_granularity": time_granularity,
			"metrics": metrics_objs,
			"attribution_options": attr_opts,
		}
		if period_type:
			payload["period_type"] = period_type
		elif start_date and end_date:
			payload["period_type"] = "FIXED"
			# Convert YYYY-MM-DD -> ISO8601 Zulu bounds
			start_iso = f"{start_date}T00:00:00Z"
			end_iso = f"{end_date}T23:59:59Z"
			payload["period_options"] = {"period_starting_at": start_iso, "period_ending_at": end_iso}

		# Breakdowns: support prebuilt dicts, else keys only (caller should supply values if API requires)
		if breakdowns:
			bd_payload: List[Dict[str, Any]] = []
			for b in breakdowns:
				if isinstance(b, dict):
					bd_payload.append(b)
				else:
					bd_payload.append({"key": b})
			payload["breakdowns"] = bd_payload

		res = self._request("POST", "/v1/exports/data-export", payload)
		export_id = res.get("id") or res.get("export_id")
		if not export_id:
			raise RuntimeError(f"Unexpected response creating export: {res}")
		return str(export_id)

	def get_export_result(self, export_id: str) -> ExportResult:
		res = self._request("GET", f"/v1/exports/data-export/result/{export_id}")
		status = str(res.get("status", "unknown")).upper()
		links = res.get("result") or []
		location = links[0] if links else None
		return ExportResult(status=status, export_id=export_id, location=location, payload=res)

	def wait_for_export(self, export_id: str, *, interval: float = DEFAULT_POLL_INTERVAL_SEC,
					   timeout: float = DEFAULT_POLL_TIMEOUT_SEC) -> ExportResult:
		start = time.time()
		while True:
			result = self.get_export_result(export_id)
			if result.status in ("SUCCESS", "READY", "COMPLETED"):
				return result
			if result.status in ("FAILED", "ERROR"):
				raise RuntimeError(f"Export {export_id} failed: {result.payload}")
			if time.time() - start > timeout:
				raise TimeoutError(f"Timed out waiting for export {export_id} (last status: {result.status})")
			time.sleep(interval) 