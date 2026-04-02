#!/usr/bin/env python3
"""
VHH nativeness scoring via igblastp + abnumber.
通过 igblastp + abnumber 进行 VHH 天然性评分。

Refactored to delegate CDR extraction, FR/CDR boundary classification,
and IMGT-position lookups to `abnumber`, while retaining IgBLAST for
germline V-gene identity, coverage, and V-call assignment.

重构后将 CDR 提取、FR/CDR 边界分类和 IMGT 位点查找委托给 abnumber，
同时保留 IgBLAST 用于种系 V 基因同一性、覆盖度和 V-call 分配。
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from abnumber import Chain

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
PARENT_DIR = os.path.dirname(PROJECT_ROOT)

if PARENT_DIR.endswith("nova"):
    IGBLAST_DIR = os.path.join(PARENT_DIR, "external_tools", "igblast")
else:
    IGBLAST_DIR = os.path.join(PARENT_DIR, "igblast")

os.environ.setdefault("IGDATA", IGBLAST_DIR)

CAMELID_DB_V = os.path.join(IGBLAST_DIR, "database", "camelid_V")
HUMAN_DB_V = os.path.join(IGBLAST_DIR, "database", "human_V")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


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


def _first_valid(row: Dict[str, str], keys) -> str:
    for k in keys:
        v = (row.get(k) or "").strip()
        if v and v != "NA":
            return v
    return ""


def read_fasta(path: str) -> List[Tuple[str, str]]:
    """Minimal FASTA reader."""
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
# abnumber wrapper
# ---------------------------------------------------------------------------

@dataclass
class NumberedSequence:
    """Holds an abnumber Chain plus pre-extracted CDR/FR info."""

    chain: Chain
    cdr1: str
    cdr2: str
    cdr3: str
    # FR sequences keyed by region name
    frameworks: Dict[str, str]  # {"fr1": ..., "fr2": ..., "fr3": ..., "fr4": ...}

    @staticmethod
    def from_sequence(seq: str) -> Optional["NumberedSequence"]:
        """
        Try to number a sequence with abnumber (IMGT, heavy chain).
        Returns None if numbering fails.
        """
        try:
            chain = Chain(seq, scheme="imgt")
        except Exception:
            return None

        cdr1 = str(chain.cdr1_seq) if chain.cdr1_seq else ""
        cdr2 = str(chain.cdr2_seq) if chain.cdr2_seq else ""
        cdr3 = str(chain.cdr3_seq) if chain.cdr3_seq else ""

        frameworks: Dict[str, str] = {}
        for key, prop in [("fr1", chain.fr1_seq), ("fr2", chain.fr2_seq),
                          ("fr3", chain.fr3_seq), ("fr4", chain.fr4_seq)]:
            frameworks[key] = str(prop) if prop else ""

        return NumberedSequence(
            chain=chain,
            cdr1=cdr1,
            cdr2=cdr2,
            cdr3=cdr3,
            frameworks=frameworks,
        )


# ---------------------------------------------------------------------------
# IgBLAST runner (unchanged — still needed for germline identity/coverage)
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
            f"igblastp failed.\ncmd: {' '.join(cmd)}\n"
            f"stdout:\n{p.stdout}\nstderr:\n{p.stderr}\n"
        )


# ---------------------------------------------------------------------------
# igblastp fmt7 parser (slimmed down — only extracts germline hit info)
# ---------------------------------------------------------------------------

_TOTAL_LINE_RE = re.compile(
    r"Total\s+N/A\s+N/A"
    r"\s+(\d+)"
    r"\s+(\d+)\s+(\d+)\s+(\d+)"
    r"\s+([\d.]+)",
)


@dataclass
class IgBlastHit:
    """Parsed top-V-hit info for one query. CDR/FR extraction is handled by abnumber."""

    query_id: str
    v_call: Optional[str] = None
    v_identity: Optional[float] = None       # 0–1
    v_alignment_length: Optional[int] = None
    v_sequence_start: Optional[int] = None   # 1-based
    v_sequence_end: Optional[int] = None
    v_germline_start: Optional[int] = None
    v_germline_end: Optional[int] = None
    query_alignment: Optional[str] = None
    germline_alignment: Optional[str] = None
    total_identity: Optional[float] = None


def parse_igblastp_fmt7(output_path: str) -> Dict[str, IgBlastHit]:
    """Parse igblastp fmt7 output — only keeps germline-alignment fields."""
    results: Dict[str, IgBlastHit] = {}
    current: Optional[IgBlastHit] = None
    in_alignment_summary = False
    hit_count = 0

    with open(output_path) as f:
        for line in f:
            line = line.rstrip("\n\r")

            if line.startswith("# Query: "):
                if current is not None:
                    results[current.query_id] = current
                qid = line[len("# Query: "):].strip()
                current = IgBlastHit(query_id=qid)
                in_alignment_summary = False
                hit_count = 0
                continue

            if current is None:
                continue

            if line.startswith("# Alignment summary"):
                in_alignment_summary = True
                continue

            if line.startswith("# Hit table"):
                in_alignment_summary = False
                continue

            if line.startswith("#"):
                continue

            # Alignment summary — only need the Total line for alignment length
            if in_alignment_summary:
                m = _TOTAL_LINE_RE.match(line.strip())
                if m:
                    current.v_alignment_length = int(m.group(1))
                    current.total_identity = float(m.group(5)) / 100.0
                continue

            # Hit table data line
            parts = line.split("\t")
            if len(parts) >= 15 and parts[0] == "V":
                hit_count += 1
                if hit_count == 1:
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

    if current is not None:
        results[current.query_id] = current

    return results


# ---------------------------------------------------------------------------
# V-gene identity and coverage (from IgBLAST hit)
# ---------------------------------------------------------------------------

_EXPECTED_V_REGION_LEN = 100


def _extract_v_identity_and_cov(
    hit: IgBlastHit,
    seq_len: int,
) -> Tuple[Optional[float], Optional[float]]:
    v_id = hit.v_identity

    # Fallback: compute from alignment strings
    if v_id is None and hit.query_alignment and hit.germline_alignment:
        aln_q, aln_g = hit.query_alignment, hit.germline_alignment
        if len(aln_q) == len(aln_g):
            match = sum(1 for a, b in zip(aln_q, aln_g) if a != "-" and b != "-" and a == b)
            denom = sum(1 for a, b in zip(aln_q, aln_g) if a != "-" and b != "-")
            if denom > 0:
                v_id = match / denom

    # Coverage
    germline_len: int = _EXPECTED_V_REGION_LEN
    if hit.germline_alignment:
        gl = sum(1 for c in hit.germline_alignment if c not in ("-", "."))
        if gl > 0:
            germline_len = gl

    v_cov: Optional[float] = None
    if hit.v_sequence_start is not None and hit.v_sequence_end is not None:
        aligned_len = hit.v_sequence_end - hit.v_sequence_start + 1
        v_cov = aligned_len / germline_len
    elif hit.v_alignment_length is not None and germline_len > 0:
        v_cov = hit.v_alignment_length / germline_len

    return v_id, v_cov


# ---------------------------------------------------------------------------
# VHH FR2 hallmark scoring (component D) — index into FR2 string directly
# ---------------------------------------------------------------------------

_FR2_IMGT_START = 39

VHH_HALLMARKS: Dict[int, Tuple[int, frozenset, frozenset]] = {
    42: (42 - _FR2_IMGT_START, frozenset("FY"),   frozenset("VLI")),
    49: (49 - _FR2_IMGT_START, frozenset("EQ"),   frozenset("GA")),
    50: (50 - _FR2_IMGT_START, frozenset("RCWF"), frozenset("LIV")),
    52: (52 - _FR2_IMGT_START, frozenset("GFLS"), frozenset("W")),
}


def _score_vhh_hallmarks(numbered: NumberedSequence) -> Tuple[float, Dict[str, Any]]:
    fr2 = numbered.frameworks.get("fr2", "")
    feats: Dict[str, Any] = {}

    if not fr2 or len(fr2) < 14:
        return 0.5, {"fr2_available": False, "fr2_seq": fr2 or None}

    hits = 0.0
    checked = 0

    for imgt_pos, (idx, vhh_aas, vh_aas) in VHH_HALLMARKS.items():
        if idx >= len(fr2):
            continue
        res = fr2[idx]
        checked += 1
        feats[f"fr2_pos{imgt_pos}"] = res
        if res in vhh_aas:
            hits += 1.0
        elif res not in vh_aas:
            hits += 0.25

    if checked == 0:
        return 0.5, {**feats, "fr2_available": False}

    score = hits / checked
    feats.update({
        "fr2_available": True,
        "fr2_hallmark_hits": hits,
        "fr2_positions_checked": checked,
    })
    return score, feats


# ---------------------------------------------------------------------------
# Position-specific FR/CDR mutation scoring (component B)
# Now uses abnumber region classification instead of manual boundary maps.
# ---------------------------------------------------------------------------

def _position_specific_score(
    hit: IgBlastHit,
    numbered: NumberedSequence,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Score FR vs CDR mutation patterns from the IgBLAST alignment."""
    aln_q = hit.query_alignment
    aln_g = hit.germline_alignment
    if not aln_q or not aln_g or len(aln_q) != len(aln_g):
        return None, {"position_specific_available": False}

    # Build a set of 0-based sequence positions that fall in FR vs CDR regions.
    # Use explicit per-region properties instead of chain.regions iterator.
    fr_positions: set[int] = set()
    cdr_positions: set[int] = set()
    seq_offset = 0
    region_order = [
        ("fr",  numbered.frameworks.get("fr1", "")),
        ("cdr", numbered.cdr1),
        ("fr",  numbered.frameworks.get("fr2", "")),
        ("cdr", numbered.cdr2),
        ("fr",  numbered.frameworks.get("fr3", "")),
        ("cdr", numbered.cdr3),
        ("fr",  numbered.frameworks.get("fr4", "")),
    ]
    for region_type, region_seq in region_order:
        if not region_seq:
            continue
        for _ in region_seq:
            if region_type == "fr":
                fr_positions.add(seq_offset)
            else:
                cdr_positions.add(seq_offset)
            seq_offset += 1

    fr_match = fr_total = 0
    cdr_match = cdr_total = 0
    seq_pos = -1
    for q_ch, g_ch in zip(aln_q, aln_g):
        if q_ch != "-":
            seq_pos += 1
        if q_ch == "-" or g_ch == "-":
            continue
        if seq_pos in fr_positions:
            fr_total += 1
            if q_ch == g_ch:
                fr_match += 1
        elif seq_pos in cdr_positions:
            cdr_total += 1
            if q_ch == g_ch:
                cdr_match += 1

    fr_identity = fr_match / fr_total if fr_total > 0 else None
    cdr_identity = cdr_match / cdr_total if cdr_total > 0 else None

    fr_score = clamp((fr_identity - 0.80) / (1.0 - 0.80), 0.0, 1.0) if fr_identity is not None else 0.5
    if cdr_identity is not None:
        cdr_score = 1.0 - clamp(abs(cdr_identity - 0.55) / 0.45, 0.0, 1.0) * 0.35
    else:
        cdr_score = 0.5
    score = 0.80 * fr_score + 0.20 * cdr_score

    return score, {
        "position_specific_available": True,
        "fr_identity": fr_identity,
        "cdr_identity": cdr_identity,
        "fr_positions": fr_total,
        "cdr_positions": cdr_total,
        "B_fr_score": fr_score,
        "B_cdr_score": cdr_score,
    }


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
    hit: IgBlastHit,
    numbered: NumberedSequence,
    seq: str,
    *,
    hard_reject_thresholds: Dict[str, float] | None = None,
) -> Tuple[bool, Optional[str], float, Dict[str, Any]]:
    """
    Compute VHH nativeness composite score.
    Takes an IgBlastHit (for germline info) and a NumberedSequence (for CDR/FR info).
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

    v_id, v_cov = _extract_v_identity_and_cov(hit, seq_len)

    cdr3 = numbered.cdr3
    cdr3_len = len(cdr3) if cdr3 else None

    base_feats: Dict[str, Any] = {
        "v_call": hit.v_call,
        "v_identity": v_id,
        "v_coverage": v_cov,
        "cdr1": numbered.cdr1 or None,
        "cdr2": numbered.cdr2 or None,
        "cdr3": cdr3 or None,
        "cdr1_len": len(numbered.cdr1) if numbered.cdr1 else None,
        "cdr2_len": len(numbered.cdr2) if numbered.cdr2 else None,
        "cdr3_len": cdr3_len,
    }

    # --- Hard rejection gates ---
    if not hit.v_call:
        return True, "no_v_call", 0.0, base_feats
    if v_cov is None or v_cov < thr["min_v_coverage"]:
        return True, "low_v_coverage", 0.0, base_feats
    if v_id is None or v_id < thr["min_v_identity"]:
        return True, "low_v_identity", 0.0, base_feats
    if not cdr3 or cdr3_len is None:
        return True, "missing_cdr3", 0.0, base_feats
    if cdr3_len < int(thr["min_cdr3_len"]) or cdr3_len > int(thr["max_cdr3_len"]):
        return True, "cdr3_length_out_of_range", 0.0, base_feats

    # --- Component A: germline fit ---
    v_id_s = clamp((v_id - 0.70) / (0.95 - 0.70), 0.0, 1.0)
    v_cov_s = clamp((v_cov - 0.80) / (1.00 - 0.80), 0.0, 1.0)
    A = 0.70 * v_id_s + 0.30 * v_cov_s

    # --- Component B: position-specific mutations ---
    B_score, B_feats = _position_specific_score(hit, numbered)
    if B_score is None:
        B = clamp((v_id - 0.75) / (0.95 - 0.75), 0.0, 1.0)
        B_feats["B_fallback"] = True
    else:
        B = B_score
        B_feats["B_fallback"] = False

    # --- Component C: CDR3 plausibility ---
    C = math.exp(-((cdr3_len - 18) / 8.0) ** 2)

    # --- Component D: VHH hallmarks ---
    D, D_feats = _score_vhh_hallmarks(numbered)

    vhh_nativeness = clamp(
        0.25 * A + 0.30 * B + 0.20 * C + 0.25 * D,
        0.0, 1.0,
    )

    feats: Dict[str, Any] = {
        **base_feats,
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
    hit: IgBlastHit,
    seq: str,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Score human framework similarity for humanization readiness."""
    seq_len = len(seq.strip())
    v_id, v_cov = _extract_v_identity_and_cov(hit, seq_len)
    if v_id is None or v_cov is None or not hit.v_call:
        return None, {
            "human_v_call": hit.v_call,
            "human_v_identity": v_id,
            "human_v_coverage": v_cov,
        }
    h_id_s = clamp((v_id - 0.60) / (0.90 - 0.60), 0.0, 1.0)
    h_cov_s = clamp((v_cov - 0.80) / (1.00 - 0.80), 0.0, 1.0)
    human_sc = clamp(0.8 * h_id_s + 0.2 * h_cov_s, 0.0, 1.0)
    return human_sc, {
        "human_v_call": hit.v_call,
        "human_v_identity": v_id,
        "human_v_coverage": v_cov,
        "human_framework_score": round(human_sc, 4),
    }


