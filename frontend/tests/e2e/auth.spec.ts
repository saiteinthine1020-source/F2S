import { expect, test, type Page, type Route } from "@playwright/test";

const workspaceId = "11111111-1111-4111-8111-111111111111";
const ownerMembershipId = "22222222-2222-4222-8222-222222222222";
const candidateMembershipId = "33333333-3333-4333-8333-333333333333";
const transferId = "44444444-4444-4444-8444-444444444444";

async function fulfillJson(route: Route, body: object, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: { "Cache-Control": "no-store", "X-Correlation-ID": workspaceId },
    body: JSON.stringify(body),
  });
}

async function mockApi(page: Page, bootstrapAvailable = false) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/setup/bootstrap")) {
      await fulfillJson(
        route,
        request.method() === "GET"
          ? { data: { available: bootstrapAvailable } }
          : { data: { status: "COMPLETE" } },
        request.method() === "GET" ? 200 : 201,
      );
      return;
    }
    if (path.endsWith("/auth/login")) {
      await fulfillJson(route, {
        data: {
          access_token: "a".repeat(48),
          csrf_token: "c".repeat(48),
          token_type: "Bearer",
          access_expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
          absolute_expires_at: new Date(Date.now() + 30 * 24 * 60 * 60_000).toISOString(),
        },
      });
      return;
    }
    if (path.endsWith("/me/workspaces")) {
      await fulfillJson(route, {
        data: [
          {
            membership_id: ownerMembershipId,
            role: "ADMIN",
            workspace: {
              id: workspaceId,
              name: "Synthetic household",
              type: "HOUSEHOLD",
              base_currency_code: "JPY",
              timezone: "Asia/Tokyo",
              preferred_language: "en",
              version: 1,
            },
          },
        ],
      });
      return;
    }
    if (path.endsWith(`/workspaces/${workspaceId}`)) {
      await fulfillJson(route, {
        data: {
          workspace: {
            id: workspaceId,
            name: "Synthetic household",
            type: "HOUSEHOLD",
            base_currency_code: "JPY",
            timezone: "Asia/Tokyo",
            preferred_language: "en",
            version: 1,
          },
          modules: [],
        },
      });
      return;
    }
    if (path.endsWith(`/workspaces/${workspaceId}/members`) && request.method() === "GET") {
      const createdAt = new Date().toISOString();
      await fulfillJson(route, {
        data: [
          {
            id: ownerMembershipId,
            email: "admin@example.invalid",
            display_name: "Synthetic Admin",
            role: "ADMIN",
            status: "ACTIVE",
            account_status: "ACTIVE",
            preferred_language: "en",
            timezone: "Asia/Tokyo",
            last_login_at: null,
            created_at: createdAt,
            version: 1,
          },
          {
            id: candidateMembershipId,
            email: "candidate@example.invalid",
            display_name: "Synthetic Candidate",
            role: "CONTRIBUTOR",
            status: "ACTIVE",
            account_status: "ACTIVE",
            preferred_language: "en",
            timezone: "Asia/Tokyo",
            last_login_at: null,
            created_at: createdAt,
            version: 2,
          },
        ],
      });
      return;
    }
    if (path.endsWith(`/workspaces/${workspaceId}/ownership-transfers`)) {
      await fulfillJson(
        route,
        {
          data: {
            id: transferId,
            workspace_id: workspaceId,
            current_owner_membership_id: ownerMembershipId,
            target_membership_id: candidateMembershipId,
            former_owner_role: "CONTRIBUTOR",
            status: "INITIATED",
            expires_at: new Date(Date.now() + 30 * 60_000).toISOString(),
            version: 1,
          },
        },
        201,
      );
      return;
    }
    if (path.endsWith(`/workspaces/${workspaceId}/ownership-transfers/${transferId}/cancel`)) {
      await route.fulfill({ status: 204, headers: { "Cache-Control": "no-store" } });
      return;
    }
    if (path.endsWith("/auth/recovery/request")) {
      await fulfillJson(route, { data: { status: "ACCEPTED" } }, 202);
      return;
    }
    if (path.endsWith("/auth/activate")) {
      await fulfillJson(route, { data: { status: "ACTIVE" } });
      return;
    }
    if (path.endsWith("/auth/password/change") || path.endsWith("/auth/logout")) {
      await route.fulfill({ status: 204, headers: { "Cache-Control": "no-store" } });
      return;
    }
    await fulfillJson(
      route,
      { error: { code: "REQUEST_FAILED", correlation_id: workspaceId } },
      500,
    );
  });
}

