"""Canonical synthetic two-workspace fixture for the Phase 1 release gate."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import text

from app.core.config import Settings
from app.infrastructure.database.session import create_database_engine


@dataclass(frozen=True, slots=True)
class PhaseOneWorkspaceFixture:
    """Handles for every Phase 1 role/state and foreign-ID substitution."""

    workspace_a_id: UUID
    workspace_b_id: UUID
    admin_a_user_id: UUID
    admin_a_membership_id: UUID
    admin_b_user_id: UUID
    admin_b_membership_id: UUID
    multi_user_id: UUID
    contributor_a_membership_id: UUID
    advisor_b_membership_id: UUID
    advisor_a_user_id: UUID
    advisor_a_membership_id: UUID
    pending_user_id: UUID
    pending_membership_id: UUID
    suspended_user_id: UUID
    suspended_membership_id: UUID
    revoked_user_id: UUID
    revoked_membership_id: UUID
    module_a_id: UUID
    module_b_id: UUID

    @property
    def foreign_membership_id(self) -> UUID:
        return self.admin_b_membership_id

    @property
    def foreign_module_id(self) -> UUID:
        return self.module_b_id


async def seed_phase_one_workspaces(settings: Settings) -> PhaseOneWorkspaceFixture:
    """Seed all Phase 1 roles/states across two isolated synthetic workspaces."""
    ids = [uuid4() for _ in range(19)]
    fixture = PhaseOneWorkspaceFixture(*ids)
    suffix = uuid4().hex
    users = (
        (fixture.admin_a_user_id, f"admin-a-{suffix}@example.invalid", "Admin A"),
        (fixture.admin_b_user_id, f"admin-b-{suffix}@example.invalid", "Admin B"),
        (fixture.multi_user_id, f"multi-{suffix}@example.invalid", "Multi User"),
        (fixture.advisor_a_user_id, f"advisor-{suffix}@example.invalid", "Advisor A"),
        (fixture.pending_user_id, f"pending-{suffix}@example.invalid", "Pending"),
        (fixture.suspended_user_id, f"suspended-{suffix}@example.invalid", "Suspended"),
        (fixture.revoked_user_id, f"revoked-{suffix}@example.invalid", "Revoked"),
    )
    memberships = (
        (
            fixture.admin_a_membership_id,
            fixture.workspace_a_id,
            fixture.admin_a_user_id,
            "ADMIN",
            "ACTIVE",
        ),
        (
            fixture.admin_b_membership_id,
            fixture.workspace_b_id,
            fixture.admin_b_user_id,
            "ADMIN",
            "ACTIVE",
        ),
        (
            fixture.contributor_a_membership_id,
            fixture.workspace_a_id,
            fixture.multi_user_id,
            "CONTRIBUTOR",
            "ACTIVE",
        ),
        (
            fixture.advisor_b_membership_id,
            fixture.workspace_b_id,
            fixture.multi_user_id,
            "ADVISOR",
            "ACTIVE",
        ),
        (
            fixture.advisor_a_membership_id,
            fixture.workspace_a_id,
            fixture.advisor_a_user_id,
            "ADVISOR",
            "ACTIVE",
        ),
        (
            fixture.pending_membership_id,
            fixture.workspace_a_id,
            fixture.pending_user_id,
            "CONTRIBUTOR",
            "PENDING",
        ),
        (
            fixture.suspended_membership_id,
            fixture.workspace_a_id,
            fixture.suspended_user_id,
            "ADVISOR",
            "SUSPENDED",
        ),
        (
            fixture.revoked_membership_id,
            fixture.workspace_a_id,
            fixture.revoked_user_id,
            "CONTRIBUTOR",
            "REVOKED",
        ),
    )
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            for user_id, email, display_name in users:
                await connection.execute(
                    text(
                        "INSERT INTO user_accounts "
                        "(id, normalized_email, display_name, status, "
                        "preferred_language, timezone) VALUES "
                        "(:id, :email, :name, 'ACTIVE', 'en', 'UTC')"
                    ),
                    {"id": user_id, "email": email, "name": display_name},
                )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, name, type, base_currency_code, timezone, preferred_language, "
                    "description, address, owner_membership_id, owner_role, "
                    "owner_membership_status, status) VALUES "
                    "(:wa, 'Workspace A', 'HOUSEHOLD', 'USD', 'UTC', 'en', "
                    "'Restricted A', 'Address A', :oa, 'ADMIN', 'ACTIVE', 'ACTIVE'), "
                    "(:wb, 'Workspace B', 'FARM', 'JPY', 'Asia/Tokyo', 'ja', "
                    "'Restricted B', 'Address B', :ob, 'ADMIN', 'ACTIVE', 'ACTIVE')"
                ),
                {
                    "wa": fixture.workspace_a_id,
                    "wb": fixture.workspace_b_id,
                    "oa": fixture.admin_a_membership_id,
                    "ob": fixture.admin_b_membership_id,
                },
            )
            for membership_id, workspace_id, user_id, role, status in memberships:
                await connection.execute(
                    text(
                        "INSERT INTO workspace_memberships "
                        "(id, workspace_id, user_account_id, role, status) "
                        "VALUES (:id, :workspace, :user, :role, :status)"
                    ),
                    {
                        "id": membership_id,
                        "workspace": workspace_id,
                        "user": user_id,
                        "role": role,
                        "status": status,
                    },
                )
            await connection.execute(
                text(
                    "INSERT INTO workspace_modules "
                    "(id, workspace_id, module_code, enabled) VALUES "
                    "(:ma, :wa, 'HOUSEHOLD_FINANCE', true), "
                    "(:mb, :wb, 'FARMING_INVESTMENTS', false)"
                ),
                {
                    "ma": fixture.module_a_id,
                    "wa": fixture.workspace_a_id,
                    "mb": fixture.module_b_id,
                    "wb": fixture.workspace_b_id,
                },
            )
    finally:
        await engine.dispose()
    return fixture
