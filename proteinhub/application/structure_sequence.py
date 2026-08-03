from __future__ import annotations

import shlex
from dataclasses import dataclass, replace

from proteinhub.domain.errors import DomainError


THREE_TO_ONE = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "SEC": "U",
    "PYL": "O",
    "ASX": "B",
    "GLX": "Z",
    "XLE": "J",
    "UNK": "X",
    "MSE": "M",
    "SEP": "S",
    "TPO": "T",
    "PTR": "Y",
    "HYP": "P",
    "CSO": "C",
    "CME": "C",
}


@dataclass(frozen=True)
class StructureSequence:
    sequence: str
    source: str
    chain_id: str = ""
    entity_id: str = ""


def extract_structure_sequence(filename: str, content: bytes) -> dict:
    text = content.decode("utf-8", errors="replace")
    for extractor in (
        _extract_pdb_seqres,
        _extract_mmcif_entity_poly,
        _extract_pdb_atom_coordinates,
    ):
        sequences = extractor(text)
        selected = _select_chain_a_sequence(sequences)
        if selected:
            return {
                "filename": filename,
                "sequence": selected.sequence,
                "length": len(selected.sequence),
                "source": selected.source,
                "chain_id": selected.chain_id,
                "entity_id": selected.entity_id,
                "sequence_count": len(sequences),
            }

    raise DomainError("No chain A protein sequence found in PDB or mmCIF file")


def _extract_pdb_seqres(text: str) -> list[StructureSequence]:
    residues_by_chain: dict[str, list[str]] = {}
    for line in text.splitlines():
        if line[:6].strip() != "SEQRES":
            continue
        chain_id = line[11:12].strip() or "?"
        residues = line[19:].split()
        residues_by_chain.setdefault(chain_id, []).extend(residues)

    sequences = []
    for chain_id, residues in residues_by_chain.items():
        sequence = "".join(THREE_TO_ONE.get(residue.upper(), "X") for residue in residues)
        if sequence:
            sequences.append(
                StructureSequence(
                    sequence=sequence,
                    source=f"PDB SEQRES chain {chain_id}",
                    chain_id=chain_id,
                )
            )
    return sequences


def _select_chain_a_sequence(
    sequences: list[StructureSequence],
) -> StructureSequence | None:
    for sequence in sequences:
        if _chain_ids(sequence.chain_id) == ["A"]:
            return sequence
    for sequence in sequences:
        if "A" in _chain_ids(sequence.chain_id):
            return replace(
                sequence,
                chain_id="A",
                source=sequence.source.replace(sequence.chain_id, "A"),
            )
    return None


def _chain_ids(chain_id: str) -> list[str]:
    return [item.strip() for item in chain_id.split(",") if item.strip()]


def _extract_pdb_atom_coordinates(text: str) -> list[StructureSequence]:
    residues_by_chain: dict[str, list[str]] = {}
    seen_residues_by_chain: dict[str, set[str]] = {}

    for line in text.splitlines():
        if line[:6].strip() != "ATOM" or len(line) < 27:
            continue
        atom_name = line[12:16].strip()
        if atom_name != "CA":
            continue
        residue_name = line[17:20].strip().upper()
        chain_id = line[21:22].strip() or "?"
        residue_id = line[22:27].strip()
        if not residue_id:
            continue
        seen_residues = seen_residues_by_chain.setdefault(chain_id, set())
        if residue_id in seen_residues:
            continue
        seen_residues.add(residue_id)
        residues_by_chain.setdefault(chain_id, []).append(residue_name)

    sequences = []
    for chain_id, residues in residues_by_chain.items():
        sequence = "".join(THREE_TO_ONE.get(residue, "X") for residue in residues)
        if sequence:
            sequences.append(
                StructureSequence(
                    sequence=sequence,
                    source=f"PDB ATOM chain {chain_id}",
                    chain_id=chain_id,
                )
            )
    return sequences


