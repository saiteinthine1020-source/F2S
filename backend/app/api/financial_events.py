"""Strict workspace-scoped manual income and expense creation API."""

import json
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import correlation_for, safe_error
from app.api.security import AuthenticatedAccountId
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
    FinanceCommandMetadata,
    FinancialEventCommandService,
    FinancialEventInProgress,
    FinancialEventKind,
    FinancialEventRecord,
    FinancialEventRecoveryRequired,
    FinancialEventReplayUnavailable,
    InvalidFinanceCategory,
    ManualFinancialEventCommand,
    PaymentMethod,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
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
StrictAmount = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=64)]
StrictCurrency = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[A-Z]{3}$"),
]


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


def _service(session: AsyncSession) -> FinancialEventCommandService:
    return FinancialEventCommandService(
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
            reason=AuditReason.PERMISSION_DENIED,
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
