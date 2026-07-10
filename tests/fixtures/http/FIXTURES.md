# HTTP fixtures — provenance note

These fixtures are **synthetic**, written at Stage 3 to match the response
shapes recorded by the 2026-07-09 live probe and documented in the
Engineering Plan (Tool page §7):

- `jjkane_item_1619602.json` — shape of `GET www.jjkane.com/api/items/1619602`
  (fields incl. `imageUrls[]`, `imageCount`; CDN pattern
  `prod.cdn.jjkane.com/{id}-{n}`, extensionless).
- `publicsurplus_picloader_4043486.txt` — shape of
  `GET /sms/auction/ajaxpicloader?auctionId=4043486` (JS array of CloudFront
  URLs, not JSON).
- Purple Wave needs no response fixture: the resolver enumerates the CDN
  pattern `d323w7klwy72q3.cloudfront.net/i/a/{year}/{auction_id}ve/{lot}{L}.JPG`
  (probe example: `ED5334[A-I].JPG`).
- GovDeals override-path test data uses the probe's `webassets.lqdt1.com`
  GUID-style URL pattern.

Live capture was attempted at build time (2026-07-10) but the agent
environment's network policy blocks the auction hosts (proxy CONNECT 403).
Fidelity limit noted in the Validation Ledger; the CI live-smoke job and
Stage 4 real runs verify against the real endpoints, and real captures
should be committed here as regression fixtures per the Fixture Policy.
