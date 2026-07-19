import argparse
import json
from pathlib import Path

import mysql.connector


DEFAULT_BLOCKLIST = {
    "Cool",
    "Nice",
    "Other",
    "Unknown",
    "Unincorporated",
    "Weed",
}


def fetch_cities(conn, min_count):
    query = """
    SELECT TRIM(L_City) AS city, COUNT(*) AS listing_count
    FROM rets_property
    WHERE L_City IS NOT NULL AND TRIM(L_City) <> ''
    GROUP BY TRIM(L_City)
    HAVING listing_count >= %s
    ORDER BY city
    """
    cursor = conn.cursor()
    cursor.execute(query, (min_count,))
    rows = cursor.fetchall()
    cursor.close()
    return rows


def build_city_payload(rows, blocklist):
    blocklist = set(blocklist)
    cities = [city for city, _ in rows if city not in blocklist]

    return {
        "cities": cities,
        "blocked": sorted(city for city, _ in rows if city in blocklist),
    }


def save_json(payload, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3307)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="root")
    parser.add_argument("--database", default="real_estate")
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--output", default="data/processed/valid_cities.json")
    args = parser.parse_args()

    conn = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )
    rows = fetch_cities(conn, args.min_count)
    conn.close()

    payload = build_city_payload(rows, DEFAULT_BLOCKLIST)
    save_json(payload, args.output)

    print(f"Saved {len(payload['cities'])} cities to {args.output}")
    if payload["blocked"]:
        print(f"Blocked: {', '.join(payload['blocked'])}")


if __name__ == "__main__":
    main()
