import type { ApiClient } from "./client";
import type {
  BootstrapCommand,
  SelectedWorkspace,
  SessionRepresentation,
  SessionView,
  WorkspaceMembership,
} from "./contracts";

interface Envelope<T> {
  readonly data: T;
}

function json(method: "POST", body: object): RequestInit {
  return { method, body: JSON.stringify(body) };
}

function acceptSession(client: ApiClient, session: SessionRepresentation): SessionView {
  const accessExpiresAt = Date.parse(session.access_expires_at);
  const absoluteExpiresAt = Date.parse(session.absolute_expires_at);
  if (
    session.token_type !== "Bearer" ||
    !Number.isFinite(accessExpiresAt) ||
    !Number.isFinite(absoluteExpiresAt) ||
    accessExpiresAt <= Date.now() ||
    absoluteExpiresAt < accessExpiresAt
  ) {
    client.setSessionCredentials(null);
    throw new TypeError("SESSION_RESPONSE_INVALID");
  }
  client.setSessionCredentials({
    accessToken: session.access_token,
    csrfToken: session.csrf_token,
  });
  return {
    accessExpiresAt: session.access_expires_at,
    absoluteExpiresAt: session.absolute_expires_at,
  };
}

export async function bootstrapAvailable(client: ApiClient): Promise<boolean> {
  const response = await client.request<Envelope<{ readonly available: boolean }>>(
    "/setup/bootstrap",
    undefined,
    { authorization: "omit" },
  );
  return response.data.available;
}

export async function completeBootstrap(client: ApiClient, command: BootstrapCommand) {
  await client.request<Envelope<{ readonly status: "COMPLETE" }>>(
    "/setup/bootstrap",
    json("POST", command),
    { authorization: "omit" },
  );
}

export async function activateAccount(client: ApiClient, value: string, password: string | null) {
  await client.request(
    "/auth/activate",
    json("POST", password === null ? { value } : { value, password }),
    { authorization: "omit" },
  );
}

export async function login(client: ApiClient, email: string, password: string) {
  const response = await client.request<Envelope<SessionRepresentation>>(
    "/auth/login",
    json("POST", { email, password }),
    { authorization: "omit" },
  );
  return acceptSession(client, response.data);
}

export async function refreshSession(client: ApiClient) {
  const response = await client.request<Envelope<SessionRepresentation>>(
    "/auth/refresh",
    json("POST", {}),
    { authorization: "omit", csrf: true },
  );
  return acceptSession(client, response.data);
}

export async function logout(client: ApiClient, scope: "CURRENT" | "ALL") {
  try {
    await client.request("/auth/logout", json("POST", { scope }), {
      authorization: "omit",
      csrf: true,
    });
  } finally {
    client.setSessionCredentials(null);
  }
}

export async function changePassword(
  client: ApiClient,
  currentPassword: string,
  newPassword: string,
) {
  await client.request(
    "/auth/password/change",
    json("POST", { current_password: currentPassword, new_password: newPassword }),
  );
}

export async function requestRecovery(client: ApiClient, email: string) {
  await client.request("/auth/recovery/request", json("POST", { email }), {
    authorization: "omit",
  });
}

export async function confirmRecovery(client: ApiClient, value: string, newPassword: string) {
  await client.request(
    "/auth/recovery/confirm",
    json("POST", { value, new_password: newPassword }),
    { authorization: "omit" },
  );
}

export async function listWorkspaces(client: ApiClient): Promise<readonly WorkspaceMembership[]> {
  const response = await client.request<Envelope<readonly WorkspaceMembership[]>>("/me/workspaces");
  if (!Array.isArray(response.data) || !response.data.every(isWorkspaceMembership)) {
    throw new TypeError("WORKSPACE_DIRECTORY_INVALID");
  }
  return response.data;
}

export async function getWorkspace(client: ApiClient, id: string): Promise<SelectedWorkspace> {
  if (!UUID.test(id)) {
    throw new TypeError("WORKSPACE_ID_INVALID");
  }
  const response = await client.request<Envelope<SelectedWorkspace>>(`/workspaces/${id}`);
  return response.data;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const ROLES = new Set(["ADMIN", "CONTRIBUTOR", "ADVISOR"]);

function isWorkspaceMembership(value: unknown): value is WorkspaceMembership {
  if (typeof value !== "object" || value === null || !("workspace" in value)) {
    return false;
  }
  const candidate = value as {
    readonly membership_id?: unknown;
    readonly role?: unknown;
    readonly workspace?: unknown;
  };
  if (
    typeof candidate.membership_id !== "string" ||
    !UUID.test(candidate.membership_id) ||
    typeof candidate.role !== "string" ||
    !ROLES.has(candidate.role) ||
    typeof candidate.workspace !== "object" ||
    candidate.workspace === null
  ) {
    return false;
  }
  const workspace = candidate.workspace as { readonly id?: unknown; readonly name?: unknown };
  return (
    typeof workspace.id === "string" &&
    UUID.test(workspace.id) &&
    typeof workspace.name === "string"
  );
}
