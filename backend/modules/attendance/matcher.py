"""
Auto-Correction & Data Matching Engine for KTM Attendance.
Implements FR-03:
- Priority Path: Regex cleansing & NIM verification.
- Fallback Path: Fuzzy matching (RapidFuzz) on Student Name (Threshold >= 75%).
- Attribute Alignment: Completes official NIM & Name from reference database.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from rapidfuzz import fuzz, process


class AttendanceMatcher:
    """Matches raw OCR texts with student records using deterministic NIM and fuzzy Name rules."""

    # Common OCR character substitutions in numbers
    NUMERIC_SUBSTITUTIONS = {
        "O": "0", "o": "0", "D": "0", "Q": "0",
        "I": "1", "l": "1", "i": "1", "|": "1", "!": "1",
        "Z": "2", "z": "2",
        "E": "3",
        "A": "4",
        "S": "5", "s": "5",
        "G": "6", "b": "6",
        "T": "7",
        "B": "8",
        "g": "9", "q": "9"
    }

    # Common KTM boilerplate keywords to ignore when evaluating student names
    BOILERPLATE_WORDS = {
        "KARTU", "TANDA", "MAHASISWA", "KTM", "UNIVERSITAS", "INSTITUT", "POLITEKNIK",
        "SEKOLAH", "TINGGI", "FAKULTAS", "JURUSAN", "DEPARTEMEN", "PROGRAM", "STUDI",
        "PRODI", "TEKNIK", "ILMU", "NAMA", "NAME", "NIM", "STUDENT", "ID", "TEMPAT",
        "TANGGAL", "LAHIR", "TTL", "ALAMAT", "STATUS", "MASA", "BERLAKU", "REPUBLIK",
        "INDONESIA", "KEMENTERIAN", "PENDIDIKAN", "KEBUDAYAAN", "RISET", "TEKNOLOGI",
        "PAMULANG", "UNPAM", "SASMITA", "JAYA", "INFORMATIKA", "TPLP", "REGULER",
        "PAS", "FOTO", "JENIS", "KELAMIN", "GOLONGAN", "DARAH"
    }

    def __init__(self, database_records: List[Dict[str, Any]], fuzzy_threshold: float = 70.0):
        self.fuzzy_threshold = fuzzy_threshold
        self.update_records(database_records)

    def update_records(self, database_records: List[Dict[str, Any]]) -> None:
        """Updates internal database cache."""
        self.records = []
        self.nim_map = {}
        self.name_list = []
        self.name_to_rec = {}
        for r in database_records:
            nim_val = str(r.get("NIM") or r.get("nim") or "").strip()
            name_val = str(r.get("Nama") or r.get("name") or "").strip()
            if not nim_val or not name_val:
                continue
            rec_clean = {
                "NIM": nim_val,
                "Nama": name_val,
                "nim": nim_val,
                "name": name_val,
                "Status": str(r.get("Status") or r.get("status") or "Belum Hadir").strip()
            }
            self.records.append(rec_clean)
            self.nim_map[nim_val] = rec_clean
            self.name_list.append(name_val)
            self.name_to_rec[name_val.lower()] = rec_clean

    def repair_numeric_string(self, text: str) -> str:
        """Replaces common OCR letter misreads in numeric sequences."""
        chars = list(text)
        for i, c in enumerate(chars):
            if c in self.NUMERIC_SUBSTITUTIONS:
                # If adjacent characters are digits, substitute with high probability
                left_digit = (i > 0 and chars[i - 1].isdigit())
                right_digit = (i < len(chars) - 1 and chars[i + 1].isdigit())
                if left_digit or right_digit:
                    chars[i] = self.NUMERIC_SUBSTITUTIONS[c]
        return "".join(chars)

    def extract_candidate_numbers(self, text_lines: List[str]) -> List[str]:
        """Extracts cleaned numeric substrings from OCR texts."""
        candidates = []
        for line in text_lines:
            # 1. Direct digit sequence extraction
            digits_only = re.findall(r"\d+", line)
            candidates.extend(digits_only)

            # 2. Extract after numeric character repair
            repaired_line = self.repair_numeric_string(line)
            repaired_digits = re.findall(r"\d+", repaired_line)
            candidates.extend(repaired_digits)

            # 3. Handle numbers with spaces or hyphens (e.g., 23101140 2760)
            line_without_space = re.sub(r"[ -]", "", line)
            if any(c.isdigit() for c in line_without_space):
                rep_no_space = self.repair_numeric_string(line_without_space)
                candidates.extend(re.findall(r"\d+", rep_no_space))

        # Return unique candidate strings sorted by length (longer first)
        unique_candidates = sorted(list(set(candidates)), key=len, reverse=True)
        return unique_candidates

    def match_by_nim(self, text_lines: List[str]) -> Optional[Tuple[Dict[str, Any], str, float]]:
        """
        Jalur 1: NIM Prioritas.
        Searches candidate numbers for match against reference database NIMs.
        """
        candidates = self.extract_candidate_numbers(text_lines)

        for candidate in candidates:
            # 1. Exact match
            if candidate in self.nim_map:
                return self.nim_map[candidate], "NIM (Exact)", 100.0

            # 2. Substring match (candidate contains full NIM or vice versa)
            for ref_nim, rec in self.nim_map.items():
                if len(ref_nim) >= 8 and (ref_nim in candidate or (len(candidate) >= 10 and candidate in ref_nim)):
                    return rec, "NIM (Substring)", 95.0

        # 3. Fuzzy NIM match if candidate has 8+ digits
        for candidate in candidates:
            if len(candidate) >= 8:
                for ref_nim, rec in self.nim_map.items():
                    sim = fuzz.ratio(candidate, ref_nim)
                    # Suffix match bonus (last 4 digits are unique to student)
                    suffix_match = (ref_nim[-4:] in candidate) or (candidate[-4:] == ref_nim[-4:])
                    if sim >= 82.0 or (sim >= 75.0 and suffix_match):
                        return rec, f"NIM Fuzzy ({sim:.1f}%)", float(sim)

        return None

    def clean_name_candidate(self, text: str) -> str:
        """Strips noise, punctuation, labels like 'Nama:', and boilerplate words."""
        # Remove label prefixes
        cleaned = re.sub(r"(?i)^(nama|name|student|identitas)\s*[:=\-]?\s*", "", text.strip())
        # Strip digits & punctuation
        cleaned = re.sub(r"[^a-zA-Z\s]", " ", cleaned)
        words = cleaned.split()
        filtered = [w for w in words if w.upper() not in self.BOILERPLATE_WORDS and len(w) > 1]
        return " ".join(filtered).strip()

    def match_by_name(self, text_lines: List[str]) -> Optional[Tuple[Dict[str, Any], str, float]]:
        """
        Jalur 2: Nama (Fuzzy Matching with RapidFuzz).
        Checks OCR lines and token combinations against reference student names.
        """
        best_match_rec = None
        best_score = 0.0
        best_method = ""

        # Build candidate phrases from single lines and individual words
        candidates: List[str] = []
        for line in text_lines:
            c = self.clean_name_candidate(line)
            if len(c) >= 3:
                candidates.append(c)
                # Also consider individual words of candidate if length >= 4 (e.g. ADITYA)
                words = c.split()
                if len(words) > 1:
                    for w in words:
                        if len(w) >= 4 and w.upper() not in self.BOILERPLATE_WORDS:
                            candidates.append(w)

        # Also add full concatenated string of cleaned text for multi-line names
        if len(candidates) > 1:
            candidates.append(" ".join(candidates))

        for candidate in candidates:
            cand_upper = candidate.upper()
            for ref_name in self.name_list:
                ref_upper = ref_name.upper()

                # Calculate fuzzy scores
                token_sort = fuzz.token_sort_ratio(candidate, ref_name)
                token_set = fuzz.token_set_ratio(candidate, ref_name)
                partial = fuzz.partial_ratio(candidate, ref_name) if len(candidate) >= 4 else 0.0
                
                # Check if candidate is a key name token (e.g. ADITYA in MUHAMMAD ADITYA)
                ref_tokens = ref_upper.split()
                token_exact_match = any(cand_upper == t for t in ref_tokens if len(t) >= 4)
                
                if token_exact_match:
                    score = 95.0
                else:
                    # Combined metric favoring token alignment
                    score = max(token_sort, token_set, (token_sort + partial) / 2.0)

                if score > best_score:
                    best_score = score
                    ref_key = ref_name.lower()
                    best_match_rec = self.name_to_rec.get(ref_key)
                    best_method = f"Nama Fuzzy ({best_score:.1f}%)"

        if best_match_rec and best_score >= self.fuzzy_threshold:
            return best_match_rec, best_method, best_score

        return None

    def match(self, text_lines: List[str]) -> Optional[Dict[str, Any]]:
        """
        Executes OR rule matching:
        1. Prioritas: Jalur NIM
        2. Fallback: Jalur Nama (Fuzzy Matching >= 75%)
        3. Penyelarasan Data: Returns fully reconciled official attributes.
        """
        if not text_lines:
            return None

        # 1. Jalur NIM (Prioritas)
        nim_match = self.match_by_nim(text_lines)
        if nim_match:
            rec, method, conf = nim_match
            return {
                "matched": True,
                "nim": rec["NIM"],
                "nama": rec["Nama"],
                "status": rec.get("Status", "Belum Hadir"),
                "method": method,
                "confidence": conf,
                "raw_record": rec
            }

        # 2. Jalur Nama (Fuzzy Matching)
        name_match = self.match_by_name(text_lines)
        if name_match:
            rec, method, conf = name_match
            return {
                "matched": True,
                "nim": rec["NIM"],
                "nama": rec["Nama"],
                "status": rec.get("Status", "Belum Hadir"),
                "method": method,
                "confidence": conf,
                "raw_record": rec
            }

        return None
