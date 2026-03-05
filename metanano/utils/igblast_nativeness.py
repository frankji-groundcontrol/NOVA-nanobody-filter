#!/usr/bin/env python3
"""
VHH nativeness scoring via standalone igblastp (local copy for MetaNano to include custom camelid database).
通过独立 igblastp 进行 VHH 天然性评分（MetaNano 本地实现）。

This is a self-contained implementation adapted to live inside
NOVA-nanobody-filter under `metanano.utils.igblast_nativeness`. It uses
the IgBLAST binaries and databases vendored under
`NOVA-nanobody-filter/igblast`.
这是一个适配为位于 NOVA-nanobody-filter 内部的自包含实现，
路径为 `metanano.utils.igblast_nativeness`。它使用
`NOVA-nanobody-filter/igblast` 目录下随附的 IgBLAST 可执行文件和数据库。
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Paths and constants (adapted for MetaNano location)
# ---------------------------------------------------------------------------

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
IGBLAST_DIR = os.path.join(PROJECT_ROOT, "igblast")

os.environ.setdefault("IGDATA", IGBLAST_DIR)

ALLOWED_AAS = set("ACDEFGHIKLMNPQRSTVWY")
CAMELID_DB_V = os.path.join(IGBLAST_DIR, "database", "camelid_V")
HUMAN_DB_V = os.path.join(IGBLAST_DIR, "database", "human_V")


def read_fasta(path: str) -> List[Tuple[str, str]]:
    """
    Minimal FASTA reader used by the scoring pipeline.
    评分流水线使用的最小 FASTA 读取器。
    """
    items: List[Tuple[str, str]] = []
    name: Optional[str] = None
    seq_parts: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    items.append((name, "".join(seq_parts)))
                name = line[1:].split()[0]
                seq_parts = []
            else:
                seq_parts.append(line)
        if name is not None:
            items.append((name, "".join(seq_parts)))
    return items


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def compute_pairwise_identity(aln_query: str, aln_germ: str) -> Optional[float]:
    if not aln_query or not aln_germ or len(aln_query) != len(aln_germ):
        return None
    match = 0
    denom = 0
    for a, b in zip(aln_query, aln_germ):
        if a == "-" or b == "-":
            continue
        denom += 1
        if a == b:
            match += 1
    if denom == 0:
        return None
    return match / denom


def safe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def safe_int(x: str) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None


def _first_valid(row: Dict[str, str], keys: Iterable[str]) -> str:
    for k in keys:
        v = (row.get(k) or "").strip()
        if v and v != "NA":
            return v
    return ""


# ---------------------------------------------------------------------------
# VHH hallmark definitions
# ---------------------------------------------------------------------------

_FR2_IMGT_START = 39

VHH_HALLMARKS: Dict[int, Tuple[int, frozenset, frozenset]] = {
    42: (42 - _FR2_IMGT_START, frozenset("FY"),    frozenset("VLI")),
    49: (49 - _FR2_IMGT_START, frozenset("EQ"),    frozenset("GA")),
    50: (50 - _FR2_IMGT_START, frozenset("RCWF"),  frozenset("LIV")),
    52: (52 - _FR2_IMGT_START, frozenset("GFLS"),  frozenset("W")),
}

_EXPECTED_V_REGION_LEN = 100


# ---------------------------------------------------------------------------
# IgBLAST runner
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IgBlastConfig:
    igblastp_path: str = os.path.join(IGBLAST_DIR, "bin", "igblastp")
    domain_system: str = "imgt"
    organism: str = "camelid"
    num_threads: int = 1
    camelid_db_v: str = CAMELID_DB_V
    human_db_v: Optional[str] = HUMAN_DB_V
    extra_args: Tuple[str, ...] = ()


def run_igblastp(
    fasta_path: str,
    out_path: str,
    cfg: IgBlastConfig,
    *,
    use_human: bool = False,
) -> None:
    """Run igblastp with BLAST tabular output (fmt 7 + qseq/sseq)."""
    igblastp = shutil.which(cfg.igblastp_path) or cfg.igblastp_path
    if use_human:
        if not cfg.human_db_v:
            raise ValueError("Human DB requested but human_db_v not provided.")
        db_v = cfg.human_db_v
        organism = "human"
    else:
        if not cfg.camelid_db_v:
            raise ValueError("Camelid DB path not provided.")
        db_v = cfg.camelid_db_v
        organism = cfg.organism
    cmd = [
        igblastp,
        "-query", fasta_path,
        "-germline_db_V", db_v,
        "-organism", organism,
        "-domain_system", cfg.domain_system,
        "-outfmt", "7 std qseq sseq",
        "-num_threads", str(cfg.num_threads),
        "-out", out_path,
        *cfg.extra_args,
    ]
    igblast_root = os.path.dirname(os.path.dirname(igblastp))
    env = {**os.environ, "IGDATA": igblast_root}
    p = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError(
            "igblastp failed.\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stdout:\n{p.stdout}\n"
            f"stderr:\n{p.stderr}\n"
        )


# ---------------------------------------------------------------------------
# igblastp fmt7 output parser
# ---------------------------------------------------------------------------

_REGION_LINE_RE = re.compile(
    r"((?:FR|CDR|FWR)[123])-IMGT"
    r"(?:\s*\(germline\))?"
    r"\s+(\d+)\s+(\d+)"
    r"\s+(\d+)"
    r"\s+(\d+)\s+(\d+)\s+(\d+)"
    r"\s+([\d.]+)",
)

_TOTAL_LINE_RE = re.compile(
    r"Total\s+N/A\s+N/A"
    r"\s+(\d+)"
    r"\s+(\d+)\s+(\d+)\s+(\d+)"
    r"\s+([\d.]+)",
)


@dataclass
class IgBlastQueryResult:
    """Parsed result for one query from igblastp fmt7 output."""

    query_id: str
    v_call: Optional[str] = None
    v_identity: Optional[float] = None       # 0-1 scale
    v_sequence_start: Optional[int] = None   # 1-based
    v_sequence_end: Optional[int] = None     # 1-based
    v_germline_start: Optional[int] = None
    v_germline_end: Optional[int] = None
    v_alignment_length: Optional[int] = None
    query_alignment: Optional[str] = None
    germline_alignment: Optional[str] = None
    region_bounds: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    region_identity: Dict[str, float] = field(default_factory=dict)
    total_identity: Optional[float] = None

    def to_row_dict(self, seq: str = "") -> Dict[str, str]:
        """
        Convert to a dict with keys compatible with the scoring functions.
        Bridges the gap between fmt7 output and the field names used by
        the scoring code.
        """
        d: Dict[str, str] = {}

        d["v_call"] = self.v_call or ""
        d["j_call"] = ""

        if self.v_identity is not None:
            d["v_identity"] = str(self.v_identity * 100.0)

        if self.v_sequence_start is not None:
            d["v_sequence_start"] = str(self.v_sequence_start)
        if self.v_sequence_end is not None:
            d["v_sequence_end"] = str(self.v_sequence_end)
        if self.v_alignment_length is not None:
            d["v_alignment_length"] = str(self.v_alignment_length)

        if self.query_alignment:
            d["v_sequence_alignment"] = self.query_alignment
        if self.germline_alignment:
            d["v_germline_alignment"] = self.germline_alignment

        # Map region bounds to AIRR-style field names
        _region_map = {
            "FR1":  ("fwr1_start", "fwr1_end"),
            "CDR1": ("cdr1_start", "cdr1_end"),
            "FR2":  ("fwr2_start", "fwr2_end"),
            "CDR2": ("cdr2_start", "cdr2_end"),
            "FR3":  ("fwr3_start", "fwr3_end"),
        }
        for region, (start, end) in self.region_bounds.items():
            rkey = region.replace("FWR", "FR")
            if rkey in _region_map:
                sk, ek = _region_map[rkey]
                d[sk] = str(start)
                d[ek] = str(end)

        # Extract FR2 amino acid sequence for hallmark checking
        if seq:
            seq = seq.strip().upper()
            fr2_bounds = self.region_bounds.get("FR2") or self.region_bounds.get("FWR2")
            if fr2_bounds:
                fr2_start, fr2_end = fr2_bounds
                d["fwr2_aa"] = seq[fr2_start - 1 : fr2_end]

            fr3_bounds = self.region_bounds.get("FR3") or self.region_bounds.get("FWR3")
            if fr3_bounds:
                d["fwr3_end"] = str(fr3_bounds[1])

        return d


def parse_igblastp_fmt7(output_path: str) -> Dict[str, IgBlastQueryResult]:
    """
    Parse igblastp fmt7 output file into a dict of query_id -> IgBlastQueryResult.
    """
    results: Dict[str, IgBlastQueryResult] = {}
    current: Optional[IgBlastQueryResult] = None
    in_alignment_summary = False
    hit_count = 0

    with open(output_path) as f:
        for line in f:
            line = line.rstrip("\n\r")

            # New query block
            if line.startswith("# Query: "):
                if current is not None:
                    results[current.query_id] = current
                qid = line[len("# Query: "):].strip()
                current = IgBlastQueryResult(query_id=qid)
                in_alignment_summary = False
                hit_count = 0
                continue

            if current is None:
                continue

            # Alignment summary section start
            if line.startswith("# Alignment summary"):
                in_alignment_summary = True
                continue

            # Hit table section start — ends alignment summary
            if line.startswith("# Hit table"):
                in_alignment_summary = False
                continue

            # Comment lines (# Fields, # N hits found, etc.)
            if line.startswith("#"):
                continue

            # Alignment summary region lines (tab-delimited):
            #   FR1-IMGT\t1\t25\t25\t22\t3\t0\t88
            #   Total\tN/A\tN/A\t99\t65\t32\t2\t65.7
            if in_alignment_summary:
                stripped = line.strip()
                m = _REGION_LINE_RE.match(stripped)
                if m:
                    region = m.group(1).replace("FWR", "FR")
                    r_from = int(m.group(2))
                    r_to = int(m.group(3))
                    pct_id = float(m.group(8)) / 100.0
                    current.region_bounds[region] = (r_from, r_to)
                    current.region_identity[region] = pct_id
                    continue

                m = _TOTAL_LINE_RE.match(stripped)
                if m:
                    current.v_alignment_length = int(m.group(1))
                    current.total_identity = float(m.group(5)) / 100.0
                    continue
                # Unrecognized summary line — skip
                continue

            # Hit table data line (not a comment, not in summary)
            # chain_type \t qid \t sid \t pct_id \t aln_len \t mm \t
            # gap_opens \t gaps \t q_start \t q_end \t s_start \t s_end \t
            # evalue \t bit_score \t qseq \t sseq
            parts = line.split("\t")
            if len(parts) >= 15 and parts[0] == "V":
                hit_count += 1
                if hit_count == 1:  # top V hit only
                    current.v_call = parts[2]
                    pct = safe_float(parts[3])
                    if pct is not None:
                        current.v_identity = pct / 100.0
                    current.v_alignment_length = current.v_alignment_length or safe_int(parts[4])
                    current.v_sequence_start = safe_int(parts[8])
                    current.v_sequence_end = safe_int(parts[9])
                    current.v_germline_start = safe_int(parts[10])
                    current.v_germline_end = safe_int(parts[11])
                    if len(parts) > 14:
                        current.query_alignment = parts[14]
                    if len(parts) > 15:
                        current.germline_alignment = parts[15]

    # Save last query
    if current is not None:
        results[current.query_id] = current

    return results


# ---------------------------------------------------------------------------
# V-gene identity and coverage extraction
# ---------------------------------------------------------------------------

def _germline_v_length(row: Dict[str, str]) -> Optional[int]:
    aln_g = _first_valid(row, ("v_germline_alignment", "germline_alignment"))
    if not aln_g:
        return None
    return sum(1 for c in aln_g if c not in ("-", "."))


def _extract_v_identity_and_cov(
    row: Dict[str, str],
    seq_len: int,
) -> Tuple[Optional[float], Optional[float]]:
    v_id: Optional[float] = None
    for k in ("v_identity",):
        if k in row:
            x = safe_float(row[k])
            if x is not None:
                v_id = x / 100.0 if x > 1.0 else x
                break
    if v_id is None:
        aln_q = _first_valid(row, ("v_sequence_alignment",))
        aln_g = _first_valid(row, ("v_germline_alignment",))
        v_id = compute_pairwise_identity(aln_q, aln_g)

    v_start = safe_int(_first_valid(row, ("v_sequence_start",)) or "")
    v_end   = safe_int(_first_valid(row, ("v_sequence_end",))   or "")
    germline_len = _germline_v_length(row) or _EXPECTED_V_REGION_LEN

    v_cov: Optional[float] = None
    if v_start is not None and v_end is not None and v_end >= v_start:
        aligned_len = v_end - v_start + 1
        v_cov = aligned_len / germline_len
    else:
        aln_len = safe_int(_first_valid(row, ("v_alignment_length",)) or "")
        if aln_len is not None and germline_len > 0:
            v_cov = aln_len / germline_len

    return v_id, v_cov


# ---------------------------------------------------------------------------
# CDR3 extraction (anchor-based, since igblastp has no J alignment)
# ---------------------------------------------------------------------------

_FR4_MOTIF = re.compile(r"[WF]G.G")
_FR4_MOTIF_LOOSE = re.compile(r"[WF]G[QRKTAS]")


def _extract_cdr3(row: Dict[str, str], seq: str = "") -> Tuple[Optional[str], Optional[int], Dict[str, Any]]:
    """
    Extract CDR3 using anchor-based scanning on the raw sequence。
    igblastp never populates CDR3 fields, so we go straight to anchors.
    """
    feats: Dict[str, Any] = {}

    if not seq:
        feats["cdr3_source"] = "none"
        return None, None, feats

    cdr3, cdr3_len, anchor_feats = _extract_cdr3_by_anchors(seq.strip().upper(), row)
    feats.update(anchor_feats)
    return cdr3, cdr3_len, feats


def _extract_cdr3_by_anchors(
    seq: str,
    row: Dict[str, str],
) -> Tuple[Optional[str], Optional[int], Dict[str, Any]]:
    """
    Extract CDR3 from raw AA sequence using conserved anchor residues.
    CDR3 = residues between Cys104 (exclusive) and FR4 Trp/Phe (exclusive).
    """
    feats: Dict[str, Any] = {}

    cys_pos = _find_cys104(seq, row)
    feats["cys104_pos"] = cys_pos

    if cys_pos is None:
        feats["cdr3_source"] = "no_cys104"
        return None, None, feats

    search_start = cys_pos + 1
    search_region = seq[search_start:]

    fr4_offset = _find_fr4_motif(search_region)
    if fr4_offset is not None:
        fr4_pos = search_start + fr4_offset
        feats["fr4_pos"] = fr4_pos
        feats["fr4_motif"] = seq[fr4_pos:fr4_pos + 4]
    else:
        feats["cdr3_source"] = "no_fr4_motif"
        feats["fr4_pos"] = None
        return None, None, feats

    cdr3_seq = seq[cys_pos + 1 : fr4_pos]
    cdr3_len = len(cdr3_seq)

    feats["cdr3_source"] = "anchors"
    return cdr3_seq, cdr3_len, feats


def _find_cys104(seq: str, row: Dict[str, str]) -> Optional[int]:
    """
    Find the conserved Cys at IMGT position 104 (end of FR3).
    Prefers FR3 end from igblastp alignment summary, then scans。
    """
    seq_len = len(seq)

    fr3_end = safe_int(_first_valid(row, ("fwr3_end", "fr3_end")) or "")
    if fr3_end is not None:
        idx = fr3_end - 1  # 1-based → 0-based
        if 0 <= idx < seq_len and seq[idx] == "C":
            return idx
        for offset in (-1, 1, -2, 2):
            adj = idx + offset
            if 0 <= adj < seq_len and seq[adj] == "C":
                return adj

    # Fallback: scan expected window
    window_start = max(0, int(seq_len * 0.65))
    window_end   = min(seq_len, int(seq_len * 0.88))

    for i in range(window_end - 1, window_start - 1, -1):
        if seq[i] == "C":
            return i

    return None


def _find_fr4_motif(region: str) -> Optional[int]:
    """Find FR4 anchor motif ([WF]GxG) downstream of Cys104."""
    max_search = min(len(region), 45)
    search_str = region[:max_search]

    m = _FR4_MOTIF.search(search_str)
    if m:
        return m.start()

    m = _FR4_MOTIF_LOOSE.search(search_str)
    if m:
        return m.start()

    return None


# ---------------------------------------------------------------------------
# VHH FR2 hallmark scoring (component D)
# ---------------------------------------------------------------------------

def _score_vhh_hallmarks(row: Dict[str, str]) -> Tuple[float, Dict[str, Any]]:
    fr2 = _first_valid(row, ("fwr2_aa", "fr2_aa", "fwr2"))
    feats: Dict[str, Any] = {}
    if not fr2 or len(fr2) < 14:
        return 0.5, {"fr2_available": False, "fr2_seq": fr2 or None}
    hallmark_hits = 0.0
    n_checked = 0
    for imgt_pos, (idx, vhh_aas, vh_aas) in VHH_HALLMARKS.items():
        if idx >= len(fr2):
            continue
        res = fr2[idx]
        n_checked += 1
        feats[f"fr2_pos{imgt_pos}"] = res
        if res in vhh_aas:
            hallmark_hits += 1.0
        elif res in vh_aas:
            hallmark_hits += 0.0
        else:
            hallmark_hits += 0.25
    if n_checked == 0:
        return 0.5, {**feats, "fr2_available": False}
    score = hallmark_hits / n_checked
    feats.update({
        "fr2_available": True,
        "fr2_hallmark_hits": hallmark_hits,
        "fr2_positions_checked": n_checked,
    })
    return score, feats


# ---------------------------------------------------------------------------
# Position-specific FR/CDR mutation scoring (component B)
# ---------------------------------------------------------------------------

def _region_boundaries_from_row(row: Dict[str, str]) -> Dict[int, str]:
    """Build a map of sequence position (0-based) -> region type (fr/cdr)."""
    pos_type: Dict[int, str] = {}
    _region_defs = [
        ("fwr1", "fr"),
        ("cdr1", "cdr"),
        ("fwr2", "fr"),
        ("cdr2", "cdr"),
        ("fwr3", "fr"),
    ]
    for prefix, label in _region_defs:
        start = safe_int(_first_valid(row, (f"{prefix}_start",)) or "")
        end   = safe_int(_first_valid(row, (f"{prefix}_end",))   or "")
        if start is not None and end is not None:
            for p in range(start - 1, end):  # 1-based → 0-based
                pos_type[p] = label
    return pos_type


def _position_specific_score(
    row: Dict[str, str],
    seq: str,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Score position-specific FR vs CDR mutations from V alignment."""
    aln_q = _first_valid(row, ("v_sequence_alignment",))
    aln_g = _first_valid(row, ("v_germline_alignment",))
    if not aln_q or not aln_g or len(aln_q) != len(aln_g):
        return None, {"position_specific_available": False}

    pos_type = _region_boundaries_from_row(row)
    if not pos_type:
        return None, {"position_specific_available": False}

    fr_match = fr_total = 0
    cdr_match = cdr_total = 0
    seq_pos = -1
    for q_ch, g_ch in zip(aln_q, aln_g):
        if q_ch != "-":
            seq_pos += 1
        if q_ch == "-" or g_ch == "-":
            continue
        region = pos_type.get(seq_pos)
        if region == "fr":
            fr_total += 1
            if q_ch == g_ch:
                fr_match += 1
        elif region == "cdr":
            cdr_total += 1
            if q_ch == g_ch:
                cdr_match += 1

    fr_identity  = fr_match  / fr_total  if fr_total  > 0 else None
    cdr_identity = cdr_match / cdr_total if cdr_total > 0 else None

    fr_score = clamp((fr_identity - 0.80) / (1.0 - 0.80), 0.0, 1.0) if fr_identity is not None else 0.5
    if cdr_identity is not None:
        cdr_score = 1.0 - clamp(abs(cdr_identity - 0.55) / 0.45, 0.0, 1.0) * 0.35
    else:
        cdr_score = 0.5
    score = 0.80 * fr_score + 0.20 * cdr_score

    feats: Dict[str, Any] = {
        "position_specific_available": True,
        "fr_identity": fr_identity,
        "cdr_identity": cdr_identity,
        "fr_positions": fr_total,
        "cdr_positions": cdr_total,
        "B_fr_score": fr_score,
        "B_cdr_score": cdr_score,
    }
    return score, feats