test("anonymous deep links reveal no protected workspace content", async ({ page }) => {
  await mockApi(page);
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByText("Synthetic household")).toHaveCount(0);
});

test("critical login and protected-shell flow is keyboard accessible", async ({ page }) => {
  await mockApi(page);
  await page.goto("/login");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.getByLabel("Email address").fill("admin@example.invalid");
  await page.getByLabel("Password").fill("synthetic-password-value");
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await expect(page.getByRole("heading", { name: "Workspace access is ready" })).toBeVisible();
  await expect(page.getByText("Synthetic household")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Workspace navigation" })).toContainText(
    "Reports",
  );
});

test("recovery response does not disclose account existence", async ({ page }) => {
  await mockApi(page);
  await page.goto("/recovery");
  await page.getByLabel("Email address").fill("unknown@example.invalid");
  await page.getByRole("button", { name: "Request recovery" }).click();
  await expect(page.getByRole("status")).toContainText("If recovery is available");
  await expect(page.getByText("unknown@example.invalid")).toHaveCount(0);
});

test("one-time bootstrap collects the complete account and workspace contract", async ({
  page,
}) => {
  await mockApi(page, true);
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/setup");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.getByLabel("Your name").fill("Synthetic Admin");
  await page.getByLabel("Email address").fill("admin@example.invalid");
  await page.getByLabel("Password").fill("synthetic-password-value");
  await page.getByLabel("Workspace name").fill("Synthetic household");
  await page.getByRole("button", { name: "Complete secure setup" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("activation evidence remains in a form field and never enters the URL", async ({ page }) => {
  await mockApi(page);
  await page.goto("/activate");
  const evidence = "e".repeat(48);
  await page.getByLabel("Activation code").fill(evidence);
  await page
    .getByLabel("New password, if this is your first activation")
    .fill("synthetic-password-value");
  await page.getByRole("button", { name: "Activate access" }).click();
  await expect(page.getByRole("status")).toContainText("Activation is complete");
  await expect(page).toHaveURL(/\/activate$/u);
  await expect(page).not.toHaveURL(new RegExp(evidence, "u"));
});

test("password change and logout complete from the protected shell", async ({ page }) => {
  await mockApi(page);
  await page.goto("/login");
  await page.getByLabel("Email address").fill("admin@example.invalid");
  await page.getByLabel("Password").fill("synthetic-password-value");
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await page.getByRole("link", { name: "Change password" }).click();
  await page.getByLabel("Current password").fill("synthetic-password-value");
  await page.getByLabel("New password").fill("different-synthetic-password");
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByRole("status")).toContainText("other sessions were revoked");
  await page.getByRole("button", { name: "Sign out on this device" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByText("Synthetic household")).toHaveCount(0);
});

test("Admin ownership transfer requires consequences and reauthentication without URL evidence", async ({
  page,
}) => {
  await mockApi(page);
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/login");
  await page.getByLabel("Email address").fill("admin@example.invalid");
  await page.getByLabel("Password").fill("synthetic-password-value");
  await page.getByRole("button", { name: "Sign in securely" }).click();
  await page.getByRole("link", { name: "Administration" }).click();
  await page.getByRole("link", { name: /Transfer workspace ownership/u }).click();

  const password = "ownership-reauthentication-value";
  await page.getByLabel("New owner").selectOption(candidateMembershipId);
  await page.getByLabel("Current password").fill(password);
  await page.getByLabel(/I understand the selected member becomes the sole Admin/u).check();
  await page.getByRole("button", { name: "Review ownership transfer" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Initiate ownership transfer?");
  await expect(page).not.toHaveURL(new RegExp(password, "u"));
  await page.getByRole("button", { name: "Initiate transfer" }).click();

  await expect(page.getByText("Waiting for confirmation").first()).toBeVisible();
  await expect(page.getByText(transferId)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.getByRole("button", { name: "Cancel pending transfer" }).click();
  await expect(page.getByText("Cancelled").first()).toBeVisible();
});
