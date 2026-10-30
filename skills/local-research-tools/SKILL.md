

# research-tools (Pax's custom web research skill)

Runs on the isolated environment `~/workspace/tools/research-venv`
(httpx, trafilatura, readability-lxml, BeautifulSoup, Scrapy,
feedparser, tldextract, youtube-transcript-api — all pinned in
requirements.txt). Entry point:

    ~/workspace/tools/research-venv/bin/python scripts/research_tool.py <command>

Every command prints one JSON object:
`{ok, command, data, warnings, error, timing_ms}`.

## Commands

- `doctor` — library versions, yt-dlp availability, feature flags.
- `collect --urls <file> --outdir <dir> [--delay 1.0] [--max-pages 50]`
  — for each URL (one per line): enforce robots.txt, fetch politely
  (single identifying user agent, per-host delay), extract the
  readable article (trafilatura → readability → plain text), and
  record title/date/author/text. Deduplicates by canonical URL
  (tracking parameters stripped) and by content hash. Writes
  `records.jsonl` (full text) and `records.csv` (metadata) into the
  output directory. Every input produces exactly one record —
  failures included, with their real status and error.
- `youtube-info <watch-url|youtu.be|video-id> [--transcript]` —
  metadata via yt-dlp dump-json (no media download) and, on request,
  a transcript via youtube-transcript-api. Platform blocks (HTTP
  429, bot checks) are reported verbatim in the status fields.

## Operating rules (binding)

- robots.txt is ALWAYS obeyed. A denial is a result, not an
  obstacle. There is no flag to disable it.
- Rate limit: default 1 s between requests to a host; raise the
  delay for sensitive sources, never lower it to zero outside tests.
- No cookies, no logins, no account state, no paywall/CAPTCHA/
  anti-bot bypass — of any kind, ever. If a source blocks the tool,
  the record says so and the research moves to other sources.
- Respect copyright: collect for research and short quotation;
  exports keep source URLs and collection timestamps so claims can
  be traced and attributed.
- Scrapy is available in the venv for larger structured crawls;
  prefer `collect` for ordinary source gathering.

## Not implemented

JavaScript-rendered page collection (use the webapp-testing
skill's Playwright when a page truly needs a browser), scheduled
monitoring (no cron — collection is on demand), and any form of
authenticated or paywalled access.
## Available connectors

Use `muse.connector_search` to find the current connector docs before following
recovered instructions.
