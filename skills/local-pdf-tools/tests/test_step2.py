"""Step 2 tests: create, extract-tables, stamp, forms, encrypt/decrypt."""
from __future__ import annotations

import json

from conftest import PASSWORD, run_cli, sha256_of


def _write_json(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


# ---------- create ----------

def test_create_from_spec(tmp_path):
    spec = _write_json(tmp_path / "spec.json", {
        "title": "Spec Doc", "author": "Pax Tests",
        "blocks": [
            {"type": "heading", "text": "Quarterly Summary", "level": 1},
            {"type": "paragraph", "text": "Revenue grew this quarter."},
            {"type": "table", "header": True,
             "rows": [["Region", "Sales"], ["North", "CellValue9"]]},
            {"type": "pagebreak"},
            {"type": "paragraph", "text": "Second page notes."},
        ]})
    out = tmp_path / "created.pdf"
    _, r = run_cli("create", "--spec", str(spec), "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["pages_out"] == 2
    _, ri = run_cli("inspect", str(out))
    assert ri["data"]["metadata"]["title"] == "Spec Doc"
    _, rt = run_cli("extract-text", str(out))
    all_text = " ".join(p["text"] for p in rt["data"]["pages"])
    assert "Quarterly Summary" in all_text
    assert "CellValue9" in all_text
    assert "Second page notes." in all_text


def test_create_from_text(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("# My Title\nHello world line\n## Section\nBody line\n",
                   encoding="utf-8")
    out = tmp_path / "from-text.pdf"
    _, r = run_cli("create", "--from-text", str(src), "--out", str(out))
    assert r["ok"] is True, r["error"]
    _, rt = run_cli("extract-text", str(out))
    text = rt["data"]["pages"][0]["text"]
    assert "My Title" in text and "Hello world line" in text


def test_create_invalid_spec(tmp_path):
    spec = _write_json(tmp_path / "bad.json",
                       {"blocks": [{"type": "teleport", "text": "x"}]})
    _, r = run_cli("create", "--spec", str(spec),
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "unknown type" in r["error"]


def test_create_missing_spec_and_source_rules(tmp_path):
    _, r = run_cli("create", "--spec", str(tmp_path / "nope.json"),
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "not found" in r["error"]
    _, r = run_cli("create", "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "exactly one" in r["error"]


# ---------- extract-tables ----------

def test_extract_tables_found(fixtures):
    _, r = run_cli("extract-tables", str(fixtures["table"]))
    assert r["ok"] is True
    assert r["data"]["tables_total"] >= 1
    rows = [row for p in r["data"]["pages"] for t in p["tables"]
            for row in t["rows"]]
    flat = [cell for row in rows for cell in row]
    assert "Apples" in flat and "42" in flat


def test_extract_tables_none(fixtures):
    _, r = run_cli("extract-tables", str(fixtures["doc3"]))
    assert r["ok"] is True and r["data"]["tables_total"] == 0


def test_extract_tables_csv(fixtures, tmp_path):
    out = tmp_path / "tables.csv"
    _, r = run_cli("extract-tables", str(fixtures["table"]),
                   "--out", str(out))
    assert r["ok"] is True and out.exists()
    assert "Apples" in out.read_text()


# ---------- stamp ----------

def _squashed(text: str) -> str:
    """Whitespace-stripped text. Rotated stamp text extracts one char
    per line (and may read in reverse along its rotated baseline), so
    stamp assertions accept the word or its reverse once squashed."""
    return "".join(text.split())


def _has_stamp(text: str, word: str) -> bool:
    squashed = _squashed(text)
    return word in squashed or word[::-1] in squashed


def test_stamp_all_pages(fixtures, tmp_path):
    before = sha256_of(fixtures["doc3"])
    out = tmp_path / "stamped.pdf"
    _, r = run_cli("stamp", str(fixtures["doc3"]), "--text", "CONFIDENTIAL",
                   "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["stamped_pages"] == [1, 2, 3]
    assert sha256_of(fixtures["doc3"]) == before
    _, rt = run_cli("extract-text", str(out), "--pages", "1")
    text = rt["data"]["pages"][0]["text"]
    assert "ALPHA PAGE ONE" in text
    assert _has_stamp(text, "CONFIDENTIAL")


def test_stamp_selected_pages(fixtures, tmp_path):
    out = tmp_path / "stamped2.pdf"
    _, r = run_cli("stamp", str(fixtures["doc3"]), "--text", "DRAFT",
                   "--pages", "2", "--out", str(out))
    assert r["ok"] is True
    _, rt = run_cli("extract-text", str(out))
    texts = [p["text"] for p in rt["data"]["pages"]]
    assert not _has_stamp(texts[0], "DRAFT")
    assert _has_stamp(texts[1], "DRAFT")


def test_stamp_invalid_opacity(fixtures, tmp_path):
    _, r = run_cli("stamp", str(fixtures["doc3"]), "--text", "X",
                   "--opacity", "1.5", "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "opacity" in r["error"]


# ---------- forms ----------

def test_form_fields(fixtures):
    _, r = run_cli("form-fields", str(fixtures["form"]))
    assert r["ok"] is True, r["error"]
    by_name = {f["name"]: f for f in r["data"]["fields"]}
    assert set(by_name) == {"name", "agree", "color"}
    assert by_name["name"]["type"] == "text"


def test_fill_form(fixtures, tmp_path):
    data = _write_json(tmp_path / "values.json",
                       {"name": "Jo", "agree": True, "color": "green"})
    out = tmp_path / "filled.pdf"
    _, r = run_cli("fill-form", str(fixtures["form"]), "--data", str(data),
                   "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["values_read_back"]["name"] == "Jo"
    assert r["data"]["values_read_back"]["agree"] == "/Yes"
    _, rf = run_cli("form-fields", str(out))
    by_name = {f["name"]: f for f in rf["data"]["fields"]}
    assert by_name["name"]["value"] == "Jo"


def test_fill_form_unknown_field(fixtures, tmp_path):
    data = _write_json(tmp_path / "v.json", {"nope": "x"})
    _, r = run_cli("fill-form", str(fixtures["form"]), "--data", str(data),
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "unknown field" in r["error"]


def test_fill_form_bad_json(fixtures, tmp_path):
    data = tmp_path / "v.json"
    data.write_text("this is not json", encoding="utf-8")
    _, r = run_cli("fill-form", str(fixtures["form"]), "--data", str(data),
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "not valid JSON" in r["error"]


def test_form_fields_on_plain_pdf(fixtures):
    _, r = run_cli("form-fields", str(fixtures["doc3"]))
    assert r["ok"] is True and r["data"]["field_count"] == 0
    assert any("no form fields" in w for w in r["warnings"])


# ---------- encrypt / decrypt ----------

def test_encrypt_roundtrip(fixtures, tmp_path):
    out = tmp_path / "enc.pdf"
    _, r = run_cli("encrypt", str(fixtures["doc3"]),
                   "--password", "long-password-1", "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["verified_encrypted"] is True
    _, ri = run_cli("inspect", str(out))
    assert ri["data"]["encrypted"] is True
    _, rx = run_cli("extract-text", str(out))
    assert rx["ok"] is False
    _, rx = run_cli("extract-text", str(out),
                    "--password", "long-password-1")
    assert rx["ok"] is True


def test_encrypt_requires_password(fixtures, tmp_path):
    _, r = run_cli("encrypt", str(fixtures["doc3"]),
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "requires --password" in r["error"]


def test_decrypt_roundtrip(fixtures, tmp_path):
    out = tmp_path / "dec.pdf"
    _, r = run_cli("decrypt", str(fixtures["encrypted"]),
                   "--password", PASSWORD, "--out", str(out))
    assert r["ok"] is True, r["error"]
    assert r["data"]["verified_unencrypted"] is True
    _, ri = run_cli("inspect", str(out))
    assert ri["data"]["encrypted"] is False
    assert ri["data"]["page_count"] == 3


def test_decrypt_wrong_password(fixtures, tmp_path):
    _, r = run_cli("decrypt", str(fixtures["encrypted"]),
                   "--password", "nope", "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False


def test_decrypt_not_encrypted(fixtures, tmp_path):
    _, r = run_cli("decrypt", str(fixtures["doc3"]), "--password", "x",
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "not encrypted" in r["error"]


# ---------- doctor reflects step 2 ----------

def test_doctor_step2_features():
    _, r = run_cli("doctor")
    f = r["data"]["features"]
    assert f["create"] is True and f["forms"] is True
    assert f["watermark"] is True and f["extract_tables"] is True
    assert f["encrypt_decrypt"] is True
    # (the step-2 era assertion "optimize tier stays off" was retired
    # in step 4, which installs pikepdf; test_step4 asserts it is on.)
