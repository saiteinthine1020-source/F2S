"""Protected expense-receipt lifecycle and untrusted-content boundaries."""

import binascii
import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceRole,
    require_capability,
)

MAX_RECEIPT_BYTES = 10 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_STORAGE_KEY = _SHA256
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]")
_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


class ProtectedFileState(StrEnum):
    PENDING = "PENDING"
    QUARANTINED = "QUARANTINED"
    AVAILABLE = "AVAILABLE"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"


class ReceiptFailure(StrEnum):
    SIZE_MISMATCH = "SIZE_MISMATCH"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    SIGNATURE_MISMATCH = "SIGNATURE_MISMATCH"
    POLYGLOT_REJECTED = "POLYGLOT_REJECTED"
    MALWARE_DETECTED = "MALWARE_DETECTED"
    SCANNER_UNAVAILABLE = "SCANNER_UNAVAILABLE"
    RESERVATION_EXPIRED = "RESERVATION_EXPIRED"
    STORAGE_FAILURE = "STORAGE_FAILURE"


class ReceiptStateConflict(Exception):
    pass


class InvalidReceipt(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReceiptRecord:
    id: UUID
    financial_event_id: UUID
    state: str
    media_type: str
    filename: str
    expected_size: int
    checksum_sha256: str
    created_at: datetime
    expires_at: datetime
    version: int
    failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class ReceiptStorageRecord:
    receipt: ReceiptRecord
    storage_key: str
    actual_sha256: str | None


class ReceiptRepository(Protocol):
    async def reserve(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        operation_id: UUID,
        filename: str,
        media_type: str,
        expected_size: int,
        expected_sha256: str,
        storage_key: str,
        expires_at: datetime,
    ) -> ReceiptRecord: ...

    async def list_receipts(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> tuple[ReceiptRecord, ...] | None: ...

    async def get_for_upload(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord | None: ...

    async def mark_quarantined(
        self,
        context: AuthorizationContext,
        *,
        receipt_id: UUID,
        actual_size: int,
        actual_sha256: str,
        detected_media_type: str,
    ) -> ReceiptStorageRecord: ...

    async def mark_available(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord: ...

    async def mark_failed(
        self, context: AuthorizationContext, *, receipt_id: UUID, failure_code: str
    ) -> ReceiptStorageRecord: ...

    async def mark_expired(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord: ...

    async def get_for_download(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptStorageRecord | None: ...

    async def get_status(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptRecord | None: ...

    async def remove(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        receipt_id: UUID,
        operation_id: UUID,
        reason_code: str,
    ) -> ReceiptRecord: ...

    async def due_for_cleanup(self, *, now: datetime) -> tuple[ReceiptStorageRecord, ...]: ...

    async def mark_deleted(self, *, receipt_id: UUID, now: datetime) -> None: ...


class ReceiptStorage(Protocol):
    async def write(self, key: str, content: bytes) -> None: ...
    async def read(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


class MalwareScanner(Protocol):
    async def is_safe(self, content: bytes, media_type: str) -> bool: ...


class DevelopmentMalwareScanner:
    """Deterministic local scanner; production must replace this adapter."""

    async def is_safe(self, content: bytes, media_type: str) -> bool:
        del media_type
        lowered = content.lower()
        return b"eicar-standard-antivirus-test-file" not in lowered and b"<script" not in lowered


class RejectingMalwareScanner:
    async def is_safe(self, content: bytes, media_type: str) -> bool:
        del content, media_type
        raise RuntimeError("SCANNER_UNAVAILABLE")


class MemoryReceiptStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def write(self, key: str, content: bytes) -> None:
        _validate_storage_key(key)
        self.objects[key] = bytes(content)

    async def read(self, key: str) -> bytes:
        _validate_storage_key(key)
        return self.objects[key]

    async def delete(self, key: str) -> None:
        _validate_storage_key(key)
        self.objects.pop(key, None)


class FilesystemReceiptStorage:
    """Private local adapter whose keys can never select a user path."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        _validate_storage_key(key)
        target = (self._root / key[:2] / key).resolve()
        if target.parent.parent != self._root:
            raise ValueError("INVALID_STORAGE_KEY")
        return target

    async def write(self, key: str, content: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)

    async def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class ReceiptService:
    def __init__(
        self, repository: ReceiptRepository, storage: ReceiptStorage, scanner: MalwareScanner
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._scanner = scanner

    async def list(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> tuple[ReceiptRecord, ...] | None:
        self._authorize_reader(context)
        return await self._repository.list_receipts(context, event_id=event_id)

    async def reserve(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        operation_id: UUID,
        filename: str,
        media_type: str,
        expected_size: int,
        checksum_sha256: str,
        storage_key: str,
        expires_at: datetime,
    ) -> ReceiptRecord:
        require_capability(context, Capability.ATTACH_FINANCE_RECEIPTS)
        safe_name = sanitize_filename(filename, media_type)
        if not 1 <= expected_size <= MAX_RECEIPT_BYTES:
            raise InvalidReceipt("INVALID_FILE_SIZE")
        if _SHA256.fullmatch(checksum_sha256) is None:
            raise InvalidReceipt("INVALID_CHECKSUM")
        _validate_storage_key(storage_key)
        return await self._repository.reserve(
            context,
            event_id=event_id,
            operation_id=operation_id,
            filename=safe_name,
            media_type=media_type,
            expected_size=expected_size,
            expected_sha256=checksum_sha256,
            storage_key=storage_key,
            expires_at=expires_at,
        )

    async def upload(
        self,
        context: AuthorizationContext,
        *,
        receipt_id: UUID,
        content: bytes,
        content_type: str,
    ) -> ReceiptRecord:
        require_capability(context, Capability.ATTACH_FINANCE_RECEIPTS)
        item = await self._repository.get_for_upload(context, receipt_id=receipt_id)
        if item is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if item.receipt.state != ProtectedFileState.PENDING:
            raise ReceiptStateConflict
        if content_type != item.receipt.media_type:
            failed = await self._repository.mark_failed(
                context, receipt_id=receipt_id, failure_code=ReceiptFailure.SIGNATURE_MISMATCH
            )
            return failed.receipt
        now = datetime.now(UTC)
        if item.receipt.expires_at <= now:
            await self._repository.mark_expired(context, receipt_id=receipt_id)
            raise ReceiptStateConflict
        failure, detected = validate_content(
            content,
            item.receipt.media_type,
            item.receipt.filename,
            item.receipt.expected_size,
            item.receipt.checksum_sha256,
        )
        if failure is not None:
            failed = await self._repository.mark_failed(
                context, receipt_id=receipt_id, failure_code=failure.value
            )
            return failed.receipt
        try:
            await self._storage.write(item.storage_key, content)
        except Exception:
            await self._repository.mark_failed(
                context, receipt_id=receipt_id, failure_code=ReceiptFailure.STORAGE_FAILURE
            )
            raise
        digest = hashlib.sha256(content).hexdigest()
        try:
            await self._repository.mark_quarantined(
                context,
                receipt_id=receipt_id,
                actual_size=len(content),
                actual_sha256=digest,
                detected_media_type=detected,
            )
        except Exception:
            await self._storage.delete(item.storage_key)
            raise
        try:
            safe = await self._scanner.is_safe(content, detected)
        except Exception:
            failed = await self._repository.mark_failed(
                context, receipt_id=receipt_id, failure_code=ReceiptFailure.SCANNER_UNAVAILABLE
            )
            return failed.receipt
        if not safe:
            failed = await self._repository.mark_failed(
                context, receipt_id=receipt_id, failure_code=ReceiptFailure.MALWARE_DETECTED
            )
            return failed.receipt
        return (await self._repository.mark_available(context, receipt_id=receipt_id)).receipt

    async def authorize_upload(
        self,
        context: AuthorizationContext,
        *,
        receipt_id: UUID,
        content_type: str,
        content_length: int,
    ) -> None:
        """Validate the protected parent and declared body before reading request bytes."""
        require_capability(context, Capability.ATTACH_FINANCE_RECEIPTS)
        item = await self._repository.get_for_upload(context, receipt_id=receipt_id)
        if item is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if item.receipt.state != ProtectedFileState.PENDING:
            raise ReceiptStateConflict
        if item.receipt.expires_at <= datetime.now(UTC):
            await self._repository.mark_expired(context, receipt_id=receipt_id)
            raise ReceiptStateConflict
        if content_type != item.receipt.media_type:
            raise InvalidReceipt("FILE_TYPE_MISMATCH")
        if content_length != item.receipt.expected_size:
            raise InvalidReceipt("INVALID_FILE_SIZE")

    async def download(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> tuple[ReceiptRecord, bytes]:
        self._authorize_reader(context)
        item = await self._repository.get_for_download(context, receipt_id=receipt_id)
        if item is None or item.receipt.state != ProtectedFileState.AVAILABLE:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        content = await self._storage.read(item.storage_key)
        if hashlib.sha256(content).hexdigest() != item.actual_sha256:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        return item.receipt, content

    async def status(
        self, context: AuthorizationContext, *, receipt_id: UUID
    ) -> ReceiptRecord | None:
        self._authorize_reader(context)
        return await self._repository.get_status(context, receipt_id=receipt_id)

    async def remove(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        receipt_id: UUID,
        operation_id: UUID,
        reason_code: str,
    ) -> ReceiptRecord:
        require_capability(context, Capability.ATTACH_FINANCE_RECEIPTS)
        if reason_code not in {"DUPLICATE", "WRONG_FILE", "REPLACED", "OTHER"}:
            raise InvalidReceipt("INVALID_REMOVAL_REASON")
        return await self._repository.remove(
            context,
            event_id=event_id,
            receipt_id=receipt_id,
            operation_id=operation_id,
            reason_code=reason_code,
        )

    async def cleanup_due(self, *, now: datetime) -> int:
        rows = await self._repository.due_for_cleanup(now=now)
        for row in rows:
            await self._storage.delete(row.storage_key)
            await self._repository.mark_deleted(receipt_id=row.receipt.id, now=now)
        return len(rows)

    @staticmethod
    def _authorize_reader(context: AuthorizationContext) -> None:
        if context.role is WorkspaceRole.CONTRIBUTOR:
            require_capability(context, Capability.ATTACH_FINANCE_RECEIPTS)
        else:
            require_capability(context, Capability.VIEW_FINANCE_RECEIPTS)


def sanitize_filename(filename: str, media_type: str) -> str:
    if media_type not in _EXTENSIONS or type(filename) is not str:
        raise InvalidReceipt("INVALID_FILE_TYPE")
    value = unicodedata.normalize("NFKC", filename).strip()
    if not value or len(value) > 128 or any(char in value for char in "/\\\x00"):
        raise InvalidReceipt("INVALID_FILENAME")
    if ".." in value or any(unicodedata.category(char) in {"Cc", "Cf"} for char in value):
        raise InvalidReceipt("INVALID_FILENAME")
    extension = Path(value).suffix.lower()
    if media_type == "image/jpeg" and extension == ".jpeg":
        expected = ".jpeg"
    else:
        expected = _EXTENSIONS[media_type]
    if extension != expected:
        raise InvalidReceipt("FILE_TYPE_MISMATCH")
    sanitized = _SAFE_NAME.sub("_", value)
    if not sanitized or len(sanitized) > 128:
        raise InvalidReceipt("INVALID_FILENAME")
    return sanitized


def validate_content(
    content: bytes, media_type: str, filename: str, size: int, checksum: str
) -> tuple[ReceiptFailure | None, str]:
    del filename
    if len(content) != size or not content or len(content) > MAX_RECEIPT_BYTES:
        return ReceiptFailure.SIZE_MISMATCH, media_type
    if hashlib.sha256(content).hexdigest() != checksum:
        return ReceiptFailure.CHECKSUM_MISMATCH, media_type
    valid = False
    if media_type == "application/pdf":
        valid = _valid_pdf(content)
    elif media_type == "image/png":
        valid = _valid_png(content)
    elif media_type == "image/jpeg":
        valid = _valid_jpeg(content)
    if not valid:
        return ReceiptFailure.SIGNATURE_MISMATCH, media_type
    return None, media_type


def _valid_pdf(value: bytes) -> bool:
    if not value.startswith(b"%PDF-") or not value.rstrip().endswith(b"%%EOF"):
        return False
    lowered = value.lower()
    forbidden = (
        b"/javascript",
        b"/js",
        b"/launch",
        b"/embeddedfile",
        b"mz",
        b"\x7fELF",
        b"PK\x03\x04",
        b"\x89PNG\r\n\x1a\n",
        b"\xff\xd8\xff",
        b"<html",
        b"<script",
    )
    return not any(marker.lower() in lowered for marker in forbidden)


def _valid_png(value: bytes) -> bool:
    if not value.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset = 8
    seen_ihdr = False
    while offset + 12 <= len(value):
        length = int.from_bytes(value[offset : offset + 4], "big")
        kind = value[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(value) or kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
            return False
        data = value[offset + 8 : offset + 8 + length]
        crc = int.from_bytes(value[offset + 8 + length : end], "big")
        if binascii.crc32(kind + data) & 0xFFFFFFFF != crc:
            return False
        if kind == b"IHDR":
            if seen_ihdr or offset != 8 or length != 13:
                return False
            seen_ihdr = True
        if kind == b"IEND":
            return seen_ihdr and length == 0 and end == len(value)
        offset = end
    return False


def _valid_jpeg(value: bytes) -> bool:
    if not value.startswith(b"\xff\xd8") or not value.endswith(b"\xff\xd9"):
        return False
    lowered = value.lower()
    if any(
        marker.lower() in lowered
        for marker in (
            b"MZ",
            b"\x7fELF",
            b"PK\x03\x04",
            b"%PDF-",
            b"\x89PNG\r\n\x1a\n",
            b"<html",
            b"<script",
        )
    ):
        return False
    return value.count(b"\xff\xd8") == 1 and value.count(b"\xff\xd9") == 1


def _validate_storage_key(key: str) -> None:
    if type(key) is not str or _STORAGE_KEY.fullmatch(key) is None:
        raise ValueError("INVALID_STORAGE_KEY")
