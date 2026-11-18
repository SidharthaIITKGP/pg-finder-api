"""PG Finder demo inventory API for the CallKaro FDE assignment.

All listings and prices are intentionally fictional. The endpoint is read-only:
no booking, visit scheduling or payments are supported.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


DATA_PATH = Path(__file__).with_name("properties.json")
PROPERTIES = json.loads(DATA_PATH.read_text(encoding="utf-8"))
app = FastAPI(title="PG Finder Inventory API", version="1.1.0")


class SearchRequest(BaseModel):
    city: str | None = Field(default=None, description="City requested by the caller")
    area: str | None = Field(default=None, description="Preferred locality")
    pg_type: str | None = Field(default=None, description="boys, girls or co-living")
    min_budget: int | str | None = Field(default=None, description="Optional minimum monthly rent in INR; omit if no lower bound")
    max_budget: int | str | None = Field(default=None, description="Optional maximum monthly rent in INR; omit if no upper bound")
    room_type: str | None = Field(default=None, description="single or sharing")


def tidy(text: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", " ", str(text or "").casefold())).strip()


def canon_city(value: str | None) -> str:
    norm = tidy(value)
    return {
        "bangalore": "bengaluru", "bengaluru": "bengaluru", "blr": "bengaluru",
        "pune": "pune", "poona": "pune",
        "hyderabad": "hyderabad", "hyd": "hyderabad",
    }.get(norm, norm)


def canon_area(value: str | None) -> str:
    norm = tidy(value)
    return {
        "hsr": "hsr layout", "hsr layout": "hsr layout", "hinjewadi phase 1": "hinjewadi",
        "hinjawadi": "hinjewadi", "viman nagar": "viman nagar",
        "gachibowli": "gachibowli", "koramangala": "koramangala",
    }.get(norm, norm)


def canon_pg_type(value: str | None) -> str:
    norm = tidy(value)
    return {
        "boy": "boys", "boy's": "boys", "boys pg": "boys", "mens": "boys", "male": "boys",
        "girl": "girls", "girls pg": "girls", "female": "girls", "women": "girls",
        "coliving": "co-living", "co living": "co-living", "mixed": "co-living",
        "unisex": "co-living", "co-living": "co-living",
    }.get(norm, norm)


def canon_room(value: str | None) -> str:
    norm = tidy(value)
    return {
        "shared": "sharing", "double": "sharing", "double sharing": "sharing",
        "twin sharing": "sharing", "triple sharing": "sharing", "shared room": "sharing",
        "private": "single", "private room": "single", "single room": "single",
        "sharing": "sharing", "single": "single",
    }.get(norm, norm)


def budget_rupees(value: int | str | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).lower().strip().replace("₹", "").replace(",", "")
    # Accepted examples: 12000, 12k, 12 thousand, 12.5k, 12000 rupees
    match = re.fullmatch(r"(?:rs\.?\s*)?(\d+(?:\.\d+)?)\s*(k|thousand|rupees?|inr)?", text)
    if not match:
        return None
    amount = float(match.group(1)) * (1000 if match.group(2) in {"k", "thousand"} else 1)
    return round(amount) if amount > 0 else None


def search_inventory(query: SearchRequest) -> dict[str, Any]:
    city = canon_city(query.city)
    area = canon_area(query.area)
    pg_type = canon_pg_type(query.pg_type)
    room_type = canon_room(query.room_type)
    min_budget = budget_rupees(query.min_budget)
    max_budget = budget_rupees(query.max_budget)

    # A missing budget means no price restriction, but a malformed supplied
    # budget must not silently turn into an unrestricted search.
    invalid_budget_fields = [
        key for key, raw, parsed in (
            ("min_budget", query.min_budget, min_budget),
            ("max_budget", query.max_budget, max_budget),
        )
        if raw is not None and str(raw).strip() and parsed is None
    ]
    if invalid_budget_fields:
        return {
            "status": "invalid_budget", "match_count": 0, "matches": [],
            "invalid_fields": invalid_budget_fields,
            "message": "Invalid budget value. Clarify the amount in INR and search again.",
        }
    if min_budget is not None and max_budget is not None and min_budget > max_budget:
        return {
            "status": "invalid_budget_range", "match_count": 0, "matches": [],
            "message": "Minimum budget is greater than maximum. Ask the caller to clarify.",
        }

    missing = []
    for key, value in [("city", city), ("area", area), ("pg_type", pg_type),
                       ("room_type", room_type)]:
        if not value:
            missing.append(key)
    if pg_type and pg_type not in {"boys", "girls", "co-living"}:
        missing.append("pg_type")
    if room_type and room_type not in {"single", "sharing"}:
        missing.append("room_type")
    missing = list(dict.fromkeys(missing))

    all_cities = sorted({p["city"] for p in PROPERTIES})
    in_city = [p for p in PROPERTIES if canon_city(p["city"]) == city]
    available_areas = sorted({p["area"] for p in in_city}) if in_city else []
    if missing:
        return {
            "status": "need_more_info", "missing_fields": missing,
            "available_cities": all_cities,
            "available_areas_in_city": available_areas,
            "message": "Ask the caller only for missing or unclear requirements. Do not suggest a PG yet."
        }

    matches = []
    for property_ in in_city:
        if canon_area(property_["area"]) != area or property_["pg_type"] != pg_type:
            continue
        for room in property_["rooms"]:
            if room["type"] != room_type:
                continue
            if min_budget is not None and room["monthly_price"] < min_budget:
                continue
            if max_budget is not None and room["monthly_price"] > max_budget:
                continue
            matches.append({
                "id": property_["id"], "name": property_["name"],
                "city": property_["city"], "area": property_["area"],
                "pg_type": property_["pg_type"], "room_type": room["type"],
                "monthly_price_inr": room["monthly_price"],
            })
    matches.sort(key=lambda m: (m["monthly_price_inr"], m["name"]))
    shown = matches[:3]
    return {
        "status": "matches_found" if shown else "no_matches",
        "match_count": len(matches),
        "matches": shown,
        "filters": {"city": query.city, "area": query.area, "pg_type": pg_type,
                    "min_budget_inr": min_budget, "max_budget_inr": max_budget,
                    "room_type": room_type},
        "available_areas_in_city": available_areas if not shown else [],
        "message": (
            "Recommend only these returned properties. Prices are monthly and room availability is unverified."
            if shown else
            "No exact property match. Do not invent listings or broaden filters without asking the caller."
        ),
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "PG Finder demo inventory", "status": "ok", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "properties": len(PROPERTIES)}


@app.post("/search_pgs")
def search_pgs(query: SearchRequest) -> dict[str, Any]:
    return search_inventory(query)


@app.get("/search_pgs")
def search_pgs_get(city: str | None = None, area: str | None = None,
                   pg_type: str | None = None, min_budget: str | None = None,
                   max_budget: str | None = None, room_type: str | None = None) -> dict[str, Any]:
    """Convenient browser testing; use POST for the actual CallKaro function."""
    return search_inventory(SearchRequest(city=city, area=area, pg_type=pg_type,
                                          min_budget=min_budget, max_budget=max_budget,
                                          room_type=room_type))
