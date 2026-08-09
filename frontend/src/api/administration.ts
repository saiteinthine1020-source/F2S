import type { ApiClient } from "./client";
import type {
  MemberRecord,
  MemberRole,
  ModuleCode,
  OwnershipTransfer,
  SelectedWorkspace,
  SupportedLanguage,
  WorkspaceType,
} from "./contracts";

interface Envelope<T> {
  readonly data: T;
}

export interface WorkspaceSettingsCommand {
  readonly name: string;
  readonly type: WorkspaceType;
  readonly base_currency_code: string;
  readonly timezone: string;
  readonly preferred_language: SupportedLanguage;
  readonly description: string | null;
  readonly address: string | null;
  readonly business_category_code: string | null;
  readonly farm_type_code: string | null;
  readonly modules: readonly { readonly code: ModuleCode; readonly enabled: boolean }[];
}

export interface ProvisionMemberCommand {
  readonly email: string;
  readonly display_name: string;
  readonly role: MemberRole;
  readonly preferred_language: SupportedLanguage;
  readonly timezone: string;
}

function mutation(
  method: "POST" | "PATCH" | "DELETE",
  body: object,
  version?: number,
): RequestInit {
  const headers = new Headers();
  if (version !== undefined) headers.set("If-Match", `"v${version}"`);
  return { method, headers, body: JSON.stringify(body) };
}

export async function updateWorkspaceSettings(
  client: ApiClient,
  workspaceId: string,
  version: number,
  command: WorkspaceSettingsCommand,
): Promise<SelectedWorkspace> {
  requireUuid(workspaceId);
  const response = await client.request<Envelope<SelectedWorkspace>>(
    `/workspaces/${workspaceId}`,
    mutation("PATCH", command, version),
    { csrf: true },
  );
  if (response.data.workspace.id !== workspaceId || response.data.workspace.version <= version) {
    throw new TypeError("WORKSPACE_UPDATE_RESPONSE_INVALID");
  }
  return response.data;
}

export async function listMembers(
  client: ApiClient,
  workspaceId: string,
): Promise<readonly MemberRecord[]> {
  requireUuid(workspaceId);
  const response = await client.request<Envelope<readonly MemberRecord[]>>(
    `/workspaces/${workspaceId}/members`,
  );
  if (!Array.isArray(response.data) || !response.data.every(isMemberRecord)) {
    throw new TypeError("MEMBER_LIST_RESPONSE_INVALID");
  }
  return response.data;
}

export async function provisionMember(
  client: ApiClient,
  workspaceId: string,
  command: ProvisionMemberCommand,
): Promise<void> {
  requireUuid(workspaceId);
  await client.request(`/workspaces/${workspaceId}/members`, mutation("POST", command), {
    csrf: true,
  });
}

export async function changeMemberRole(
  client: ApiClient,
  workspaceId: string,
  member: MemberRecord,
  role: MemberRole,
): Promise<MemberRecord> {
  return memberMutation(client, workspaceId, member, "PATCH", { role });
}

export async function suspendMember(
  client: ApiClient,
  workspaceId: string,
  member: MemberRecord,
): Promise<MemberRecord> {
  return memberMutation(client, workspaceId, member, "PATCH", { status: "SUSPENDED" });
}

export async function reactivateMember(
  client: ApiClient,
  workspaceId: string,
  member: MemberRecord,
): Promise<MemberRecord> {
  return memberMutation(client, workspaceId, member, "POST", {}, "reactivate");
}

export async function restartActivation(
  client: ApiClient,
  workspaceId: string,
  member: MemberRecord,
): Promise<void> {
  requireWorkspaceMember(workspaceId, member);
  await client.request(
    `/workspaces/${workspaceId}/members/${member.id}/activation/restart`,
    mutation("POST", {}, member.version),
    { csrf: true },
  );
}

export async function revokeMember(
  client: ApiClient,
  workspaceId: string,
  member: MemberRecord,
): Promise<void> {
  requireWorkspaceMember(workspaceId, member);
  await client.request(
    `/workspaces/${workspaceId}/members/${member.id}`,
    mutation("DELETE", {}, member.version),
    { csrf: true },
  );
}