# ---------------------------------------------------------------------------
# Temp FASTA helpers
# ---------------------------------------------------------------------------

def _write_temp_fasta(
    sequences: Dict[str, str],
    directory: str,
) -> str:
    """Write sequences to a temp FASTA file. Returns the file path."""
    path = os.path.join(directory, "input.fasta")
    with open(path, "w", encoding="utf-8") as f:
        for sid, seq in sequences.items():
            f.write(f">{sid}\n{seq}\n")
    return path


# ---------------------------------------------------------------------------
# Core pipeline: sequences dict → igblastp → abnumber → score
# ---------------------------------------------------------------------------

def _score_with_fasta(
    fasta_path: str,
    seq_by_id: Dict[str, str],
    cfg: IgBlastConfig,
    *,
    human_weight: float = 0.15,
    base_weight: float = 0.85,
) -> List[ScoreResult]:
    """
    Internal pipeline that runs IgBLAST on an already-written FASTA file.
    All temp IgBLAST outputs are cleaned up automatically.
    """
    with tempfile.TemporaryDirectory() as td:
        camelid_out = os.path.join(td, "camelid_fmt7.txt")
        run_igblastp(fasta_path, camelid_out, cfg, use_human=False)
        camelid_parsed = parse_igblastp_fmt7(camelid_out)

        human_parsed: Dict[str, IgBlastHit] = {}
        if cfg.human_db_v:
            human_out = os.path.join(td, "human_fmt7.txt")
            run_igblastp(fasta_path, human_out, cfg, use_human=True)
            human_parsed = parse_igblastp_fmt7(human_out)

    results: List[ScoreResult] = []
    for sid, seq in seq_by_id.items():
        chit = camelid_parsed.get(sid)
        if chit is None:
            results.append(ScoreResult(
                sequence_id=sid, vhh_nativeness=0.0,
                human_framework=None, final_score=0.0,
                hard_reject=True, reject_reason="missing_igblast_row",
                features={"sequence_len": len(seq)},
            ))
            continue

        numbered = NumberedSequence.from_sequence(seq)
        if numbered is None:
            results.append(ScoreResult(
                sequence_id=sid, vhh_nativeness=0.0,
                human_framework=None, final_score=0.0,
                hard_reject=True, reject_reason="abnumber_failed",
                features={"sequence_len": len(seq), "v_call": chit.v_call},
            ))
            continue

        hard_reject, reason, vhh_score, feats = vhh_nativeness_score(chit, numbered, seq)

        human_score = None
        if human_parsed:
            hhit = human_parsed.get(sid)
            if hhit is not None:
                human_score, hfeats = human_framework_score(hhit, seq)
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
            sequence_id=sid, vhh_nativeness=vhh_score,
            human_framework=human_score, final_score=final,
            hard_reject=hard_reject, reject_reason=reason,
            features=feats,
        ))
    return results


