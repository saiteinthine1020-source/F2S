"""Strict workspace-scoped manual income and expense creation API."""

import hashlib
import json
import re
from dataclasses import replace
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import correlation_for, safe_error
from app.api.financial_event_cursors import (
    InvalidFinancialEventCursor,
    decode_financial_event_cursor,
    encode_financial_event_cursor,
)
from app.api.security import AuthenticatedAccountId
from app.api.workspace_settings import PreconditionRequired
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.finance import SqlAlchemyFinanceRepository
from app.infrastructure.database.repositories.idempotency import SqlAlchemyIdempotencyRepository
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
from app.modules.application_support import IdempotencyKeyReused, IdempotencyService
from app.modules.audit import (
    AuditAction,
    AuditActor,
    AuditContext,
    AuditEventIntent,
    AuditModule,
    AuditReason,
    AuditResourceType,
    AuditResult,
    AuditScope,
    AuditSource,
)
from app.modules.household_finance import (
    ActivityClassification,
    ApprovalReasonCode,
    CashDirection,
    FinanceCommandMetadata,
    FinancialEventArchiveScope,
    FinancialEventCommandService,
    FinancialEventDecision,
    FinancialEventDecisionCommand,
    FinancialEventDecisionService,
    FinancialEventInProgress,
    FinancialEventKind,
    FinancialEventQuery,
    FinancialEventQueryService,
    FinancialEventRecord,
    FinancialEventRecoveryRequired,
    FinancialEventReplayUnavailable,
    FinancialEventStateConflict,
    FinancialEventStatusRecord,
    FinancialEventVersionMismatch,
    InvalidFinanceCategory,
    InvalidFinancialEventFilter,
    ManualFinancialEventCommand,
    PaymentMethod,
    PendingFinancialEventUpdateCommand,
    PendingFinancialEventUpdateService,
    RejectionReasonCode,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceVersionMismatch,
)
from app.shared_kernel import (
    INITIAL_CURRENCY_REGISTRY,
    IdempotencyKey,
    Money,
    OperationCode,
    RequestFingerprint,
)

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/financial-events", tags=["finance"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key")]
IfMatch = Annotated[str | None, Header(alias="If-Match")]
StrictAmount = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=64)]
StrictCurrency = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[A-Z]{3}$"),
]
_DEFAULT_SORT = "-occurred_on,-created_at,id"
_ETAG = re.compile(r'^"v([1-9][0-9]*)"$')
_ALLOWED_QUERY_PARAMETERS = frozenset(
    {
        "status",
        "occurred_from",
        "occurred_to",
        "category_id",
        "event_kind",
        "direction",
        "activity_classification",
        "payment_method",
        "currency",
        "archived",
        "farming_investment_id",
        "page_size",
        "after",
        "sort",
    }
)


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class FinancialEventVisibility(StrEnum):
    ALL_PERMITTED = "ALL_PERMITTED"
    OWN_SUBMISSIONS = "OWN_SUBMISSIONS"
    APPROVED_ONLY = "APPROVED_ONLY"


class UnknownFinancialEventFilter(Exception):
    pass


class InvalidFinancialEventSort(Exception):
    pass


class MoneyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: StrictAmount
    currency_code: StrictCurrency


class FinancialEventCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: UUID
    event_kind: FinancialEventKind
    activity_classification: ActivityClassification
    occurred_on: date
    finance_category_id: UUID
    money: MoneyRequest
    payment_method: PaymentMethod
    counterparty: str | None = Field(default=None, min_length=1, max_length=256)
    reference: str | None = Field(default=None, min_length=1, max_length=128)
    notes: str | None = Field(default=None, min_length=1, max_length=2000)


class FinancialEventUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    activity_classification: ActivityClassification | None = None
    occurred_on: date | None = None
    finance_category_id: UUID | None = None
    money: MoneyRequest | None = None
    payment_method: PaymentMethod | None = None
    counterparty: str | None = Field(default=None, min_length=1, max_length=256)
    reference: str | None = Field(default=None, min_length=1, max_length=128)
    notes: str | None = Field(default=None, min_length=1, max_length=2000)


class FinancialEventApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: UUID
    reason_code: ApprovalReasonCode


class FinancialEventRejectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: UUID
    reason_code: RejectionReasonCode
    explanation: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512)]


class MoneyRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: str
    currency_code: str


class FinancialEventRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    event_kind: FinancialEventKind
    cash_direction: str
    activity_classification: ActivityClassification
    occurred_on: date
    finance_category_id: UUID
    money: MoneyRepresentation
    payment_method: PaymentMethod
    counterparty: str | None
    reference: str | None
    notes: str | None
    approval_status: str
    posting_status: str
    version: int


class FinancialEventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: FinancialEventRepresentation


class FinancialEventListMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    next_cursor: str | None
    page_size: int
    sort: str
    visibility: FinancialEventVisibility


class FinancialEventListEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: tuple[FinancialEventRepresentation, ...]
    meta: FinancialEventListMetadata


class FinancialEventHistoryActor(StrEnum):
    SUBMITTER = "SUBMITTER"
    WORKSPACE_ADMIN = "WORKSPACE_ADMIN"


class FinancialEventStatusRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str
    approval_status: ApprovalStatus
    actor: FinancialEventHistoryActor
    occurred_at: datetime


class FinancialEventStatusHistoryEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: tuple[FinancialEventStatusRepresentation, ...]


def _service(session: AsyncSession) -> FinancialEventCommandService:
    return FinancialEventCommandService(
        SqlAlchemyFinanceRepository(session),
        IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
    )


def _query_service(session: AsyncSession) -> FinancialEventQueryService:
    return FinancialEventQueryService(SqlAlchemyFinanceRepository(session))


def _update_service(session: AsyncSession) -> PendingFinancialEventUpdateService:
    return PendingFinancialEventUpdateService(SqlAlchemyFinanceRepository(session))


def _decision_service(session: AsyncSession) -> FinancialEventDecisionService:
    return FinancialEventDecisionService(
        SqlAlchemyFinanceRepository(session),
        IdempotencyService(SqlAlchemyIdempotencyRepository(session)),
    )


async def _resolve_context(
    session: AsyncSession,
    *,
    account_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
) -> AuthorizationContext:
    return await SqlAlchemyWorkspaceAccessRepository(session).resolve_context(
        actor_account_id=account_id,
        workspace_id=workspace_id,
        correlation_id=correlation_id,
    )


def _fingerprint(payload: FinancialEventCreateRequest) -> RequestFingerprint:
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return RequestFingerprint.from_canonical_bytes(canonical)


