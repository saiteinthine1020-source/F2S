import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type PropsWithChildren, useMemo, useState } from "react";

import { createApiClient } from "../api/client";
import type { RuntimeConfig } from "../config/runtime";
import { ApiClientContext } from "./ApiClientContext";

interface AppProvidersProps extends PropsWithChildren {
  readonly config: RuntimeConfig;
}

export function AppProviders({ children, config }: AppProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
            staleTime: 0,
            gcTime: 0,
          },
          mutations: { retry: false },
        },
      }),
  );
  const apiClient = useMemo(() => createApiClient(config), [config]);

  return (
    <ApiClientContext.Provider value={apiClient}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ApiClientContext.Provider>
  );
}
