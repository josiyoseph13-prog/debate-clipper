"""Step 1 tests: doctor, inspect, extract-text, page ops, safety."""
from __future__ import annotations

from conftest import PASSWORD, run_cli, sha256_of


# ---------- doctor & contract ----------

def test_doctor_ok():
    proc, r = run_cli("doctor")
    assert proc.returncode == 0 and r["ok"] is True
    assert r["command"] == "doctor"
    assert r["data"]["core_ok"] is True
    assert r["data"]["libraries"]["pypdf"] == "6.20.0"
    assert r["data"]["features"]["inspect"] is True
    assert r["data"]["features"]["page_operations"] is True
    assert r["data"]["features"]["ocr_tier"] is False  # no tesseract here


def test_json_contract_keys():
    _, r = run_cli("doctor")
    for key in ("ok", "command", "data", "warnings", "error", "timing_ms"):
        assert key in r
    assert r["error"] is None


# ---------- inspect ----------

def test_inspect_basic(fixtures):
    _, r = run_cli("inspect", str(fixtures["doc3"]))
    assert r["ok"] is True
    d = r["data"]
    assert d["page_count"] == 3
    assert d["encrypted"] is False
    assert d["metadata"]["title"] == "Step1 Fixture"
    assert d["metadata"]["author"] == "Pax Tests"
    assert d["pages"][0]["width_pt"] == 612.0
    assert d["pages"][0]["height_pt"] == 792.0
    assert d["sha256"].startswith("sha256:")


def test_inspect_encrypted_without_password(fixtures):
    _, r = run_cli("inspect", str(fixtures["encrypted"]))
    assert r["ok"] is True  # status reporting works without a password
    assert r["data"]["encrypted"] is True
    assert r["data"]["page_count"] is None
    assert any("password" in w for w in r["warnings"])


def test_inspect_encrypted_with_password(fixtures):
    _, r = run_cli("inspect", str(fixtures["encrypted"]),
                   "--password", PASSWORD)
    assert r["ok"] is True
    assert r["data"]["page_count"] == 3


def test_inspect_malformed(fixtures):
    proc, r = run_cli("inspect", str(fixtures["bad"]))
    assert proc.returncode == 2 and r["ok"] is False
    assert "could not read" in r["error"]


def test_inspect_missing_file(fixtures):
    _, r = run_cli("inspect", str(fixtures["dir"] / "nope.pdf"))
    assert r["ok"] is False and "not found" in r["error"]


# ---------- extract-text ----------

def test_extract_all_pages(fixtures):
    _, r = run_cli("extract-text", str(fixtures["doc3"]))
    assert r["ok"] is True
    assert r["data"]["pages_extracted"] == 3
    texts = [p["text"] for p in r["data"]["pages"]]
    assert "ALPHA PAGE ONE" in texts[0]
    assert "BRAVO PAGE TWO" in texts[1]
    assert "CHARLIE PAGE THREE" in texts[2]


def test_extract_page_filter(fixtures):
    _, r = run_cli("extract-text", str(fixtures["doc3"]), "--pages", "2")
    assert r["ok"] is True
    assert r["data"]["pages_extracted"] == 1
    assert r["data"]["pages"][0]["page"] == 2


def test_extract_to_file(fixtures, tmp_path):
    out = tmp_path / "text.txt"
    _, r = run_cli("extract-text", str(fixtures["doc3"]), "--out", str(out))
    assert r["ok"] is True and out.exists()
    assert "ALPHA PAGE ONE" in out.read_text()
    # second run without --overwrite must refuse
    _, r2 = run_cli("extract-text", str(fixtures["doc3"]), "--out", str(out))
    assert r2["ok"] is False and "already exists" in r2["error"]


def test_extract_encrypted(fixtures):
    _, r = run_cli("extract-text", str(fixtures["encrypted"]))
    assert r["ok"] is False and "password" in r["error"]
    _, r = run_cli("extract-text", str(fixtures["encrypted"]),
                   "--password", "wrong")
    assert r["ok"] is False and "wrong password" in r["error"]
    _, r = run_cli("extract-text", str(fixtures["encrypted"]),
                   "--password", PASSWORD)
    assert r["ok"] is True and r["data"]["pages_extracted"] == 3