def _decision_fingerprint(
    event_id: UUID,
    decision: FinancialEventDecision,
    payload: FinancialEventApprovalRequest | FinancialEventRejectionRequest,
) -> RequestFingerprint:
    canonical = json.dumps(
        {
            "decision": decision.value,
            "event_id": str(event_id),
            "payload": payload.model_dump(mode="json"),
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return RequestFingerprint.from_canonical_bytes(canonical)


def _representation(record: FinancialEventRecord) -> FinancialEventRepresentation:
    currency = INITIAL_CURRENCY_REGISTRY.require(record.currency_code)
    exact_money = Money.from_calculated(record.amount, currency)
    if exact_money.amount != record.amount:
        raise ValueError("INVALID_STORED_MONEY")
    money = exact_money.to_api()
    return FinancialEventRepresentation(
        id=record.id,
        event_kind=FinancialEventKind(record.event_kind),
        cash_direction=record.cash_direction,
        activity_classification=ActivityClassification(record.activity_classification_code),
        occurred_on=record.occurred_on,
        finance_category_id=record.finance_category_id,
        money=MoneyRepresentation(**money),
        payment_method=PaymentMethod(record.payment_method_code),
        counterparty=record.counterparty_text,
        reference=record.reference_text,
        notes=record.notes,
        approval_status=record.approval_status,
        posting_status=record.posting_status,
        version=record.version,
    )


def _status_representation(
    record: FinancialEventStatusRecord,
) -> FinancialEventStatusRepresentation:
    submitter_action = record.action_code in {
        "FINANCIAL_EVENT_SUBMITTED",
        "FINANCIAL_EVENT_PENDING_UPDATED",
    }
    return FinancialEventStatusRepresentation(
        action=record.action_code,
        approval_status=ApprovalStatus(record.approval_status),
        actor=(
            FinancialEventHistoryActor.SUBMITTER
            if submitter_action
            else FinancialEventHistoryActor.WORKSPACE_ADMIN
        ),
        occurred_at=record.occurred_at,
    )


def _expected_version(value: str | None) -> int:
    if value is None:
        raise PreconditionRequired
    match = _ETAG.fullmatch(value)
    if match is None:
        raise WorkspaceVersionMismatch
    return int(match.group(1))


def _single_query_value(request: Request, name: str) -> str | None:
    values = request.query_params.getlist(name)
    if len(values) > 1:
        raise InvalidFinancialEventFilter
    return values[0] if values else None


def _enum_query_values[EnumValue: StrEnum](
    request: Request, name: str, value_type: type[EnumValue]
) -> tuple[str, ...]:
    try:
        return tuple(
            sorted({value_type(value).value for value in request.query_params.getlist(name)})
        )
    except ValueError as error:
        raise InvalidFinancialEventFilter from error


def _uuid_query_values(request: Request, name: str) -> tuple[UUID, ...]:
    try:
        return tuple(sorted({UUID(value) for value in request.query_params.getlist(name)}))
    except ValueError as error:
        raise InvalidFinancialEventFilter from error


def _date_query_value(request: Request, name: str) -> date | None:
    value = _single_query_value(request, name)
    if value is None:
        return None
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value, re.ASCII) is None:
        raise InvalidFinancialEventFilter
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise InvalidFinancialEventFilter from error


def _page_size(request: Request) -> int:
    value = _single_query_value(request, "page_size")
    if value is None:
        return 25
    if re.fullmatch(r"[1-9][0-9]{0,2}", value, re.ASCII) is None:
        raise InvalidFinancialEventFilter
    parsed = int(value)
    if not 1 <= parsed <= 100:
        raise InvalidFinancialEventFilter
    return parsed


def _query_scope(context: AuthorizationContext, query: FinancialEventQuery) -> str:
    canonical = json.dumps(
        {
            "workspace": str(context.workspace_id),
            "membership": str(context.membership_id),
            "role": context.role.value,
            "status": query.approval_statuses,
            "occurred_from": (
                query.occurred_from.isoformat() if query.occurred_from is not None else None
            ),
            "occurred_to": (
                query.occurred_to.isoformat() if query.occurred_to is not None else None
            ),
            "category_id": tuple(str(value) for value in query.category_ids),
            "event_kind": query.event_kinds,
            "direction": query.cash_directions,
            "activity_classification": query.activity_classifications,
            "payment_method": query.payment_methods,
            "currency": query.currencies,
            "archived": query.archive_scope.value,
            "sort": _DEFAULT_SORT,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def _parse_event_query(
    request: Request, context: AuthorizationContext
) -> tuple[FinancialEventQuery, str]:
    unknown = set(request.query_params) - _ALLOWED_QUERY_PARAMETERS
    if unknown:
        raise UnknownFinancialEventFilter
    sort = _single_query_value(request, "sort")
    if sort is not None and sort != _DEFAULT_SORT:
        raise InvalidFinancialEventSort
    farming_ids = _uuid_query_values(request, "farming_investment_id")
    if farming_ids:
        # Phase 2 explicitly defers canonical farming source links.
        raise InvalidFinancialEventFilter
    currencies = tuple(sorted(set(request.query_params.getlist("currency"))))
    for currency_code in currencies:
        INITIAL_CURRENCY_REGISTRY.require(currency_code)
    archive_value = _single_query_value(request, "archived") or "ACTIVE"
    try:
        archive_scope = FinancialEventArchiveScope(archive_value)
    except ValueError as error:
        raise InvalidFinancialEventFilter from error
    query = FinancialEventQuery(
        approval_statuses=_enum_query_values(request, "status", ApprovalStatus),
        occurred_from=_date_query_value(request, "occurred_from"),
        occurred_to=_date_query_value(request, "occurred_to"),
        category_ids=_uuid_query_values(request, "category_id"),
        event_kinds=_enum_query_values(request, "event_kind", FinancialEventKind),
        cash_directions=_enum_query_values(request, "direction", CashDirection),
        activity_classifications=_enum_query_values(
            request, "activity_classification", ActivityClassification
        ),
        payment_methods=_enum_query_values(request, "payment_method", PaymentMethod),
        currencies=currencies,
        archive_scope=archive_scope,
        page_size=_page_size(request),
    )
    scope = _query_scope(context, query)
    after = _single_query_value(request, "after")
    if after is not None:
        query = replace(
            query,
            after=decode_financial_event_cursor(
                after,
                expected_scope=scope,
                digests=request.app.state.keyed_digests,
            ),
        )
    return query, scope


def _visibility(context: AuthorizationContext) -> FinancialEventVisibility:
    if context.role.value == "CONTRIBUTOR":
        return FinancialEventVisibility.OWN_SUBMISSIONS
    if context.role.value == "ADVISOR":
        return FinancialEventVisibility.APPROVED_ONLY
    return FinancialEventVisibility.ALL_PERMITTED


@router.get("", response_model=FinancialEventListEnvelope)
async def list_financial_events(
    workspace_id: UUID,
    request: Request,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> FinancialEventListEnvelope | Response:
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        query, scope = _parse_event_query(request, context)
        page = await _query_service(session).list_events(context, query=query)
    except AuthorizationDenied as error:
        return _authorization_error(request, error)
    except UnknownFinancialEventFilter:
        return _query_error(request, "UNKNOWN_FILTER", "The query contains an unknown filter.")
    except InvalidFinancialEventSort:
        return _query_error(request, "INVALID_SORT", "The requested sort is not supported.")
    except InvalidFinancialEventCursor:
        return _query_error(request, "INVALID_CURSOR", "The pagination cursor is invalid.")
    except (InvalidFinancialEventFilter, ValueError):
        return _query_error(request, "INVALID_FILTER", "The requested filters are invalid.")

    next_cursor = (
        encode_financial_event_cursor(
            page.next_position,
            scope=scope,
            digests=request.app.state.keyed_digests,
        )
        if page.next_position is not None
        else None
    )
    return FinancialEventListEnvelope(
        data=tuple(_representation(record) for record in page.records),
        meta=FinancialEventListMetadata(
            next_cursor=next_cursor,
            page_size=query.page_size,
            sort=_DEFAULT_SORT,
            visibility=_visibility(context),
        ),
    )


@router.get("/{event_id}", response_model=FinancialEventEnvelope)
async def get_financial_event(
    workspace_id: UUID,
    event_id: UUID,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> FinancialEventEnvelope | Response:
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        record = await _query_service(session).get_event(context, event_id=event_id)
        if record is None:
            await _audit_access_denial(session, context, AuditReason.RESOURCE_NOT_FOUND)
            return _authorization_error(request, AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND))
    except AuthorizationDenied as error:
        return _authorization_error(request, error)
    response.headers["ETag"] = f'"v{record.version}"'
    return FinancialEventEnvelope(data=_representation(record))


@router.get("/{event_id}/status-history", response_model=FinancialEventStatusHistoryEnvelope)
async def get_financial_event_status_history(
    workspace_id: UUID,
    event_id: UUID,
    request: Request,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> FinancialEventStatusHistoryEnvelope | Response:
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        history = await _query_service(session).get_status_history(context, event_id=event_id)
        if history is None:
            await _audit_access_denial(session, context, AuditReason.RESOURCE_NOT_FOUND)
            return _authorization_error(request, AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND))
    except AuthorizationDenied as error:
        return _authorization_error(request, error)
    return FinancialEventStatusHistoryEnvelope(
        data=tuple(_status_representation(record) for record in history)
    )


async def _run_financial_event_decision(
    *,
    workspace_id: UUID,
    event_id: UUID,
    payload: FinancialEventApprovalRequest | FinancialEventRejectionRequest,
    decision: FinancialEventDecision,
    request: Request,
    response: Response,
    account_id: UUID,
    session: AsyncSession,
    idempotency_key: str,
) -> FinancialEventEnvelope | Response:
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        record, replayed = await _decision_service(session).decide(
            context,
            event_id=event_id,
            command=FinancialEventDecisionCommand(
                decision=decision,
                reason_code=payload.reason_code,
                explanation=(
                    payload.explanation
                    if isinstance(payload, FinancialEventRejectionRequest)
                    else None
                ),
            ),
            metadata=FinanceCommandMetadata(
                operation_id=payload.operation_id,
                operation=OperationCode(
                    "APPROVE_FINANCIAL_EVENT"
                    if decision is FinancialEventDecision.APPROVE
                    else "REJECT_FINANCIAL_EVENT"
                ),
                idempotency_key=IdempotencyKey(idempotency_key),
                request_fingerprint=_decision_fingerprint(event_id, decision, payload),
                required_capability=Capability.APPROVE_OR_REJECT_SUBMISSIONS,
            ),
        )
    except AuthorizationDenied as error:
        if "context" in locals() and error.code is DenialCode.PERMISSION_DENIED:
            await _audit_permission_denial(session, context)
        return _authorization_error(request, error)
    except IdempotencyKeyReused:
        return _conflict(
            request,
            "IDEMPOTENCY_KEY_REUSED",
            "The idempotency key is already bound to another request.",
        )
    except (FinancialEventInProgress, FinancialEventRecoveryRequired):
        return _conflict(request, "CONFLICT", "The decision is already being processed.")
    except FinancialEventReplayUnavailable:
        return _conflict(request, "CONFLICT", "The stored decision cannot be replayed safely.")
    except FinancialEventStateConflict:
        return _conflict(
            request,
            "INVALID_STATE_TRANSITION",
            "Only a Pending financial event can be approved or rejected.",
        )
    response.headers["Idempotency-Replayed"] = "true" if replayed else "false"
    response.headers["ETag"] = f'"v{record.version}"'
    return FinancialEventEnvelope(data=_representation(record))


@router.post("/{event_id}/approvals", response_model=FinancialEventEnvelope)
async def approve_financial_event(
    workspace_id: UUID,
    event_id: UUID,
    payload: FinancialEventApprovalRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    idempotency_key: IdempotencyHeader,
) -> FinancialEventEnvelope | Response:
    del browser
    return await _run_financial_event_decision(
        workspace_id=workspace_id,
        event_id=event_id,
        payload=payload,
        decision=FinancialEventDecision.APPROVE,
        request=request,
        response=response,
        account_id=account_id,
        session=session,
        idempotency_key=idempotency_key,
    )


@router.post("/{event_id}/rejections", response_model=FinancialEventEnvelope)
async def reject_financial_event(
    workspace_id: UUID,
    event_id: UUID,
    payload: FinancialEventRejectionRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    idempotency_key: IdempotencyHeader,
) -> FinancialEventEnvelope | Response:
    del browser
    return await _run_financial_event_decision(
        workspace_id=workspace_id,
        event_id=event_id,
        payload=payload,
        decision=FinancialEventDecision.REJECT,
        request=request,
        response=response,
        account_id=account_id,
        session=session,
        idempotency_key=idempotency_key,
    )


@router.patch("/{event_id}", response_model=FinancialEventEnvelope)
async def update_pending_financial_event(
    workspace_id: UUID,
    event_id: UUID,
    payload: FinancialEventUpdateRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> FinancialEventEnvelope | Response:
    del browser
    expected_version = _expected_version(if_match)
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        record = await _update_service(session).update(
            context,
            event_id=event_id,
            expected_version=expected_version,
            command=PendingFinancialEventUpdateCommand(
                changed_fields=frozenset(payload.model_fields_set),
                activity_classification=payload.activity_classification,
                occurred_on=payload.occurred_on,
                finance_category_id=payload.finance_category_id,
                amount=payload.money.amount if payload.money is not None else None,
                currency_code=(payload.money.currency_code if payload.money is not None else None),
                payment_method=payload.payment_method,
                counterparty=payload.counterparty,
                reference=payload.reference,
                notes=payload.notes,
            ),
        )
    except AuthorizationDenied as error:
        if "context" in locals() and error.code is DenialCode.PERMISSION_DENIED:
            await _audit_permission_denial(session, context)
        return _authorization_error(request, error)
    except FinancialEventVersionMismatch:
        return _version_error(request)
    except FinancialEventStateConflict:
        return _conflict(
            request,
            "INVALID_STATE_TRANSITION",
            "Only an eligible own Pending submission can be edited.",
        )
    except InvalidFinanceCategory:
        return safe_error(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The selected category is incompatible with the financial event.",
            correlation_id=correlation_for(request),
        )
    response.headers["ETag"] = f'"v{record.version}"'
    return FinancialEventEnvelope(data=_representation(record))


@router.post("", response_model=FinancialEventEnvelope, status_code=status.HTTP_201_CREATED)
async def create_financial_event(
    workspace_id: UUID,
    payload: FinancialEventCreateRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    idempotency_key: IdempotencyHeader,
) -> FinancialEventEnvelope | Response:
    del browser
    try:
        context = await _resolve_context(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
        metadata = FinanceCommandMetadata(
            operation_id=payload.operation_id,
            operation=OperationCode("CREATE_FINANCIAL_EVENT"),
            idempotency_key=IdempotencyKey(idempotency_key),
            request_fingerprint=_fingerprint(payload),
            required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
        )
        record, replayed = await _service(session).create_manual(
            context,
            command=ManualFinancialEventCommand(
                event_kind=payload.event_kind,
                activity_classification=payload.activity_classification,
                occurred_on=payload.occurred_on,
                finance_category_id=payload.finance_category_id,
                amount=payload.money.amount,
                currency_code=payload.money.currency_code,
                payment_method=payload.payment_method,
                counterparty=payload.counterparty,
                reference=payload.reference,
                notes=payload.notes,
            ),
            metadata=metadata,
        )
    except AuthorizationDenied as error:
        if "context" in locals() and error.code is DenialCode.PERMISSION_DENIED:
            await _audit_permission_denial(session, context)
        return _authorization_error(request, error)
    except IdempotencyKeyReused:
        return _conflict(
            request,
            "IDEMPOTENCY_KEY_REUSED",
            "The idempotency key is already bound to another request.",
        )
    except (FinancialEventInProgress, FinancialEventRecoveryRequired):
        return _conflict(
            request,
            "CONFLICT",
            "The financial event command is already being processed.",
        )
    except FinancialEventReplayUnavailable:
        return _conflict(
            request,
            "CONFLICT",
            "The stored command outcome cannot be replayed safely.",
        )
    except InvalidFinanceCategory:
        return safe_error(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The selected category is incompatible with the financial event.",
            correlation_id=correlation_for(request),
        )

    location = f"/api/v1/workspaces/{workspace_id}/financial-events/{record.id}"
    response.headers["Location"] = location
    response.headers["Idempotency-Replayed"] = "true" if replayed else "false"
    return FinancialEventEnvelope(data=_representation(record))


async def _audit_permission_denial(session: AsyncSession, context: AuthorizationContext) -> None:
    await _audit_access_denial(session, context, AuditReason.PERMISSION_DENIED)


async def _audit_access_denial(
    session: AsyncSession, context: AuthorizationContext, reason: AuditReason
) -> None:
    await SqlAlchemyAuditWriter(session).append(
        AuditEventIntent(
            scope=AuditScope.WORKSPACE,
            workspace_id=context.workspace_id,
            actor=AuditActor.user(context.actor_account_id, context.membership_id),
            action=AuditAction.FINANCE_ACCESS_DENIED,
            module=AuditModule.HOUSEHOLD_FINANCE,
            result=AuditResult.DENIED,
            correlation_id=context.correlation_id,
            resource_type=AuditResourceType.FINANCIAL_EVENT,
            reason=reason,
            source=AuditSource.API,
            context=AuditContext.FINANCE_ENTRY,
        )
    )


def _authorization_error(request: Request, error: AuthorizationDenied) -> Response:
    not_found = error.code is DenialCode.RESOURCE_NOT_FOUND
    return safe_error(
        status_code=404 if not_found else 403,
        code="RESOURCE_NOT_FOUND" if not_found else "PERMISSION_DENIED",
        message=(
            "The requested resource was not found."
            if not_found
            else "The operation is not permitted."
        ),
        correlation_id=correlation_for(request),
    )


def _conflict(request: Request, code: str, message: str) -> Response:
    return safe_error(
        status_code=409,
        code=code,
        message=message,
        correlation_id=correlation_for(request),
    )


def _version_error(request: Request) -> Response:
    return safe_error(
        status_code=412,
        code="VERSION_MISMATCH",
        message="The resource version is no longer current.",
        correlation_id=correlation_for(request),
    )


def _query_error(request: Request, code: str, message: str) -> Response:
    return safe_error(
        status_code=400,
        code=code,
        message=message,
        correlation_id=correlation_for(request),
    )