# ---------------------------------------------------------------------------
# Composite nativeness scoring
# ---------------------------------------------------------------------------

@dataclass
class ScoreResult:
    sequence_id: str
    vhh_nativeness: float
    human_framework: Optional[float]
    final_score: float
    hard_reject: bool
    reject_reason: Optional[str]
    features: Dict[str, Any]


def vhh_nativeness_score(
    row: Dict[str, str],
    seq: str,
    *,
    hard_reject_thresholds: Dict[str, float] | None = None,
) -> Tuple[bool, Optional[str], float, Dict[str, Any]]:
    """
    Compute VHH nativeness composite score from a parsed igblastp result row.
    Returns (hard_reject, reject_reason, score, features).
    """
    seq = seq.strip().upper()
    seq_len = len(seq)
    thr = {
        "min_v_identity": 0.70,
        "min_v_coverage": 0.80,
        "min_cdr3_len": 6,
        "max_cdr3_len": 35,
    }
    if hard_reject_thresholds:
        thr.update(hard_reject_thresholds)

    v_id, v_cov = _extract_v_identity_and_cov(row, seq_len)
    cdr3, cdr3_len, cdr3_feats = _extract_cdr3(row, seq)
    v_call = _first_valid(row, ("v_call",))

    base_feats: Dict[str, Any] = {
        "v_call": v_call or None,
        "v_identity": v_id,
        "v_coverage": v_cov,
        **cdr3_feats,
    }

    if not v_call:
        return True, "no_v_call", 0.0, base_feats
    if v_cov is None or v_cov < thr["min_v_coverage"]:
        return True, "low_v_coverage", 0.0, base_feats
    if v_id is None or v_id < thr["min_v_identity"]:
        return True, "low_v_identity", 0.0, base_feats
    if cdr3_len is None:
        source = cdr3_feats.get("cdr3_source", "missing_cdr3")
        if source == "no_cys104":
            return True, "missing_cdr3_no_cys104", 0.0, base_feats
        elif source == "no_fr4_motif":
            return True, "missing_cdr3_no_fr4_motif", 0.0, base_feats
        else:
            return True, "missing_cdr3", 0.0, base_feats
    if cdr3_len < int(thr["min_cdr3_len"]) or cdr3_len > int(thr["max_cdr3_len"]):
        return True, "cdr3_length_out_of_range", 0.0, {**base_feats, "cdr3_len": cdr3_len, "cdr3": cdr3}

    # Component A: germline fit
    v_id_s = clamp((v_id - 0.70) / (0.95 - 0.70), 0.0, 1.0)
    v_cov_s = clamp((v_cov - 0.80) / (1.00 - 0.80), 0.0, 1.0)
    A = 0.70 * v_id_s + 0.30 * v_cov_s

    # Component B: position-specific mutations
    B_score, B_feats = _position_specific_score(row, seq)
    if B_score is None:
        B = clamp((v_id - 0.75) / (0.95 - 0.75), 0.0, 1.0)
        B_feats["position_specific_available"] = False
        B_feats["B_fallback"] = True
    else:
        B = B_score
        B_feats["B_fallback"] = False

    # Component C: CDR3 plausibility
    C = math.exp(-((cdr3_len - 18) / 8.0) ** 2)

    # Component D: VHH hallmarks
    D, D_feats = _score_vhh_hallmarks(row)

    vhh_nativeness = clamp(
        0.25 * A + 0.30 * B + 0.20 * C + 0.25 * D,
        0.0, 1.0,
    )

    feats: Dict[str, Any] = {
        **base_feats,
        "cdr3_len": cdr3_len,
        "cdr3": cdr3,
        "A_germline_fit": round(A, 4),
        "B_position_specific": round(B, 4),
        "C_cdr3_plausibility": round(C, 4),
        "D_vhh_hallmarks": round(D, 4),
        "vhh_nativeness": round(vhh_nativeness, 4),
        **B_feats,
        **D_feats,
    }
    return False, None, vhh_nativeness, feats


