import { useQueryClient } from "@tanstack/react-query";
import { type PropsWithChildren, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import {
  bootstrapAvailable,
  getWorkspace,
  listWorkspaces,
  login,
  logout,
  refreshSession,
} from "../api/auth";
import type { SessionView, WorkspaceMembership } from "../api/contracts";
import { useApiClient } from "../app/ApiClientContext";
import { AuthContext, type AuthState, type SessionEndReason } from "./AuthContext";

const REFRESH_EARLY_MS = 60_000;
const MINIMUM_REFRESH_DELAY_MS = 1_000;

export function AuthProvider({ children }: PropsWithChildren) {
  const client = useApiClient();
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({ status: "checking" });
  const refreshInFlight = useRef<Promise<void> | null>(null);

  const endSession = useCallback(
    (reason: SessionEndReason) => {
      client.setSessionCredentials(null);
      queryClient.clear();
      setState({ status: "anonymous", reason });
    },
    [client, queryClient],
  );

  const select = useCallback(
    async (
      workspaceId: string,
      session: SessionView,
      memberships: readonly WorkspaceMembership[],
    ) => {
      const membership = memberships.find((item) => item.workspace.id === workspaceId);
      if (membership === undefined) {
        throw new TypeError("WORKSPACE_SELECTION_INVALID");
      }
      queryClient.clear();
      setState({ status: "selecting-workspace", session, memberships, error: false });
      try {
        const details = await getWorkspace(client, workspaceId);
        if (details.workspace.id !== membership.workspace.id) {
          throw new TypeError("WORKSPACE_RESPONSE_INVALID");
        }
        setState({
          status: "authenticated",
          session,
          memberships,
          selected: { membership, details },
        });
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          endSession("expired");
          return;
        }
        setState({ status: "selecting-workspace", session, memberships, error: true });
        throw error;
      }
    },
    [client, endSession, queryClient],
  );

  const establishSession = useCallback(
    async (session: SessionView) => {
      const memberships = await listWorkspaces(client);
      if (memberships.length === 1) {
        const onlyMembership = memberships[0];
        if (onlyMembership === undefined) {
          throw new TypeError("WORKSPACE_DIRECTORY_INVALID");
        }
        await select(onlyMembership.workspace.id, session, memberships);
        return;
      }
      setState({ status: "selecting-workspace", session, memberships, error: false });
    },
    [client, select],
  );

  const initialise = useCallback(async () => {
    client.setSessionCredentials(null);
    queryClient.clear();
    setState({ status: "checking" });
    try {
      setState(
        (await bootstrapAvailable(client))
          ? { status: "bootstrap" }
          : { status: "anonymous", reason: null },
      );
    } catch {
      setState({ status: "unavailable" });
    }
  }, [client, queryClient]);

  useEffect(() => {
    queueMicrotask(() => void initialise());
  }, [initialise]);

  useEffect(() => {
    client.setUnauthorizedHandler(() => endSession("expired"));
    return () => client.setUnauthorizedHandler(null);
  }, [client, endSession]);

  useEffect(() => {
    if (state.status !== "authenticated" && state.status !== "selecting-workspace") {
      return;
    }
    const delay = Math.max(
      MINIMUM_REFRESH_DELAY_MS,
      Date.parse(state.session.accessExpiresAt) - Date.now() - REFRESH_EARLY_MS,
    );
    const timer = window.setTimeout(() => {
      if (refreshInFlight.current !== null) {
        return;
      }
      refreshInFlight.current = refreshSession(client)
        .then(async (session) => {
          if (state.status === "authenticated") {
            setState({ ...state, session });
          } else {
            setState({ ...state, session });
          }
        })
        .catch((error: unknown) => {
          endSession(error instanceof ApiError && error.status === 401 ? "expired" : "network");
        })
        .finally(() => {
          refreshInFlight.current = null;
        });
    }, delay);
    return () => window.clearTimeout(timer);
  }, [client, endSession, state]);

  const controller = useMemo(
    () => ({
      state,
      retryStartup: initialise,
      async signIn(email: string, password: string) {
        try {
          await establishSession(await login(client, email, password));
        } catch (error) {
          client.setSessionCredentials(null);
          queryClient.clear();
          setState({ status: "anonymous", reason: null });
          throw error;
        }
      },
      async signOut(scope: "CURRENT" | "ALL") {
        try {
          await logout(client, scope);
        } catch {
          // Local protected state must still be destroyed when the network is unavailable.
        } finally {
          endSession(null);
        }
      },
      async selectWorkspace(workspaceId: string) {
        if (state.status !== "selecting-workspace" && state.status !== "authenticated") {
          throw new TypeError("WORKSPACE_SELECTION_UNAVAILABLE");
        }
        await select(workspaceId, state.session, state.memberships);
      },
      beginWorkspaceSwitch() {
        if (state.status !== "authenticated") {
          return;
        }
        queryClient.clear();
        setState({
          status: "selecting-workspace",
          session: state.session,
          memberships: state.memberships,
          error: false,
        });
      },
      markBootstrapComplete() {
        client.setSessionCredentials(null);
        setState({ status: "anonymous", reason: null });
      },
    }),
    [client, endSession, establishSession, initialise, queryClient, select, state],
  );

  return <AuthContext.Provider value={controller}>{children}</AuthContext.Provider>;
}