def score_fasta(
    fasta_in: str,
    cfg: IgBlastConfig,
    *,
    human_weight: float = 0.15,
    base_weight: float = 0.85,
) -> List[ScoreResult]:
    """Score from an existing FASTA file on disk."""
    items = read_fasta(fasta_in)
    seq_by_id = {sid: seq for sid, seq in items}
    return _score_with_fasta(
        fasta_in, seq_by_id, cfg,
        human_weight=human_weight, base_weight=base_weight,
    )


def score_sequences(
    sequences: Dict[str, str] | List[Tuple[str, str]] | str,
    cfg: IgBlastConfig | None = None,
    *,
    human_weight: float = 0.15,
    base_weight: float = 0.85,
) -> List[ScoreResult]:
    """
    Score in-memory sequences. Handles all temp file creation/cleanup.
    从内存中的序列进行评分。处理所有临时文件的创建和清理。

    Args:
        sequences: One of:
            - Dict[str, str]: {sequence_id: sequence}
            - List[Tuple[str, str]]: [(sequence_id, sequence), ...]
            - str: a single bare sequence (gets id "seq_0")
        cfg: IgBlastConfig (uses defaults if None).

    Returns:
        List[ScoreResult]

    Example:
        >>> results = score_sequences({"nb1": "EVQLVES...", "nb2": "QVQLQES..."})
        >>> results = score_sequences("EVQLVESGGGLVQPGG...")  # single sequence
    """
    # Normalize input to Dict[str, str]
    if isinstance(sequences, str):
        seq_by_id = {"seq_0": sequences.strip().upper()}
    elif isinstance(sequences, list):
        seq_by_id = {sid: seq for sid, seq in sequences}
    else:
        seq_by_id = sequences

    if cfg is None:
        cfg = IgBlastConfig()

    with tempfile.TemporaryDirectory() as td:
        fasta_path = _write_temp_fasta(seq_by_id, td)
        return _score_with_fasta(
            fasta_path, seq_by_id, cfg,
            human_weight=human_weight, base_weight=base_weight,
        )


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------

