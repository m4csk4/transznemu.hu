#!/usr/bin/env bash
#
# Fetches all unisex=yes toilets in Hungary from the Overpass API and
# writes them to data/budik.json in the schema the Budikereső map expects.
#
# Usage: ./scripts/fetch-budik.sh
# Requires: curl, jq

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$SCRIPT_DIR/../data/budik.json"
ENDPOINT="https://overpass-api.de/api/interpreter"

read -r -d '' QUERY <<'EOF' || true
[out:json][timeout:90];
area["ISO3166-1"="HU"][admin_level=2]->.hu;
(
  node["amenity"="toilets"]["unisex"="yes"](area.hu);
  way["amenity"="toilets"]["unisex"="yes"](area.hu);
  relation["amenity"="toilets"]["unisex"="yes"](area.hu);
);
out center meta;
EOF

echo "Querying Overpass…" >&2
RAW="$(curl -sS --fail \
  -A "transznemu.hu-budikereso/1.0 (https://transznemu.hu)" \
  --data-urlencode "data=$QUERY" "$ENDPOINT")"

echo "$RAW" | jq --arg updated "$(date -u +%Y-%m-%d)" '{ updated: $updated, toilets: [.elements[]
  | { type: .type, id: .id, lat: (.lat // .center.lat), lng: (.lon // .center.lon), ts: .timestamp, t: (.tags // {}) }
  | select(.lat != null and .lng != null)
  | .t as $t
  | ([ ($t["addr:street"] // empty), ($t["addr:housenumber"] // empty) ] | join(" ")) as $street
  | (if $street == "" then ($t["addr:city"] // "")
     else $street + (if $t["addr:city"] then ", " + $t["addr:city"] else "" end) end) as $addr
  | {
      name: ($t.name // $t.operator // "Nyilvános mosdó"),
      lat: .lat,
      lng: .lng,
      address: $addr,
      fee: ($t.fee // null),
      charge: ($t.charge // null),
      payment: [ $t | to_entries[]
                 | select(.key | startswith("payment:"))
                 | select(.value == "yes")
                 | (.key | ltrimstr("payment:"))
                 | select(test(":") | not) ],
      disposal: ($t["toilets:disposal"] // null),
      menstrual_products: ($t["toilets:menstrual_products"] // null),
      wheelchair: ($t.wheelchair // null),
      layer: ($t.layer // null),
      access: ($t.access // null),
      opening_hours: ($t.opening_hours // null),
      website: ($t.website // $t.url // $t["operator:website"] // null),
      description: ($t.description // null),
      checked: ($t.check_date // $t["survey:date"] // $t["source:date"] // null),
      edited: (.ts // null),
      osm_type: .type,
      osm_id: .id
    }] | sort_by(.name) }' > "$OUT"

echo "Wrote $(jq '.toilets | length' "$OUT") toilets to ${OUT}" >&2