async function memberMutation(
  client: ApiClient,
  workspaceId: string,
  member: MemberRecord,
  method: "POST" | "PATCH",
  body: object,
  command?: string,
): Promise<MemberRecord> {
  requireWorkspaceMember(workspaceId, member);
  const suffix = command === undefined ? "" : `/${command}`;
  const response = await client.request<Envelope<MemberRecord>>(
    `/workspaces/${workspaceId}/members/${member.id}${suffix}`,
    mutation(method, body, member.version),
    { csrf: true },
  );
  if (!isMemberRecord(response.data) || response.data.id !== member.id) {
    throw new TypeError("MEMBER_RESPONSE_INVALID");
  }
  return response.data;
}

export async function initiateOwnershipTransfer(
  client: ApiClient,
  workspaceId: string,
  targetMembershipId: string,
  formerOwnerRole: MemberRole,
  currentPassword: string,
): Promise<OwnershipTransfer> {
  requireUuid(workspaceId);
  requireUuid(targetMembershipId);
  const response = await client.request<Envelope<OwnershipTransfer>>(
    `/workspaces/${workspaceId}/ownership-transfers`,
    mutation("POST", {
      target_membership_id: targetMembershipId,
      former_owner_role: formerOwnerRole,
      current_password: currentPassword,
    }),
    { csrf: true },
  );
  return acceptTransfer(response.data, workspaceId);
}

export async function confirmOwnershipTransfer(
  client: ApiClient,
  workspaceId: string,
  transferId: string,
  value: string,
): Promise<OwnershipTransfer> {
  requireUuid(workspaceId);
  requireUuid(transferId);
  const response = await client.request<Envelope<OwnershipTransfer>>(
    `/workspaces/${workspaceId}/ownership-transfers/${transferId}/confirm`,
    mutation("POST", { value }),
    { csrf: true },
  );
  return acceptTransfer(response.data, workspaceId);
}

export async function cancelOwnershipTransfer(
  client: ApiClient,
  transfer: OwnershipTransfer,
): Promise<void> {
  requireUuid(transfer.workspace_id);
  requireUuid(transfer.id);
  await client.request(
    `/workspaces/${transfer.workspace_id}/ownership-transfers/${transfer.id}/cancel`,
    mutation("POST", {}, transfer.version),
    { csrf: true },
  );
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const ROLES = new Set(["ADMIN", "CONTRIBUTOR", "ADVISOR"]);
const STATUSES = new Set(["PENDING", "ACTIVE", "SUSPENDED", "REVOKED"]);
const TRANSFER_STATUSES = new Set(["INITIATED", "CONFIRMED", "CANCELLED", "EXPIRED", "COMPLETED"]);

function requireUuid(value: string): void {
  if (!UUID.test(value)) throw new TypeError("RESOURCE_ID_INVALID");
}

function requireWorkspaceMember(workspaceId: string, member: MemberRecord): void {
  requireUuid(workspaceId);
  requireUuid(member.id);
  if (!Number.isInteger(member.version) || member.version < 1) {
    throw new TypeError("MEMBER_VERSION_INVALID");
  }
}

function isMemberRecord(value: unknown): value is MemberRecord {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Partial<MemberRecord>;
  return (
    typeof item.id === "string" &&
    UUID.test(item.id) &&
    typeof item.email === "string" &&
    typeof item.display_name === "string" &&
    typeof item.role === "string" &&
    ROLES.has(item.role) &&
    typeof item.status === "string" &&
    STATUSES.has(item.status) &&
    typeof item.version === "number" &&
    Number.isInteger(item.version) &&
    item.version > 0
  );
}

function acceptTransfer(value: OwnershipTransfer, workspaceId: string): OwnershipTransfer {
  if (
    !UUID.test(value.id) ||
    value.workspace_id !== workspaceId ||
    !TRANSFER_STATUSES.has(value.status) ||
    !Number.isInteger(value.version) ||
    value.version < 1 ||
    !Number.isFinite(Date.parse(value.expires_at))
  ) {
    throw new TypeError("OWNERSHIP_TRANSFER_RESPONSE_INVALID");
  }
  return value;
}
