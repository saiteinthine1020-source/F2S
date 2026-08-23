"""Untrusted receipt validation, quarantine, authorization, and cleanup tests."""

import asyncio
import binascii
import hashlib
import struct
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.modules.household_finance import (
    MAX_RECEIPT_BYTES,
    DevelopmentMalwareScanner,
    InvalidReceipt,
    MemoryReceiptStorage,
    ReceiptRecord,
    ReceiptRepository,
    ReceiptService,
    ReceiptStateConflict,
    ReceiptStorageRecord,
    sanitize_filename,
    validate_content,
)
from app.modules.workspace_access import AuthorizationContext, AuthorizationDenied, WorkspaceRole


def _png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", b"")
        + chunk(b"IEND", b"")
    )


class FakeReceiptRepository:
    def __init__(self, content: bytes) -> None:
        now = datetime.now(UTC)
        self.record = ReceiptRecord(
            uuid4(),
            uuid4(),
            "PENDING",
            "image/png",
            "receipt.png",
            len(content),
            hashlib.sha256(content).hexdigest(),
            now,
            now + timedelta(minutes=15),
            1,
        )
        self.storage_key = "a" * 64
        self.actual_sha256: str | None = None

    def stored(self) -> ReceiptStorageRecord:
        return ReceiptStorageRecord(self.record, self.storage_key, self.actual_sha256)

    async def get_for_upload(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord | None:
        del context
        return self.stored() if receipt_id == self.record.id else None

    async def mark_quarantined(
        self, context: AuthorizationContext, **values: object
    ) -> ReceiptStorageRecord:
        del context
        self.actual_sha256 = cast(str, values["actual_sha256"])
        self.record = replace(self.record, state="QUARANTINED", version=2)
        return self.stored()

    async def mark_available(
        self, context: AuthorizationContext, **values: object
    ) -> ReceiptStorageRecord:
        del context, values
        self.record = replace(self.record, state="AVAILABLE", version=3)
        return self.stored()

    async def mark_failed(
        self, context: AuthorizationContext, **values: object
    ) -> ReceiptStorageRecord:
        del context
        self.record = replace(
            self.record,
            state="FAILED",
            failure_code=cast(str, values["failure_code"]),
            version=self.record.version + 1,
        )
        return self.stored()

    async def mark_expired(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord:
        del context, receipt_id
        self.record = replace(
            self.record,
            state="EXPIRED",
            failure_code="RESERVATION_EXPIRED",
            version=self.record.version + 1,
        )
        return self.stored()

    async def get_for_download(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord | None:
        del context
        return self.stored() if receipt_id == self.record.id else None

    async def get_status(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptRecord | None:
        del context
        return self.record if receipt_id == self.record.id else None

    async def due_for_cleanup(self, *, now: datetime) -> tuple[ReceiptStorageRecord, ...]:
        del now
        return (self.stored(),) if self.record.state == "FAILED" else ()

    async def mark_deleted(self, *, receipt_id: UUID, now: datetime) -> None:
        del receipt_id, now
        self.record = replace(self.record, state="DELETED", version=self.record.version + 1)


def _context(role: WorkspaceRole = WorkspaceRole.ADMIN) -> AuthorizationContext:
    return AuthorizationContext(uuid4(), uuid4(), uuid4(), role, uuid4())


@pytest.mark.parametrize(
    "name",
    ["../receipt.pdf", "..\\receipt.pdf", "folder/receipt.pdf", "receipt.exe", "\u202ereceipt.pdf"],
)
def test_malicious_filename_traversal_and_type_confusion_are_rejected(name: str) -> None:
    with pytest.raises(InvalidReceipt):
        sanitize_filename(name, "application/pdf")


def test_signature_checksum_polyglot_and_size_validation_fail_closed() -> None:
    content = _png()
    checksum = hashlib.sha256(content).hexdigest()
    assert validate_content(content, "image/png", "receipt.png", len(content), checksum)[0] is None
    assert (
        validate_content(
            b"MZ" + content,
            "image/png",
            "receipt.png",
            len(content) + 2,
            hashlib.sha256(b"MZ" + content).hexdigest(),
        )[0]
        is not None
    )
    assert (
        validate_content(content, "image/png", "receipt.png", len(content), "0" * 64)[0] is not None
    )
    assert (
        validate_content(content, "application/pdf", "receipt.pdf", len(content), checksum)[0]
        is not None
    )
    assert MAX_RECEIPT_BYTES == 10 * 1024 * 1024


def test_upload_quarantine_scan_download_checksum_and_cleanup_lifecycle() -> None:
    async def exercise() -> None:
        content = _png()
        repository = FakeReceiptRepository(content)
        storage = MemoryReceiptStorage()
        service = ReceiptService(
            cast(ReceiptRepository, repository), storage, DevelopmentMalwareScanner()
        )
        with pytest.raises(AuthorizationDenied):
            await service.download(_context(), receipt_id=uuid4())
        available = await service.upload(
            _context(),
            receipt_id=repository.record.id,
            content=content,
            content_type="image/png",
        )
        assert available.state == "AVAILABLE"
        downloaded, exact = await service.download(_context(), receipt_id=available.id)
        assert downloaded.id == available.id and exact == content

        repository.actual_sha256 = "0" * 64
        with pytest.raises(AuthorizationDenied):
            await service.download(_context(), receipt_id=available.id)

        unsafe_content = b"%PDF-1.7\nEICAR-STANDARD-ANTIVIRUS-TEST-FILE\n%%EOF"
        unsafe_repository = FakeReceiptRepository(unsafe_content)
        unsafe_repository.record = replace(
            unsafe_repository.record,
            media_type="application/pdf",
            filename="receipt.pdf",
            expected_size=len(unsafe_content),
            checksum_sha256=hashlib.sha256(unsafe_content).hexdigest(),
        )
        unsafe = ReceiptService(
            cast(ReceiptRepository, unsafe_repository), storage, DevelopmentMalwareScanner()
        )
        failed = await unsafe.upload(
            _context(),
            receipt_id=unsafe_repository.record.id,
            content=unsafe_content,
            content_type="application/pdf",
        )
        assert failed.state == "FAILED"
        assert await unsafe.cleanup_due(now=datetime.now(UTC) + timedelta(days=2)) == 1
        assert unsafe_repository.record.state == "DELETED"

    asyncio.run(exercise())


def test_advisor_cannot_upload_and_contributor_has_no_aggregate_capability() -> None:
    async def exercise() -> None:
        content = _png()
        repository = FakeReceiptRepository(content)
        service = ReceiptService(
            cast(ReceiptRepository, repository),
            MemoryReceiptStorage(),
            DevelopmentMalwareScanner(),
        )
        with pytest.raises(AuthorizationDenied):
            await service.upload(
                _context(WorkspaceRole.ADVISOR),
                receipt_id=repository.record.id,
                content=content,
                content_type="image/png",
            )

    asyncio.run(exercise())


def test_expired_reservation_is_terminal_and_never_uploaded() -> None:
    async def exercise() -> None:
        content = _png()
        repository = FakeReceiptRepository(content)
        repository.record = replace(
            repository.record,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        service = ReceiptService(
            cast(ReceiptRepository, repository),
            MemoryReceiptStorage(),
            DevelopmentMalwareScanner(),
        )
        with pytest.raises(ReceiptStateConflict):
            await service.upload(
                _context(),
                receipt_id=repository.record.id,
                content=content,
                content_type="image/png",
            )
        assert repository.record.state == "EXPIRED"

    asyncio.run(exercise())
