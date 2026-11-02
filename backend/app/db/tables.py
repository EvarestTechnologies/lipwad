"""SQLAlchemy tables. Domain rules live in schemas.py, not here."""

from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ClaimRow(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(primary_key=True)
    lifecycle: Mapped[str]
    discharge_date: Mapped[date | None]
    returned_at: Mapped[datetime | None]
    fields: Mapped[list["FieldRow"]] = relationship(
        cascade="all, delete-orphan", order_by="FieldRow.position"
    )
    flags: Mapped[list["FlagRow"]] = relationship(
        cascade="all, delete-orphan", order_by="FlagRow.position"
    )


class FieldRow(Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"))
    is_coded_line: Mapped[bool]
    position: Mapped[int]
    name: Mapped[str]
    value: Mapped[str]
    confidence: Mapped[float]
    confirmed_by: Mapped[str | None]
    citations: Mapped[list["CitationRow"]] = relationship(
        cascade="all, delete-orphan", order_by="CitationRow.position"
    )


class FlagRow(Base):
    __tablename__ = "flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"))
    position: Mapped[int]
    code: Mapped[str]
    severity: Mapped[str]
    citations: Mapped[list["CitationRow"]] = relationship(
        cascade="all, delete-orphan", order_by="CitationRow.position"
    )


class CitationRow(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"))
    flag_id: Mapped[int | None] = mapped_column(ForeignKey("flags.id"))
    position: Mapped[int]
    kind: Mapped[str]
    source_id: Mapped[str]
    region: Mapped[list | None] = mapped_column(JSON)
    page: Mapped[int | None]
    t_start: Mapped[float | None]
    t_end: Mapped[float | None]
    rule_version: Mapped[str | None]
    quote: Mapped[str | None]


class UploadRow(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"))
    kind: Mapped[str]
    filename: Mapped[str]
    path: Mapped[str]