def human_framework_score(
    row: Dict[str, str],
    seq: str,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Score human framework similarity for humanization readiness."""
    seq = seq.strip().upper()
    seq_len = len(seq)
    v_id, v_cov = _extract_v_identity_and_cov(row, seq_len)
    v_call = _first_valid(row, ("v_call",))
    if v_id is None or v_cov is None or not v_call:
        return None, {"human_v_call": v_call or None, "human_v_identity": v_id, "human_v_coverage": v_cov}
    h_id_s  = clamp((v_id  - 0.60) / (0.90 - 0.60), 0.0, 1.0)
    h_cov_s = clamp((v_cov - 0.80) / (1.00 - 0.80), 0.0, 1.0)
    human_sc = clamp(0.8 * h_id_s + 0.2 * h_cov_s, 0.0, 1.0)
    feats: Dict[str, Any] = {
        "human_v_call": v_call,
        "human_v_identity": v_id,
        "human_v_coverage": v_cov,
        "human_framework_score": round(human_sc, 4),
    }
    return human_sc, feats


# ---------------------------------------------------------------------------
# Main pipeline: FASTA → igblastp → parse → score
# ---------------------------------------------------------------------------

def score_fasta(
    fasta_in: str,
    cfg: IgBlastConfig,
    *,
    human_weight: float = 0.15,
    base_weight: float = 0.85,
) -> List[ScoreResult]:
    items = read_fasta(fasta_in)
    seq_by_id = {sid: seq for sid, seq in items}

    with tempfile.TemporaryDirectory() as td:
        td = str(td)

        camelid_out = os.path.join(td, "camelid_fmt7.txt")
        run_igblastp(fasta_in, camelid_out, cfg, use_human=False)
        camelid_parsed = parse_igblastp_fmt7(camelid_out)

        human_parsed: Dict[str, IgBlastQueryResult] = {}
        if cfg.human_db_v:
            human_out = os.path.join(td, "human_fmt7.txt")
            run_igblastp(fasta_in, human_out, cfg, use_human=True)
            human_parsed = parse_igblastp_fmt7(human_out)

    results: List[ScoreResult] = []
    for sid, seq in seq_by_id.items():
        cres = camelid_parsed.get(sid)
        if cres is None:
            results.append(ScoreResult(
                sequence_id=sid,
                vhh_nativeness=0.0,
                human_framework=None,
                final_score=0.0,
                hard_reject=True,
                reject_reason="missing_igblast_row",
                features={"sequence_len": len(seq)},
            ))
            continue

        row = cres.to_row_dict(seq)
        hard_reject, reason, vhh_score, feats = vhh_nativeness_score(row, seq)

        human_score = None
        if human_parsed:
            hres = human_parsed.get(sid)
            if hres is not None:
                hrow = hres.to_row_dict(seq)
                human_score, hfeats = human_framework_score(hrow, seq)
                feats.update(hfeats)

        if hard_reject:
            final = 0.0
        elif human_score is None:
            final = vhh_score
        else:
            final = clamp(
                base_weight * vhh_score + human_weight * vhh_score * human_score,
                0.0, 1.0,
            )

        results.append(ScoreResult(
            sequence_id=sid,
            vhh_nativeness=vhh_score,
            human_framework=human_score,
            final_score=final,
            hard_reject=hard_reject,
            reject_reason=reason,
            features=feats,
        ))
    return results


def run(
    fasta_path: str,
    camelid_db_v: str = CAMELID_DB_V,
    human_db_v: str = HUMAN_DB_V,
) -> List[Dict[str, Any]]:
    """
    Public entrypoint used by MetaNano code.
    MetaNano 代码使用的公共入口。
    """
    cfg = IgBlastConfig(
        igblastp_path=os.path.join(IGBLAST_DIR, "bin", "igblastp"),
        num_threads=1,
        camelid_db_v=camelid_db_v,
        human_db_v=human_db_v,
    )
    results = score_fasta(fasta_path, cfg)
    out: List[Dict[str, Any]] = []
    for r in results:
        out.append({
            "sequence_id": r.sequence_id,
            "hard_reject": r.hard_reject,
            "reject_reason": r.reject_reason,
            "vhh_nativeness": r.vhh_nativeness,
            "human_framework": r.human_framework,
            "final_score": r.final_score,
            "features": r.features,
        })
    return out

