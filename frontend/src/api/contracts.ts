export type SupportedRole = "ADMIN" | "CONTRIBUTOR" | "ADVISOR";
export type MemberRole = Exclude<SupportedRole, "ADMIN">;
export type SupportedLanguage = "en" | "ja" | "my" | "shn";
export type WorkspaceType =
  "HOUSEHOLD" | "FARM" | "MICROBUSINESS" | "SMALL_BUSINESS" | "COMBINED" | "CUSTOM";
export type ModuleCode = "HOUSEHOLD_FINANCE" | "FARMING_INVESTMENTS";
export type MembershipStatus = "PENDING" | "ACTIVE" | "SUSPENDED" | "REVOKED";
export type OwnershipTransferStatus =
  "INITIATED" | "CONFIRMED" | "CANCELLED" | "EXPIRED" | "COMPLETED";

export interface SessionRepresentation {
  readonly access_token: string;
  readonly csrf_token: string;
  readonly token_type: "Bearer";
  readonly access_expires_at: string;
  readonly absolute_expires_at: string;
}

export interface WorkspaceReference {
  readonly id: string;
  readonly name: string;
  readonly type: WorkspaceType;
  readonly base_currency_code: string;
  readonly timezone: string;
  readonly preferred_language: SupportedLanguage;
  readonly version: number;
}

export interface WorkspaceMembership {
  readonly membership_id: string;
  readonly role: SupportedRole;
  readonly workspace: WorkspaceReference;
}

export interface ModuleSetting {
  readonly code: ModuleCode;
  readonly enabled: boolean;
  readonly version: number;
}

export interface WorkspaceAdministration {
  readonly description: string | null;
  readonly address: string | null;
  readonly business_category_code: string | null;
  readonly farm_type_code: string | null;
}

export interface SelectedWorkspace {
  readonly workspace: WorkspaceReference;
  readonly modules: readonly ModuleSetting[];
  readonly administration?: WorkspaceAdministration;
}

export interface MemberRecord {
  readonly id: string;
  readonly email: string;
  readonly display_name: string;
  readonly role: SupportedRole;
  readonly status: MembershipStatus;
  readonly account_status: string;
  readonly preferred_language: SupportedLanguage;
  readonly timezone: string;
  readonly last_login_at: string | null;
  readonly created_at: string;
  readonly version: number;
}

export interface OwnershipTransfer {
  readonly id: string;
  readonly workspace_id: string;
  readonly current_owner_membership_id: string;
  readonly target_membership_id: string;
  readonly former_owner_role: MemberRole;
  readonly status: OwnershipTransferStatus;
  readonly expires_at: string;
  readonly version: number;
}

export interface BootstrapCommand {
  readonly display_name: string;
  readonly email: string;
  readonly password: string;
  readonly account_language: "en" | "ja" | "my" | "shn";
  readonly account_timezone: string;
  readonly workspace_name: string;
  readonly workspace_type: WorkspaceType;
  readonly base_currency_code: string;
  readonly workspace_language: "en" | "ja" | "my" | "shn";
  readonly workspace_timezone: string;
}

export interface SessionView {
  readonly accessExpiresAt: string;
  readonly absoluteExpiresAt: string;
}

export interface SelectedWorkspaceView {
  readonly membership: WorkspaceMembership;
  readonly details: SelectedWorkspace;
}
