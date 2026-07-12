# Tavily Research API — Live Verification Findings

2026-07-12. Postman MCP was not available and not used, per instructions.
Verified directly against the real Tavily API using disposable probe
scripts (not committed) plus the real `valuation-research-scout` CLI.
Several details differ from Tavily's published API reference
(https://docs.tavily.com/documentation/api-reference/endpoint/research and
.../research-get); each is a genuine live-behavior finding, not a guess.

## Endpoint behavior (confirmed working as documented)

- `POST https://api.tavily.com/research`, `Authorization: Bearer tvly-...`
- `GET https://api.tavily.com/research/{request_id}` for polling
- `model`: `mini` | `pro` | `auto` (default `auto`) — both `mini` and `pro`
  confirmed working live
- Async task creation + polling loop: confirmed working
- Completed response: `status: "completed"`, `content` (matches the
  requested `output_schema`), `sources[]` (`title`, `url`, `favicon`)
- Failure shape: `status: "failed"`, `200` — not separately tested live
  (no real task failed during commissioning) but the client's handling
  is unit-tested against a scripted response
- GET polling does not count against rate limits (per Tavily's own guidance)

## Discrepancies vs. published docs (all confirmed live, all handled in code)

1. **`POST /research` returns HTTP 200, not the documented 201.** Body is
   otherwise as documented (`request_id`, `status: "pending"`, ...). Fixed:
   `RealTavilyClient.create_task` accepts both 200 and 201.

2. **`output_schema` may only contain `properties` and `required` at the
   top level.** Sending pydantic's natural `model_json_schema()` output
   (which includes `type`, `title`, `$defs`, `description` at the top
   level) is rejected: `400 "Output schema contains unexpected keys: type."`
   Not stated anywhere in the docs. Fixed: `schema.tavily_output_schema()`
   strips these before sending.

3. **`$ref`/`$defs` are rejected outright**, not just disallowed as a
   top-level key — Tavily needs a fully self-contained (inlined) schema
   with no JSON Schema references at any depth. Fixed:
   `schema._inline_refs()` recursively resolves every `$ref` into its
   full definition before sending.

4. **`title` and `additionalProperties` are rejected at every nesting
   depth**, not just the top level (`400 "unexpected keys:
   additionalProperties, title"`). Pydantic emits both on every nested
   object schema because the repo's `_Contract` base sets
   `extra="forbid"`. Fixed: stripped recursively.

5. **Every property must carry its own `description`, including
   object-typed properties**, not just leaf scalar fields (`400 "Property
   'confidence' missing required 'description' field"`). A few nested
   model classes (`SourcePlatformAnalysis`, `MileagePattern`,
   `ModelYearPattern`, `Modifier`, `RepresentativeComparable`) initially had
   no class docstring, which is what supplies an object type's own
   description after `$ref` inlining. Fixed: added docstrings to all of
   them.

6. **Genuine contract conflict — nullable fields cannot use JSON Schema's
   `"type": [T, "null"]` list form at all.** The approved v0.2 output
   schema on the Valuation Research Scout AI-OS record explicitly types
   `year`, `mileage`, `location`, and `source_url` this way (verbatim from
   the record: `"year": {"type": ["integer", "null"], ...}`). Tavily's live
   API rejects it: `400 "'type' must be a string, got list. Union types
   (e.g. ['string', 'null']) are not supported - use a single type."`
   Tavily's structured-output feature currently has no way to express
   "this field is optional/nullable" at all — this is a real conflict
   between the approved AI-OS contract and current Tavily API behavior,
   not a design choice.

   **Resolution (documented, not silently redesigned):** the field is
   collapsed to its single non-null type on the *wire request* to Tavily
   only. The `ResearchContent` pydantic contract — the actual validation
   source of truth this repo enforces — still declares these fields
   `int | None` / `str | None` unchanged, so the artifact contract itself
   is unaffected. Practical effect: Tavily's research model will always
   return *some* value of the declared type for these fields rather than
   JSON `null`; the field's `description` text ("... when available") is
   what now signals optionality to the model, not the schema shape. This
   held up in practice across both commissioning runs — comparables
   consistently populated `year`/`mileage` when known.

   This should be revisited if Tavily adds real nullable-type support to
   `output_schema`, or flagged back to the AI-OS record if the contract's
   nullable-field typing should be revised to match what Tavily can
   actually accept.

## Not verified live

- Explicit `status: "failed"` response shape from a real failed task (no
  task failed during commissioning; failure handling is unit-tested against
  a scripted response instead)
- Rate-limit (`429`) and plan-limit (`432`/`433`) responses
