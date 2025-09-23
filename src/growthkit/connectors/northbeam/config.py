import os
from pathlib import Path
from dataclasses import dataclass

try:
	from dotenv import load_dotenv  # type: ignore
	_has_dotenv = True
except Exception:
	_has_dotenv = False

DEFAULT_ENV_PATH = Path("config/northbeam/.env")


def _manual_load_env(path: Path) -> None:
	"""Minimal .env parser: KEY=VALUE per line, ignores comments/blank lines."""
	try:
		if not path.exists():
			return
		for raw in path.read_text(encoding="utf-8").splitlines():
			line = raw.strip()
			if not line or line.startswith("#"):
				continue
			if "=" not in line:
				continue
			key, val = line.split("=", 1)
			key = key.strip()
			val = val.strip().strip('"').strip("'")
			# Do not override already-set env vars
			if key and key not in os.environ:
				os.environ[key] = val
	except Exception:
		# Silent fallback
		return


def _maybe_load_dotenv(path: Path = DEFAULT_ENV_PATH) -> None:
	if path.exists():
		if _has_dotenv:
			load_dotenv(path)
		else:
			_manual_load_env(path)


@dataclass
class NorthbeamAuth:
	api_key: str
	account_id: str
	base_url: str


def load_auth(env_path: Path = DEFAULT_ENV_PATH) -> NorthbeamAuth:
	"""Load Northbeam credentials from env or optional .env file.
	Order of precedence: process env > .env file > defaults.
	"""
	_maybe_load_dotenv(env_path)
	api_key = os.getenv("NB_API_KEY", "")
	account_id = os.getenv("NB_ACCOUNT_ID", "")
	base_url = os.getenv("NB_BASE_URL", "https://api.northbeam.io")
	return NorthbeamAuth(api_key=api_key, account_id=account_id, base_url=base_url) 