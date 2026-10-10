# Source acquisition recovery — 2026-10-10 UTC

The `scouting-2026-10-10` preparation failed on tree cover, while its DEM was already
available. USGS RCMAP returned an HTTP 200 XML exception instead of a GeoTIFF. The
old GUI adapter published that response into the source cache; subsequent retries
reused the same bytes. The sampling wrapper then reported an unrelated DEM error.

## Implementation

- GUI acquisition validates response contents before publishing a reusable file
  or manifest entry. OGC/HTML errors, unreadable/truncated GeoTIFFs, incomplete
  GeoJSON and inadequate geographic coverage fail with a named source diagnostic.
  Raster decoding uses bounded strips; original coverage and NoData rules remain.
- Matching legacy cache entries are checked against their original URL and digest
  before recovery. Rejected bytes and complete provenance are retained under
  `downloads/rejected/<id>/`; only rejected entries leave the reusable manifest.
  Changed bytes or requests stop without replacing evidence.
- Publication and recovery share the download-manifest lock. Interrupted transfers
  retain their previous bytes before retry. Transfer accounting includes received
  error bodies and remains cumulative; source rejection never refunds allowance.
- Workers stream the current subprocess diagnostic into their logs and failure
  summary. A stale acquisition report cannot hide a new checksum failure. Provider
  errors identify the source and explain that retry reacquires rejected responses.
- All changes are normal GUI adapters outside the protected engine trees. New
  expanded-search manifests fingerprint the acquisition validator. Source requests,
  product year, resolution, analytical masks, settings and model assumptions remain.

## Verification

The initial HTTP 200 XML regression failed before the fix: no error was raised and
the response became reusable. The corrected adapter passes 13 acquisition tests,
including actual jobs/owner/sampling against a controlled localhost provider. That
journey preserves and replaces a matching legacy XML entry, reports a fresh provider
error, rejects a subsequently corrupted DEM, and completes after the provider starts
returning valid TIFF bytes. Checked source bytes and approval remain identical;
the transfer ledger counts every response across attempts.

Other cases cover misleading content type, HTTP 503 bodies, truncated raster blocks,
unknown vegetation, extent checks, JSON errors, changed URLs/checksums, transfer
ceilings, source changes during validation, and concurrent requests with one
publication and no lost manifest entries.
Existing interrupted-transfer, recovery and storage tests also pass.

The first full suite (`/tmp/huntmaps-check-15ng4gb8`) passed 172 backend tests,
format/build and the recovery worker, then timed out in the existing training
boundary-drawing browser check. Its audit reports 11,830 files and zero changes.
The training check passed on its isolated rerun (`/tmp/huntmaps-check-hja5oz3v`),
including the real 600-location recovery worker. The final complete `./gui/check`
passed 173 backend tests, all 20 browser journeys, formatting/type checking/build,
and the actual 600-location recovery worker. Training passed within this complete
rerun. Diagnostics: `/tmp/huntmaps-check-_y6yhqay`; its audit covers 11,834 files and
reports zero changes. The separate before/after byte audit retained all 503 original
owner records and found no changes outside the explicitly recovered incomplete run.

The actual saved plan was retried through the owner's normal local job API:
`28ade6059c8548ca92fbb0de8bb9cf32`. It failed in 3.3 seconds on a fresh USGS tree-cover
exception. Both the original and newly received 742-byte responses are preserved
byte-for-byte with their original hashes and metadata in the run's
`downloads/rejected/`; its reusable download manifest is empty. The durable ledger
increased from 742 to 1,484 bytes of the existing 30,000,000-byte ceiling. The area,
source configuration, scouting settings and reviewed signature remain identical.
Other saved results and all preexisting owner records remain unchanged. Evidence:
`/tmp/huntmaps-acquisition-fix-n38xfbcg/{saved-plan-retry,preservation}.json`.

The running owner's backend had imported the old failure classifier before this
change. This retry already displays the corrected source error and stage, while its
stored category remains `processing_failed`. Restarting the GUI loads the new
`provider_failed` classification and the more specific recovery hint. Fresh-worker
and fresh-backend tests verify that classification; existing job records are retained.

## Provider availability

Bounded diagnostic metadata and small coverage requests are retained in
`/tmp/huntmaps-acquisition-fix-n38xfbcg`. The existing WCS 1.0 request returns a Java
server exception. WCS 2.0.1 DescribeCoverage successfully advertises the same product
and 2023 time slice, but small GetCoverage requests with valid spatial axes fail
inside the provider's coverage reader (`startTime` is null). No working replacement
request was verified, so the application does not silently change requests, products,
years, resolution or providers. No provider availability is inferred from offline
tests. Protocol reference: [GeoServer WCS documentation](https://docs.geoserver.org/stable/en/user/services/wcs/reference/).
