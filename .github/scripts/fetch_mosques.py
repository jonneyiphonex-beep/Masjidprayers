import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="SD"]["admin_level"="2"]->.sudan;
(
  nwr["amenity"="mosque"](area.sudan);
  nwr["amenity"="place_of_worship"]["religion"~"^(muslim|islam)$",i](area.sudan);
  nwr["building"="mosque"](area.sudan);
);
out center;
"""
ENDPOINT = "https://overpass-api.de/api/interpreter"


def fetch_mosques():
    request = urllib.request.Request(
        ENDPOINT,
        data=urllib.parse.urlencode({"data": QUERY}).encode(),
        headers={"User-Agent": "Masjidprayers/1.0 (Sudan mosque directory)"},
    )
    with urllib.request.urlopen(request, timeout=240) as response:
        result = json.load(response)

    if not isinstance(result, dict) or not isinstance(result.get("elements"), list):
        raise RuntimeError("OpenStreetMap returned an unexpected response.")
    if result.get("remark"):
        raise RuntimeError(f"OpenStreetMap query failed: {result['remark']}")

    mosques = {}
    for element in result["elements"]:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags", {})
        center = element.get("center")
        if not isinstance(tags, dict):
            tags = {}
        if not isinstance(center, dict):
            center = {}
        latitude = element.get("lat", center.get("lat"))
        longitude = element.get("lon", center.get("lon"))
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            continue
        osm_type = element.get("type")
        osm_id = element.get("id")
        if osm_type not in {"node", "way", "relation"} or not isinstance(osm_id, int):
            continue
        mosque_id = f"{osm_type}/{osm_id}"
        mosques[mosque_id] = {
            "id": mosque_id,
            "lat": latitude,
            "lng": longitude,
            "name": tags.get("name:ar") or tags.get("name") or "مسجد بدون اسم",
            "state": tags.get("addr:state") or tags.get("is_in:state") or "",
        }

    if not mosques:
        raise RuntimeError("OpenStreetMap returned no Sudan mosque records; refusing to publish an empty dataset.")
    return sorted(mosques.values(), key=lambda mosque: (mosque["state"], mosque["name"]))


def main():
    parser = argparse.ArgumentParser(description="Fetch Sudan mosques from OpenStreetMap Overpass.")
    parser.add_argument("--output", type=Path, default=Path("mosques.json"))
    args = parser.parse_args()

    try:
        mosques = fetch_mosques()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(mosques, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    except (OSError, urllib.error.URLError, json.JSONDecodeError, RuntimeError) as error:
        print(f"Failed to fetch Sudan mosque data: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {len(mosques)} mosque records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
