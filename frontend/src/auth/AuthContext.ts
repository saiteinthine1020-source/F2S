import { createContext, useContext } from "react";

import type {
  SelectedWorkspace,
  SelectedWorkspaceView,
  SessionView,
  WorkspaceMembership,
} from "../api/contracts";

export type SessionEndReason = "expired" | "network" | "ownership" | null;

export type AuthState =
  | { readonly status: "checking" }
  | { readonly status: "unavailable" }
  | { readonly status: "bootstrap" }
  | { readonly status: "anonymous"; readonly reason: SessionEndReason }
  | {
      readonly status: "selecting-workspace";
      readonly session: SessionView;
      readonly memberships: readonly WorkspaceMembership[];
      readonly error: boolean;
    }
  | {
      readonly status: "authenticated";
      readonly session: SessionView;
      readonly memberships: readonly WorkspaceMembership[];
      readonly selected: SelectedWorkspaceView;
    };

export interface AuthController {
  readonly state: AuthState;
  retryStartup(): Promise<void>;
  signIn(email: string, password: string): Promise<void>;
  signOut(scope: "CURRENT" | "ALL"): Promise<void>;
  selectWorkspace(workspaceId: string): Promise<void>;
  beginWorkspaceSwitch(): void;
  acceptWorkspaceUpdate(details: SelectedWorkspace): void;
  endOwnershipTransferSession(): void;
  markBootstrapComplete(): void;
}

export const AuthContext = createContext<AuthController | null>(null);

export function useAuth(): AuthController {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("AUTH_CONTEXT_UNAVAILABLE");
  }
  return context;
}
