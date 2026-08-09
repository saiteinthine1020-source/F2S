export const en = {
  translation: {
    app: {
      name: "F2S",
    },
    accessibility: {
      skipToMain: "Skip to main content",
    },
    foundation: {
      eyebrow: "Secure workspace foundation",
      title: "Your workspace starts here",
      description: "No workspace information is loaded until secure access is established.",
      languageNotice: "Shan is selected. Reviewed English is shown for untranslated text.",
    },
    navigation: {
      primaryLabel: "Workspace navigation",
      home: "Home",
      transactions: "Transactions",
      add: "Add",
      reports: "Reports",
      more: "More",
      submissions: "Submissions",
      status: "Status",
      review: "Review",
      unavailable: "Unavailable",
    },
    languages: {
      shn: "Shan",
      my: "Myanmar",
      en: "English",
      ja: "Japanese",
    },
    roles: {
      ADMIN: "Admin",
      CONTRIBUTOR: "Contributor",
      ADVISOR: "Advisor",
    },
    auth: {
      common: {
        submitting: "Please wait",
        backToLogin: "Return to sign in",
      },
      fields: {
        displayName: "Your name",
        email: "Email address",
        password: "Password",
        currentPassword: "Current password",
        newPassword: "New password",
        newPasswordOptional: "New password, if this is your first activation",
        passwordHint: "Use at least 15 characters. Password managers and paste are supported.",
        activationValue: "Activation code",
        recoveryValue: "Recovery code",
        language: "Preferred language",
        timezone: "Time zone",
        workspaceName: "Workspace name",
        workspaceType: "Workspace type",
        currency: "Base currency code",
      },
      bootstrap: {
        title: "Create the first secure workspace",
        description: "This one-time setup creates the first Admin and workspace together.",
        accountHeading: "Admin account",
        workspaceHeading: "Workspace",
        submit: "Complete secure setup",
        failure:
          "Setup could not be completed. Check the fields or ask the operator whether setup is still available.",
      },
      login: {
        title: "Sign in",
        description:
          "Use your F2S account. No workspace information is shown before authentication.",
        submit: "Sign in securely",
        failure: "Sign in was not successful. Check the credentials and try again.",
        recoveryLink: "Recover account access",
      },
      activation: {
        title: "Activate account access",
        description:
          "Enter the single-use activation code you received. Codes are never placed in this page's URL.",
        submit: "Activate access",
        success: "Activation is complete. You can now sign in.",
        failure:
          "Activation could not be completed. The code may be invalid, expired, or already used.",
      },
      recovery: {
        requestTitle: "Recover account access",
        requestDescription:
          "Enter the account email. The same response is shown whether or not recovery is available.",
        requestSubmit: "Request recovery",
        requestSuccess:
          "If recovery is available, instructions will be delivered through the approved channel.",
        requestFailure: "The recovery request could not be accepted. Wait and try again.",
        confirmLink: "I already have a recovery code",
        confirmTitle: "Set a new password",
        confirmDescription: "Enter the single-use recovery code and a new password.",
        confirmSubmit: "Complete recovery",
        confirmSuccess: "The password was changed. Sign in again on every device.",
        confirmFailure:
          "Recovery could not be completed. The code may be invalid, expired, or already used.",
      },
      passwordChange: {
        link: "Change password",
        title: "Change password",
        description: "Confirm the current password. Other active sessions will be revoked.",
        submit: "Change password",
        success: "The password was changed and other sessions were revoked.",
        failure:
          "The password could not be changed. Check the current credential and new password.",
      },
      logout: {
        current: "Sign out on this device",
        all: "Sign out on every device",
      },
      session: {
        expired: "The session expired or was revoked. Sign in again.",
        network:
          "The session could not be refreshed safely. Sign in again when the connection is available.",
      },
    },
    workspace: {
      types: {
        HOUSEHOLD: "Household",
        FARM: "Farm",
        MICROBUSINESS: "Microbusiness",
        SMALL_BUSINESS: "Small business",
        COMBINED: "Combined",
        CUSTOM: "Custom",
      },
      selection: {
        eyebrow: "Authenticated account",
        title: "Choose a workspace",
        description:
          "Select the workspace you want to open. Its current membership and permissions will be checked by the server.",
        empty:
          "No active workspace membership is available. Contact a workspace Admin without sharing credentials.",
        open: "Open workspace",
        opening: "Opening securely",
      },
      current: {
        label: "Current workspace",
      },
      switch: {
        start: "Switch workspace",
        title: "Switch workspace?",
        description:
          "Current workspace selections and protected cached views will be cleared before another workspace is loaded.",
        confirm: "Clear and continue",
        cancel: "Stay here",
      },
    },
    protected: {
      home: {
        title: "Workspace access is ready",
        description:
          "Only the selected workspace context is active. Business data screens are delivered by later issues.",
        authorizationNotice:
          "Navigation reflects the current role for clarity. The server still authorizes every request.",
      },
      placeholder:
        "This role-appropriate destination is reserved for its owning feature issue. No business data has been loaded.",
    },
    states: {
      loading: {
        title: "Loading",
        description: "Please wait while the latest permitted information is requested.",
      },
      empty: {
        title: "Nothing to show yet",
        description: "No verified workspace information is available on this page.",
      },
      error: {
        title: "This page is unavailable",
        description: "Try again. If the problem continues, return to a safe page.",
        retry: "Try again",
      },
    },
    errors: {
      configuration: {
        title: "Application configuration is unavailable",
        description: "F2S could not start safely. Contact the application administrator.",
      },
      unavailable: "This information is unavailable.",
    },
    notFound: {
      title: "Page not found",
      description: "The requested page does not exist or is not available.",
      backHome: "Return home",
    },
  },
} as const;