def _results_to_dicts(results: List[ScoreResult]) -> List[Dict[str, Any]]:
    return [
        {
            "sequence_id": r.sequence_id,
            "hard_reject": r.hard_reject,
            "reject_reason": r.reject_reason,
            "vhh_nativeness": r.vhh_nativeness,
            "human_framework": r.human_framework,
            "final_score": r.final_score,
            "features": r.features,
        }
        for r in results
    ]


def run(
    sequences: str | Dict[str, str] | List[Tuple[str, str]],
    camelid_db_v: str = CAMELID_DB_V,
    human_db_v: str = HUMAN_DB_V,
) -> List[Dict[str, Any]]:
    """
    Public entrypoint used by MetaNano code.
    MetaNano 代码使用的公共入口。

    Accepts either a FASTA file path or in-memory sequences:
        run("path/to/seqs.fasta")
        run({"nb1": "EVQLVES...", "nb2": "QVQLQES..."})
        run("EVQLVESGGGLVQPGG...")   # single sequence
        run([("nb1", "EVQLVES..."), ("nb2", "QVQLQES...")])
    """
    cfg = IgBlastConfig(
        igblastp_path=os.path.join(IGBLAST_DIR, "bin", "igblastp"),
        num_threads=1,
        camelid_db_v=camelid_db_v,
        human_db_v=human_db_v,
    )

    # If it's a string that looks like a file path, use score_fasta
    if isinstance(sequences, str) and os.path.isfile(sequences):
        return _results_to_dicts(score_fasta(sequences, cfg))

    # Otherwise treat as in-memory sequences
    return _results_to_dicts(score_sequences(sequences, cfg))


def features_to_cdrs(features: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Build CDR dict for IndexManager.add_sequence from run() features.
    Returns None when all three CDRs are missing.
    """
    cdrs = {
        k: (features.get(k) if isinstance(features.get(k), str) else "") or ""
        for k in ("cdr1", "cdr2", "cdr3")
    }
    if not any(cdrs.values()):
        return None
    return cdrs
    