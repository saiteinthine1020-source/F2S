export type SupportedRole = "ADMIN" | "CONTRIBUTOR" | "ADVISOR";
export type WorkspaceType =
  "HOUSEHOLD" | "FARM" | "MICROBUSINESS" | "SMALL_BUSINESS" | "COMBINED" | "CUSTOM";

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
  readonly preferred_language: "en" | "ja" | "my" | "shn";
  readonly version: number;
}

export interface WorkspaceMembership {
  readonly membership_id: string;
  readonly role: SupportedRole;
  readonly workspace: WorkspaceReference;
}

export interface ModuleSetting {
  readonly code: string;
  readonly enabled: boolean;
  readonly version: number;
}

export interface SelectedWorkspace {
  readonly workspace: WorkspaceReference;
  readonly modules: readonly ModuleSetting[];
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