def _extract_mmcif_entity_poly(text: str) -> list[StructureSequence]:
    tokens = _cif_tokens(text)
    sequences: list[StructureSequence] = []
    scalar_values: dict[str, str] = {}
    index = 0

    while index < len(tokens):
        token = tokens[index]
        lower_token = token.lower()
        if lower_token == "loop_":
            index = _consume_cif_loop(tokens, index + 1, sequences)
            continue
        if token.startswith("_"):
            value = tokens[index + 1] if index + 1 < len(tokens) else ""
            scalar_values[token.lower()] = value
            index += 2
            continue
        index += 1

    scalar_sequence = _normalize_one_letter_sequence(
        scalar_values.get("_entity_poly.pdbx_seq_one_letter_code_can", "")
        or scalar_values.get("_entity_poly.pdbx_seq_one_letter_code", "")
    )
    scalar_type = scalar_values.get("_entity_poly.type", "")
    if scalar_sequence and _is_protein_polymer(scalar_type):
        entity_id = scalar_values.get("_entity_poly.entity_id", "")
        chain_id = scalar_values.get("_entity_poly.pdbx_strand_id", "")
        sequences.append(
            StructureSequence(
                sequence=scalar_sequence,
                source=_mmcif_source(entity_id, chain_id),
                chain_id=chain_id,
                entity_id=entity_id,
            )
        )

    return sequences


def _consume_cif_loop(
    tokens: list[str], index: int, sequences: list[StructureSequence]
) -> int:
    headers: list[str] = []
    while index < len(tokens) and tokens[index].startswith("_"):
        headers.append(tokens[index].lower())
        index += 1

    values: list[str] = []
    while index < len(tokens):
        token = tokens[index]
        if token.lower() == "loop_" or token.lower().startswith("data_"):
            break
        if token.startswith("_") and (not headers or len(values) % len(headers) == 0):
            break
        values.append(token)
        index += 1

    if headers:
        _collect_entity_poly_loop(headers, values, sequences)
    return index


def _collect_entity_poly_loop(
    headers: list[str], values: list[str], sequences: list[StructureSequence]
) -> None:
    if "_entity_poly.pdbx_seq_one_letter_code_can" in headers:
        sequence_header = "_entity_poly.pdbx_seq_one_letter_code_can"
    elif "_entity_poly.pdbx_seq_one_letter_code" in headers:
        sequence_header = "_entity_poly.pdbx_seq_one_letter_code"
    else:
        return

    column_count = len(headers)
    if column_count == 0:
        return

    sequence_index = headers.index(sequence_header)
    type_index = headers.index("_entity_poly.type") if "_entity_poly.type" in headers else -1
    entity_index = (
        headers.index("_entity_poly.entity_id") if "_entity_poly.entity_id" in headers else -1
    )
    strand_index = (
        headers.index("_entity_poly.pdbx_strand_id")
        if "_entity_poly.pdbx_strand_id" in headers
        else -1
    )

    for row_start in range(0, len(values) - column_count + 1, column_count):
        row = values[row_start : row_start + column_count]
        polymer_type = row[type_index] if type_index >= 0 else ""
        if not _is_protein_polymer(polymer_type):
            continue
        sequence = _normalize_one_letter_sequence(row[sequence_index])
        if not sequence:
            continue
        entity_id = row[entity_index] if entity_index >= 0 else ""
        chain_id = row[strand_index] if strand_index >= 0 else ""
        sequences.append(
            StructureSequence(
                sequence=sequence,
                source=_mmcif_source(entity_id, chain_id),
                chain_id=chain_id,
                entity_id=entity_id,
            )
        )


def _cif_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    lines = iter(text.splitlines())
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(";"):
            value_lines = [line[1:]] if line[1:] else []
            for value_line in lines:
                if value_line.startswith(";"):
                    break
                value_lines.append(value_line)
            tokens.append("\n".join(value_lines))
            continue

        lexer = shlex.shlex(line, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens.extend(list(lexer))
    return tokens


def _normalize_one_letter_sequence(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalpha())


def _is_protein_polymer(polymer_type: str) -> bool:
    return not polymer_type or "polypeptide" in polymer_type.lower() or "protein" in polymer_type.lower()


def _mmcif_source(entity_id: str, chain_id: str) -> str:
    if chain_id:
        return f"mmCIF chain {chain_id}"
    if entity_id:
        return f"mmCIF entity {entity_id}"
    return "mmCIF entity_poly"
