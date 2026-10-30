

# pdf-tools (Pax's custom PDF skill — Steps 1–3)

Local PDF work through one CLI that always answers with a single JSON
object, so results can be checked instead of assumed.

## Environment

- Python environment: `~/workspace/pdf-skill-project/pdf-venv`
  (isolated; created for this project — the skill is NOT yet adopted
  into Pax's live skills and must pass the security gate first).
- Entry point: `scripts/pdf_tool.py` inside this skill folder.
- Run `doctor` first in any new environment:

  `pdf-venv/bin/python scripts/pdf_tool.py doctor`

## Commands (steps 1–3)

- `doctor` — library versions, binaries, and which features are on.
- `inspect <file> [--password PW]` — page count, metadata, per-page
  size/rotation, encryption status, file hash. On an encrypted file
  without a password it reports the encryption status and what a
  password would unlock.
- `extract-text <file> [--pages 1-3,5] [--password PW] [--out f.txt]`
  — page-by-page text (pdfplumber). Without `--out`, page text is in
  the JSON; with `--out` the text goes to a new file and the JSON
  carries counts and the file's hash.
- `merge <a.pdf> <b.pdf> [...] --out <new.pdf>` — combine in order.
- `split <file> --ranges 1-2,3 --out-dir <dir> [--prefix name]` — one
  new file per range chunk.
- `rotate <file> --angle 90 [--pages 1,3-4] --out <new.pdf>`
- `reorder <file> --order 3,1,2 --out <new.pdf>` — the order must list
  every page exactly once.
- `extract-pages <file> --pages 3,1 --out <new.pdf>` — order preserved.

- `extract-tables <file> [--pages 1-3] [--out tables.json|tables.csv]`
  — detected tables per page (pdfplumber), rows as data.
- `create (--spec spec.json | --from-text notes.txt) --out <new.pdf>`
  — build a PDF. Spec blocks: heading (level 1–3), paragraph, table
  (rows, optional header repeat), spacer, pagebreak. Text mode:
  `# `/`## ` lines are headings, other lines paragraphs. Page numbers
  are added automatically.
- `stamp <file> --text CONFIDENTIAL [--pages 1-3] [--opacity 0.15]
  [--angle 45] [--under] --out <new.pdf>` — translucent rotated text
  over (default) or under the content.
- `form-fields <file>` — list AcroForm fields with type and value.
- `fill-form <file> --data values.json --out <new.pdf>` — fill fields
  from a JSON object; unknown field names are an error. JSON `true` /
  `false` map to checkbox on/off.
- `encrypt <file> --password PW --out <new.pdf>` — AES-256 copy;
  the command verifies the output really is encrypted.
- `decrypt <file> --password PW --out <new.pdf>` — unencrypted copy
  from a document you hold the password for; output is verified.
- `edit-metadata <file> [--title T] [--author A] [--subject S]
  [--keywords K] [--creator C] [--clear title,author] --out <new.pdf>`
  — write a copy with changed metadata; before/after are reported.
- `compress <file> --out <new.pdf>` — lossless recompression of page
  content streams (images untouched); reports real before/after sizes
  and warns when nothing was saved.
- `optimize <file> [--linearize] --out <new.pdf>` — pikepdf tier:
  stronger lossless optimization (object streams, orphan removal),
  structural repair on open, optional linearization. Output is
  verified against the input's page count.

Page numbers are 1-based everywhere.

## Result contract

Every command prints one JSON object:
`{"ok", "command", "data", "warnings", "error", "timing_ms"}`.
Exit code 0 = ok, 2 = user error (bad path/args/password/file),
3 = unexpected error. Never report success from anything but
`ok: true` plus the returned counts/hashes.

## Safety rules

- Input PDFs are never modified; outputs are new files.
- An output that already exists is refused unless `--overwrite` is
  passed explicitly; an output path equal to an input is always
  refused.
- Encrypted inputs need `--password`; wrong passwords and malformed
  files produce clean JSON errors. Never try to guess or crack a
  password.
- All processing is local; the tool makes no network calls.

## Not implemented

OCR (needs the tesseract binary, not installed) — the remaining
optional tier. XFA forms, digital signatures and PDF/A are out of
scope. `doctor` reports tier availability honestly.
## Available connectors

Use `muse.connector_search` to find the current connector docs before following
recovered instructions.
