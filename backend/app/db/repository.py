"""Converts claims between domain schemas and database rows."""

from sqlalchemy.orm import Session

from app.db.schemas import Citation, Claim, Field, Flag, Lifecycle
from app.db.tables import CitationRow, ClaimRow, FieldRow, FlagRow


def save_claim(session: Session, claim: Claim) -> None:
    existing = session.get(ClaimRow, claim.id)
    if existing:
        session.delete(existing)
        session.flush()
    session.add(_claim_row(claim))


def load_claim(session: Session, claim_id: str) -> Claim | None:
    row = session.get(ClaimRow, claim_id)
    if row is None:
        return None
    return Claim(
        id=row.id,
        lifecycle=Lifecycle(row.lifecycle),
        discharge_date=row.discharge_date,
        returned_at=row.returned_at,
        fields=[_field(item) for item in row.fields if not item.is_coded_line],
        coded_lines=[_field(item) for item in row.fields if item.is_coded_line],
        flags=[
            Flag(code=item.code, severity=item.severity, citations=_citations(item.citations))
            for item in row.flags
        ],
    )


def _claim_row(claim: Claim) -> ClaimRow:
    fields = [_field_row(item, position, False) for position, item in enumerate(claim.fields)]
    lines = [_field_row(item, position, True) for position, item in enumerate(claim.coded_lines)]
    return ClaimRow(
        id=claim.id,
        lifecycle=claim.lifecycle.value,
        discharge_date=claim.discharge_date,
        returned_at=claim.returned_at,
        fields=fields + lines,
        flags=[
            FlagRow(
                position=position,
                code=item.code,
                severity=item.severity,
                citations=_citation_rows(item.citations),
            )
            for position, item in enumerate(claim.flags)
        ],
    )


def _field_row(field: Field, position: int, is_coded_line: bool) -> FieldRow:
    return FieldRow(
        is_coded_line=is_coded_line,
        position=position,
        name=field.name,
        value=field.value,
        confidence=field.confidence,
        confirmed_by=field.confirmed_by,
        citations=_citation_rows(field.citations),
    )


def _citation_rows(citations: list[Citation]) -> list[CitationRow]:
    return [
        CitationRow(position=position, **citation.model_dump())
        for position, citation in enumerate(citations)
    ]


def _field(row: FieldRow) -> Field:
    return Field(
        name=row.name,
        value=row.value,
        confidence=row.confidence,
        confirmed_by=row.confirmed_by,
        citations=_citations(row.citations),
    )


def _citations(rows: list[CitationRow]) -> list[Citation]:
    return [
        Citation(
            kind=row.kind,
            source_id=row.source_id,
            region=row.region,
            page=row.page,
            t_start=row.t_start,
            t_end=row.t_end,
            rule_version=row.rule_version,
            quote=row.quote,
        )
        for row in rows
    ]
