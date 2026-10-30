

# reel-catalog (Pax's custom skill)

Turns "someone sent me a pile of reels" into a checked catalog:
who made each video, when, its link, what it says (caption), and
what it talks about — in plain words.

## Sources and rules (binding)

- The list of shared videos comes from the user's own chat, read
  with the user's permission (for example the Instagram thread
  itself). Record for each video: sender, thread time shown,
  author username as shown on the card, and the title/cover words.
- Enrich each video ONLY from public/authorised sources the user
  already has access to:
  - `instagram-cli posts --account-id <id> --username <author>
    --post-types REEL --limit <n>` for the author's public reels
    (captions usually carry the video's full spoken script).
  - `instagram-cli post --account-id <id> --url <reel-url>` for one
    exact reel once its URL is known.
  - `instagram-cli media-understanding --account-id <id>
    --media-ids <id>` for a narrative summary of a specific reel.
  - `research-tools` for ordinary public web pages about a video
    or tool (robots.txt always obeyed).
- NO anti-bot / detection-evasion scraping, no cookies beyond the
  user's own authorised connectors, no bulk download of message
  history, and no downloading the video files themselves unless
  the user explicitly asks for a specific one.
- Match honestly: a thread card is matched to an author reel only
  when author + a distinctive caption/cover phrase agree. If a
  video cannot be matched, the catalog says "not matched yet" —
  never guess a link.

## Helper script

    python3 scripts/fetch_author_reels.py --account-id <id> \
        --usernames julian.goldie_,hayderdotdev --limit 30 \
        --outdir ~/workspace/catalogs/<job-name>

Writes `reels.jsonl` (one record per reel: username, date, url,
post_id, likes, comments, caption) and `reels.csv`. Pagination
follows `next_cursor` until `--limit` per author is reached or
pages stop adding new reels. A 429 stops the run and is reported.

## Workflow

1. Read the thread, list every shared video in thread order
   (oldest → newest) with its shown author + cover words + time.
2. Collect the distinct author usernames from that list.
3. Run the helper script for those authors.
4. Match each thread video to a fetched reel (author + phrase).
5. For matched reels, summarise the caption in 1–2 plain
   sentences: what the video talks about, and any tool/name it
   pushes. For unmatched ones, use the cover words only and mark
   them clearly.
6. Deliver the catalog as a numbered list in thread order, and
   keep the JSONL/CSV under `~/workspace/catalogs/<job-name>/`.
## Available connectors

Use `muse.connector_search` to find the current connector docs before following
recovered instructions.
