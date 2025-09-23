#!/usr/bin/env python3
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Dict, Any

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

GA4_ENV = Path("config/ga4/.env")
GA4_KEY_DEFAULT = Path("config/ga4/service_account.json")


def _load_env(path: Path) -> None:
	if not path.exists():
		return
	for line in path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if not line or line.startswith("#"):
			continue
		if "=" in line:
			k, v = line.split("=", 1)
			os.environ.setdefault(k.strip(), v.strip())


@dataclass
class GA4Auth:
	property_id: str
	key_file: Path

	@staticmethod
	def load() -> "GA4Auth":
		_load_env(GA4_ENV)
		prop = os.environ.get("GA4_PROPERTY_ID") or ""
		key = os.environ.get("GA4_KEY_FILE") or str(GA4_KEY_DEFAULT)
		if not prop:
			raise RuntimeError("GA4_PROPERTY_ID not set (put it in config/ga4/.env)")
		key_path = Path(key)
		if not key_path.exists():
			raise RuntimeError(f"GA4 key not found at {key_path}")
		os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(key_path))
		return GA4Auth(property_id=prop, key_file=key_path)


class GA4Client:
	def __init__(self, auth: GA4Auth | None = None) -> None:
		self.auth = auth or GA4Auth.load()
		self.client = BetaAnalyticsDataClient()

	def run_channels_report(self, start: date, end: date) -> List[Dict[str, Any]]:
		# Default Channel Grouping v1
		req = RunReportRequest(
			property=f"properties/{self.auth.property_id}",
			date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
			dimensions=[Dimension(name="sessionDefaultChannelGroup")],
			metrics=[
				Metric(name="sessions"),
				Metric(name="totalUsers"),
				Metric(name="ecommercePurchases"),
				Metric(name="purchaseRevenue"),
			],
		)
		resp = self.client.run_report(req)
		rows: List[Dict[str, Any]] = []
		for r in resp.rows:
			row: Dict[str, Any] = {
				"channel": r.dimension_values[0].value or "(not set)",
				"sessions": float(r.metric_values[0].value or 0),
				"users": float(r.metric_values[1].value or 0),
				"purchases": float(r.metric_values[2].value or 0),
				"revenue": float(r.metric_values[3].value or 0),
			}
			rows.append(row)
		return rows

	def run_channels_engagement(self, start: date, end: date) -> List[Dict[str, Any]]:
		"""Fetch engagement-quality metrics by session default channel group."""
		req = RunReportRequest(
			property=f"properties/{self.auth.property_id}",
			date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
			dimensions=[Dimension(name="sessionDefaultChannelGroup")],
			metrics=[
				Metric(name="engagedSessions"),
				Metric(name="engagementRate"),
				Metric(name="averageSessionDuration"),
				Metric(name="eventsPerSession"),
				Metric(name="eventCount"),
				Metric(name="keyEvents"),
				Metric(name="sessionKeyEventRate"),
			],
		)
		resp = self.client.run_report(req)
		out: List[Dict[str, Any]] = []
		for r in resp.rows:
			out.append({
				"channel": r.dimension_values[0].value or "(not set)",
				"engaged_sessions": float(r.metric_values[0].value or 0),
				"engagement_rate": float(r.metric_values[1].value or 0),
				"avg_session_duration": float(r.metric_values[2].value or 0),
				"events_per_session": float(r.metric_values[3].value or 0),
				"event_count": float(r.metric_values[4].value or 0),
				"key_events": float(r.metric_values[5].value or 0),
				"session_key_event_rate": float(r.metric_values[6].value or 0),
			})
		return out

	def run_daily(self, start: date, end: date, dims: List[str]) -> List[Dict[str, Any]]:
		# Generic daily report with metrics we use elsewhere
		dimensions = [Dimension(name="date")] + [Dimension(name=d) for d in dims]
		req = RunReportRequest(
			property=f"properties/{self.auth.property_id}",
			date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
			dimensions=dimensions,
			metrics=[
				Metric(name="sessions"),
				Metric(name="totalUsers"),
				Metric(name="ecommercePurchases"),
				Metric(name="purchaseRevenue"),
			],
			limit=250000,
		)
		resp = self.client.run_report(req)
		rows: List[Dict[str, Any]] = []
		for r in resp.rows:
			vals = [dv.value for dv in r.dimension_values]
			out: Dict[str, Any] = {
				"date": vals[0],
				"sessions": float(r.metric_values[0].value or 0),
				"users": float(r.metric_values[1].value or 0),
				"purchases": float(r.metric_values[2].value or 0),
				"revenue": float(r.metric_values[3].value or 0),
			}
			# attach dimension labels in order
			for i, d in enumerate(dims, start=1):
				out[d] = vals[i]
			rows.append(out)
		return rows

	def run_daily_custom(self, start: date, end: date, dims: List[str], metric_names: List[str]) -> List[Dict[str, Any]]:
		dimensions = [Dimension(name="date")] + [Dimension(name=d) for d in dims]
		metrics = [Metric(name=m) for m in metric_names]
		req = RunReportRequest(
			property=f"properties/{self.auth.property_id}",
			date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
			dimensions=dimensions,
			metrics=metrics,
			limit=250000,
		)
		resp = self.client.run_report(req)
		rows: List[Dict[str, Any]] = []
		for r in resp.rows:
			vals = [dv.value for dv in r.dimension_values]
			out: Dict[str, Any] = {"date": vals[0]}
			for i, d in enumerate(dims, start=1):
				out[d] = vals[i]
			for j, m in enumerate(metric_names):
				out[m] = r.metric_values[j].value
			rows.append(out)
		return rows 