def test_extract_out_of_range(fixtures):
    _, r = run_cli("extract-text", str(fixtures["doc3"]), "--pages", "9")
    assert r["ok"] is False and "out of bounds" in r["error"]


# ---------- page operations ----------

def test_merge(fixtures, tmp_path):
    before = sha256_of(fixtures["doc3"])
    out = tmp_path / "merged.pdf"
    _, r = run_cli("merge", str(fixtures["doc3"]), str(fixtures["doc2"]),
                   "--out", str(out))
    assert r["ok"] is True
    assert r["data"]["pages_out"] == 5
    assert sha256_of(fixtures["doc3"]) == before  # input untouched
    _, ri = run_cli("inspect", str(out))
    assert ri["data"]["page_count"] == 5


def test_split(fixtures, tmp_path):
    _, r = run_cli("split", str(fixtures["doc3"]), "--ranges", "1-2,3",
                   "--out-dir", str(tmp_path), "--prefix", "chunk")
    assert r["ok"] is True
    outs = r["data"]["outputs"]
    assert len(outs) == 2
    _, r1 = run_cli("inspect", outs[0]["out"])
    _, r2 = run_cli("inspect", outs[1]["out"])
    assert r1["data"]["page_count"] == 2
    assert r2["data"]["page_count"] == 1


def test_rotate(fixtures, tmp_path):
    out = tmp_path / "rot.pdf"
    _, r = run_cli("rotate", str(fixtures["doc3"]), "--angle", "90",
                   "--pages", "1", "--out", str(out))
    assert r["ok"] is True
    _, ri = run_cli("inspect", str(out))
    assert ri["data"]["pages"][0]["rotation"] == 90
    assert ri["data"]["pages"][1]["rotation"] == 0


def test_rotate_invalid_angle(fixtures, tmp_path):
    _, r = run_cli("rotate", str(fixtures["doc3"]), "--angle", "45",
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "angle" in r["error"]


def test_reorder(fixtures, tmp_path):
    out = tmp_path / "re.pdf"
    _, r = run_cli("reorder", str(fixtures["doc3"]), "--order", "3,1,2",
                   "--out", str(out))
    assert r["ok"] is True
    _, rt = run_cli("extract-text", str(out), "--pages", "1")
    assert "CHARLIE PAGE THREE" in rt["data"]["pages"][0]["text"]


def test_reorder_not_a_permutation(fixtures, tmp_path):
    _, r = run_cli("reorder", str(fixtures["doc3"]), "--order", "1,1,2",
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "exactly once" in r["error"]


def test_extract_pages_order_preserved(fixtures, tmp_path):
    out = tmp_path / "sub.pdf"
    _, r = run_cli("extract-pages", str(fixtures["doc3"]), "--pages", "3,1",
                   "--out", str(out))
    assert r["ok"] is True and r["data"]["pages_out"] == 2
    _, rt = run_cli("extract-text", str(out))
    texts = [p["text"] for p in rt["data"]["pages"]]
    assert "CHARLIE" in texts[0] and "ALPHA" in texts[1]


# ---------- output safety ----------

def test_output_must_not_equal_input(fixtures):
    _, r = run_cli("merge", str(fixtures["doc3"]), str(fixtures["doc2"]),
                   "--out", str(fixtures["doc3"]), "--overwrite")
    assert r["ok"] is False and "must not overwrite an input" in r["error"]


def test_existing_output_refused_then_overwrite(fixtures, tmp_path):
    out = tmp_path / "m.pdf"
    args = ("merge", str(fixtures["doc3"]), str(fixtures["doc2"]),
            "--out", str(out))
    _, r1 = run_cli(*args)
    assert r1["ok"] is True
    _, r2 = run_cli(*args)
    assert r2["ok"] is False and "already exists" in r2["error"]
    _, r3 = run_cli(*args, "--overwrite")
    assert r3["ok"] is True


def test_merge_single_input_refused(fixtures, tmp_path):
    _, r = run_cli("merge", str(fixtures["doc3"]),
                   "--out", str(tmp_path / "x.pdf"))
    assert r["ok"] is False and "at least two" in r["error"]
