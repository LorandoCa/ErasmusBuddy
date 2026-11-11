"""Database helper for student assistant tools using local SQLite database."""
from __future__ import annotations

import json
import math
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any
from contextlib import closing

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "coimbra.db"


def _readonly_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    target = Path(db_path) if db_path else DB_PATH
    if not target.exists():
        raise FileNotFoundError(f"Database not found at {target}")
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (math.sin(delta_phi / 2) ** 2
             + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _fts_expression(query: str) -> str:
    clean = re.sub(r"[^\w\s]", " ", _fold(query)).strip()
    tokens = [t for t in clean.split() if len(t) > 1]
    if not tokens:
        return ""
    return " AND ".join(f'"{token}"*' for token in tokens)


def search_places(query: str = "", city: str = "", category: str = "",
                  max_price: float | None = None, limit: int = 5) -> str:
    clauses: list[str] = []
    parameters: list[Any] = []
    expression = _fts_expression(query or "")
    if expression:
        clauses.append("p.rowid IN (SELECT rowid FROM places_fts WHERE places_fts MATCH ?)")
        parameters.append(expression)
    if city and city.strip():
        clauses.append("lower(p.city)=lower(?)")
        parameters.append(city.strip())
    if category and category.strip():
        clauses.append("lower(p.category)=lower(?)")
        parameters.append(category.strip())
    if max_price is not None and float(max_price) > 0:
        clauses.append("p.price_monthly IS NOT NULL AND p.price_monthly<=?")
        parameters.append(float(max_price))
    where = " AND ".join(clauses) if clauses else "1=1"
    parameters.append(max(1, min(int(limit), 20)))
    sql = f"""
        SELECT p.id, p.city, p.category, p.name, p.address, p.neighborhood, p.institution, p.kind,
               p.price_monthly, p.expenses_included, p.latitude, p.longitude, p.source, p.status
        FROM places p WHERE {where}
        ORDER BY p.name LIMIT ?
    """
    with closing(_readonly_connection()) as db:
        rows = [dict(row) for row in db.execute(sql, parameters)]
    for row in rows:
        if row.get("expenses_included") is not None:
            row["expenses_included"] = bool(row["expenses_included"])
    return json.dumps({"count": len(rows), "results": rows}, ensure_ascii=False, indent=2)


def search_housing_near(anchor_query: str = "dei", city: str = "",
                        radius_meters: float = 3500, limit: int = 6) -> str:
    """Find rooms/residences near an anchor place (campus, faculty, landmark)."""
    anchor_json = json.loads(search_places(query=anchor_query, city=city, limit=1))
    if not anchor_json.get("results"):
        return json.dumps({"count": 0, "anchor": None, "results": [], "note": f"Anchor '{anchor_query}' not found in database"}, ensure_ascii=False, indent=2)

    anchor = anchor_json["results"][0]
    effective_city = city.strip() or anchor["city"]
    radius = max(200.0, min(float(radius_meters), 20_000.0))

    with closing(_readonly_connection()) as db:
        candidates = [dict(row) for row in db.execute("""
            SELECT id, city, category, name, address, neighborhood, kind, price_monthly,
                   expenses_included, latitude, longitude, source, status
            FROM places
            WHERE category IN ('quarto', 'quarto_individual', 'quarto_duplo', 'residencia', 'residencia_quarto', 'alojamento_zona')
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND lower(city)=lower(?)
        """, (effective_city,))]

    results: list[dict[str, Any]] = []
    for row in candidates:
        distance = _haversine(anchor["latitude"], anchor["longitude"], row["latitude"], row["longitude"])
        if distance <= radius:
            row["distance_meters"] = round(distance)
            row["distance_km"] = round(distance / 1000.0, 2)
            if row.get("expenses_included") is not None:
                row["expenses_included"] = bool(row["expenses_included"])
            results.append(row)

    # Sort by price and distance
    results.sort(key=lambda item: (item.get("price_monthly") or 9999, item["distance_meters"]))
    sliced = results[:max(1, min(int(limit), 20))]
    payload = {
        "count": len(sliced),
        "anchor": {
            "name": anchor["name"],
            "city": anchor["city"],
            "address": anchor.get("address"),
            "latitude": anchor["latitude"],
            "longitude": anchor["longitude"],
        },
        "results": sliced,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def distance_between_places(origin_query: str, target_query: str,
                            origin_city: str = "", target_city: str = "") -> str:
    """Calculate the straight-line distance between two places in the database."""
    origin_res = json.loads(search_places(query=origin_query, city=origin_city, limit=1))
    target_res = json.loads(search_places(query=target_query, city=target_city, limit=1))

    if not origin_res.get("results") or not target_res.get("results"):
        missing = "origin" if not origin_res.get("results") else "target"
        return json.dumps({"count": 0, "error": f"Place '{missing}' not found in database"}, ensure_ascii=False)

    first, second = origin_res["results"][0], target_res["results"][0]
    distance = _haversine(first["latitude"], first["longitude"], second["latitude"], second["longitude"])
    result = {
        "origin": {k: first.get(k) for k in ("name", "city", "address", "latitude", "longitude")},
        "target": {k: second.get(k) for k in ("name", "city", "address", "latitude", "longitude")},
        "distance_meters": round(distance),
        "distance_km": round(distance / 1000.0, 2),
    }
    return json.dumps({"count": 1, "results": [result]}, ensure_ascii=False, indent=2)


def search_products(query: str = "", retailer: str = "", limit: int = 6) -> str:
    """Search student grocery prices (Continente and Pingo Doce)."""
    clauses = ["1=1"]
    parameters: list[Any] = []
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        clauses.append("(lower(name) LIKE lower(?) OR lower(coalesce(brand,'')) LIKE lower(?))")
        parameters.extend((pattern, pattern))
    if retailer and retailer.strip():
        clauses.append("lower(retailer)=lower(?)")
        parameters.append(retailer.strip())

    parameters.append(max(1, min(int(limit), 20)))
    sql = f"""
        SELECT id, retailer, category, name, brand, package_size, price_euros, unit_price,
               promotion_text, source_url, source_label, verified
        FROM products
        WHERE {' AND '.join(clauses)}
        ORDER BY price_euros ASC LIMIT ?
    """
    with closing(_readonly_connection()) as db:
        rows = [dict(row) for row in db.execute(sql, parameters)]
    return json.dumps({"count": len(rows), "results": rows}, ensure_ascii=False, indent=2)
