"""Converts claims between domain schemas and database rows."""

from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.schemas import (
    ActivityStep,
    Citation,
    Claim,
    Field,
    Flag,
    Lifecycle,
    Readiness,
    Upload,
)
from app.db.tables import ActivityRow, CitationRow, ClaimRow, FieldRow, FlagRow, UploadRow


class StaleClaimError(Exception):
    """The claim changed in the database after this copy was loaded."""


def save_claim(session: Session, claim: Claim) -> Claim:
    """Store a claim, refusing a copy that is older than the stored one."""
    row = session.get(ClaimRow, claim.id)
    if row is None:
        row = ClaimRow(id=claim.id, version=0)
        session.add(row)
    elif row.version != claim.version:
        raise StaleClaimError(f"{claim.id}: stored v{row.version}, saving v{claim.version}")

    row.version = claim.version + 1
    row.lifecycle = claim.lifecycle.value
    row.readiness = claim.readiness.value if claim.readiness else None
    row.hie_id = claim.hie_id
    row.discharge_date = claim.discharge_date
    row.returned_at = claim.returned_at.astimezone(UTC) if claim.returned_at else None
    row.fields = [
        *(_field_row(item, position, False) for position, item in enumerate(claim.fields)),
        *(_field_row(item, position, True) for position, item in enumerate(claim.coded_lines)),
    ]
    row.flags = [
        FlagRow(
            position=position,
            code=item.code,
            severity=item.severity,
            citations=_citation_rows(item.citations),
        )
        for position, item in enumerate(claim.flags)
    ]
    session.flush()
    return claim.model_copy(update={"version": row.version})


def load_claim(session: Session, claim_id: str) -> Claim | None:
    row = session.get(
        ClaimRow,
        claim_id,
        options=[
            selectinload(ClaimRow.fields).selectinload(FieldRow.citations),
            selectinload(ClaimRow.flags).selectinload(FlagRow.citations),
        ],
    )
    if row is None:
        return None
    return Claim(
        id=row.id,
        version=row.version,
        lifecycle=Lifecycle(row.lifecycle),
        readiness=Readiness(row.readiness) if row.readiness else None,
        hie_id=row.hie_id,
        discharge_date=row.discharge_date,
        returned_at=row.returned_at.replace(tzinfo=UTC) if row.returned_at else None,
        fields=[_field(item) for item in row.fields if not item.is_coded_line],
        coded_lines=[_field(item) for item in row.fields if item.is_coded_line],
        flags=[
            Flag(code=item.code, severity=item.severity, citations=_citations(item.citations))
            for item in row.flags
        ],
    )


def save_upload(session: Session, upload: Upload) -> None:
    session.add(UploadRow(**upload.model_dump()))
    session.flush()


def add_activity(session: Session, step: ActivityStep) -> None:
    data = step.model_dump(mode="json")
    session.add(ActivityRow(**{**data, "at": step.at.astimezone(UTC)}))
    session.flush()


def list_activity(session: Session, claim_id: str | None = None) -> list[ActivityStep]:
    query = select(ActivityRow).order_by(ActivityRow.at, ActivityRow.id)
    if claim_id is not None:
        query = query.where(ActivityRow.claim_id == claim_id)
    return [
        ActivityStep(
            claim_id=row.claim_id,
            at=row.at.replace(tzinfo=UTC),
            kind=row.kind,
            text=row.text,
            model=row.model,
            citations=row.citations,
        )
        for row in session.scalars(query)
    ]


def list_uploads(session: Session, claim_id: str) -> list[Upload]:
    rows = session.scalars(select(UploadRow).where(UploadRow.claim_id == claim_id))
    return [
        Upload(
            id=row.id, claim_id=row.claim_id, kind=row.kind, filename=row.filename, path=row.path
        )
        for row in rows
    ]


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
