"""
ingestion/filters.py
Shared filter configuration for the scrapers.

Title and location keywords come from the portals config (see
config/portals.example.yml) so you can retarget the pipeline by editing YAML
instead of Python. If a key is missing, the defaults below are used, which keeps
existing configs working unchanged.
"""

import os
import yaml
from dotenv import load_dotenv

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
load_dotenv(os.path.join(BASE_DIR, ".env"))

# `or` rather than a getenv default: an unset var and a var present-but-blank in
# .env (PORTALS_PATH=) should both fall back to the repo-local config.
PORTALS_PATH = os.getenv("PORTALS_PATH") or os.path.join(BASE_DIR, "config", "portals.yml")

DEFAULT_POSITIVE = [
    "data analyst", "product analyst", "insights analyst", "growth analyst",
    "business analyst", "analytics engineer", "bi analyst", "junior data scientist",
    "storytelling analyst", "marketing analyst", "intelligence analyst",
    "analyst", "analytics", "data scientist", "data specialist", "data insights",
]

DEFAULT_NEGATIVE = [
    "senior", "sr.", "sr ", "principal", "director", "manager", "lead",
    "head of", "vp ", "vice president", "architect", "expert",
    "staff", " ii", " iii", " iv", "deal desk", "aml", "compliance", "payroll",
    "procurement", "purchasing", "compensation", "fp&a", "financial planning",
    "employee lifecycle", "sales operations", "order operations",
    "corporate development", "revenue strategy", "pricing", "sales revenue",
]

DEFAULT_LOCAL_TERMS = ["new york", "nyc", ", ny", "brooklyn", "manhattan"]

DEFAULT_EXCLUDE_CITIES = [
    "boston", "chicago", "san francisco", "seattle", "austin",
    "los angeles", "atlanta", "denver", "dallas", "phoenix",
    "miami", "boise", "stamford", "littleton", "long beach", "englewood",
]


def load_portals(verbose=True):
    """Load the portals config, or None if it isn't there yet."""
    if not os.path.exists(PORTALS_PATH):
        if verbose:
            print(f"No company config found at {PORTALS_PATH}")
            print("Copy config/portals.example.yml to config/portals.yml and edit it,")
            print("or set PORTALS_PATH in .env to point at your own config.")
        return None
    with open(PORTALS_PATH) as f:
        return yaml.safe_load(f) or {}


def _lower_all(values):
    return [str(v).lower() for v in values]


def load_filters():
    """Return (positive, negative, local_terms, exclude_cities), config or defaults."""
    portals = load_portals(verbose=False) or {}

    title = portals.get("title_filter") or {}
    location = portals.get("location_filter") or {}

    return (
        _lower_all(title.get("positive") or DEFAULT_POSITIVE),
        _lower_all(title.get("negative") or DEFAULT_NEGATIVE),
        _lower_all(location.get("local_terms") or DEFAULT_LOCAL_TERMS),
        _lower_all(location.get("exclude_cities") or DEFAULT_EXCLUDE_CITIES),
    )
