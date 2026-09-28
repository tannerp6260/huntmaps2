# Independent expert-point collection (pending)

No expert points have been supplied. Do not populate the production CSV with generated
or assistant-selected coordinates. A human independently collects selections BEFORE
viewing algorithm ranks or recommendations. Two planners are preferable; six to ten
points per planner in the identical pilot, with the same input facts and time budget.
Record wall-clock planning time including access checks, experience and optics profile.
Keep unsuccessful/uncertain selections, rationale and alternative positions.

Provide a CSV with these required columns:

```csv
id,longitude,latitude,expert_id,selected_utc,rationale
```

Coordinates are WGS84 degrees. `selected_utc` is an ISO date/time; record source of
coordinates and planning-time logs separately. Expert identities may be pseudonyms.
Set `expert_csv` in a COPY of configs/comparison.json and use a new `work` directory.
Then run `python -m glassing.compare all --config <that-copy.json>`. Imported points
are transformed, checked against the technical observer domain and snapped to the
10m grid. Original coordinates, author, timestamp and rationale remain in experts.json.
All arm scores are computed for them in component_scores.csv, with no common-pool
rank assigned. This is a separate candidate-pool comparison, not a covert change to
the frozen 150-point arm comparison. Claimed independence is reviewer-attested, not
verified by parsing a CSV. A duplicate expert id or missing provenance fails.

Connected access is a separate optional CSV:

```csv
id,reachable,evidence,hike_km,gain_m,road_distance_km,road_pressure_proxy
```

`reachable=verified` requires evidence of a connected permitted approach, relevant
season/current closures and review date; ownership alone is insufficient. Known
`prohibited`, `denied` or `excluded` positions are removed from ALL arms. Unknown
positions remain unknown unless `require_verified_access=true`, which fails if none
qualify. Hike/gain constraints require supplied route evidence, not Euclidean distance.
Road-distance and pressure preference weights default to zero and are exported
separately; they are not added to habitat or secretly imposed on scientific arm scores.
A road-pressure proxy is not measured people or hunter counts.

Investigable/stalkable targets are a DIFFERENT input: WGS84 GeoJSON FeatureCollection
with polygon features whose properties include `followup_verified: true` and `evidence`.
Set `actionable_target_geojson` only for independently verified follow-up polygons.
They do not mask obstruction terrain or change raw-control scores. Report certified
visible target area separately; zero certified area means unknown, not impossible.

The randomized comparator currently samples the technical common pool. Without
access evidence it is NOT a completed legally feasible random benchmark. Once access
is resolved, apply the same required-access configuration to EVERY comparison arm.

Distribute only BLINDED_REVIEW.csv, BLINDED_TARGETS.csv, BLINDED_MAP.png and
REVIEW_INSTRUCTIONS.md to reviewers. Do not include component scores, comparison
maps, expert-versus-algorithm labels or DO_NOT_SHARE_REVIEW_KEY.json. Freeze completed
sheets before revealing the key. Northern development and southern held-out blocks
must not share tuning observations. Blank sheets supplied here contain no evidence.
