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
      admin: "Administration",
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
        ownership:
          "Ownership transfer completed. Sign in again because both affected accounts were signed out.",
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
    administration: {
      cancel: "Go back",
      conflict:
        "Someone changed this resource after you loaded it. Your change was not applied. Reload the latest information before trying again.",
      denied: {
        title: "Administration is unavailable",
        description:
          "This workspace role cannot access administration. No administration information was requested.",
      },
      index: {
        title: "Workspace administration",
        description:
          "Manage the selected workspace and its access. The server authorizes every operation.",
        navigationLabel: "Administration sections",
        settingsDescription: "Update workspace identity, profile, and enabled modules.",
        membersDescription: "Provision members and manage their lifecycle and role.",
        ownershipDescription: "Transfer the sole Admin ownership through the dedicated workflow.",
      },
      fields: {
        description: "Description",
        address: "Address",
        businessCategory: "Business category code",
        farmType: "Farm type code",
        role: "Workspace role",
      },
      modules: {
        HOUSEHOLD_FINANCE: "Household finance",
        FARMING_INVESTMENTS: "Farming investments",
      },
      settings: {
        title: "Workspace settings",
        description:
          "Review identity, profile, and module settings. Existing records are never silently changed or deleted.",
        identityHeading: "Identity and regional settings",
        profileHeading: "Workspace profile",
        modulesHeading: "Enabled modules",
        modulesDescription:
          "Workspace type provides recommendations; these validated module settings control availability.",
        review: "Review settings change",
        confirmTitle: "Apply these workspace settings?",
        confirmDescription:
          "The server will reject this update if a newer workspace version already exists.",
        confirm: "Apply settings",
        success: "Workspace settings were updated.",
        failure: "Workspace settings could not be updated. Review the fields and try again.",
        reload: "Reload latest settings",
        latestLoaded: "The latest workspace settings were loaded.",
        reloadFailure: "The latest workspace settings could not be loaded.",
      },
      members: {
        title: "Workspace members",
        description:
          "Only Contributor and Advisor memberships can be managed here. Ownership uses its dedicated flow.",
        empty: "No members are available.",
        createTitle: "Add a workspace member",
        createDescription:
          "Create a pending Contributor or Advisor membership. Activation instructions use the approved delivery channel.",
        create: "Create pending member",
        createSuccess: "The pending member was created and activation delivery was requested.",
        createFailure:
          "The member could not be created. Your non-secret entries remain available for correction.",
        ownerProtected: "The sole Admin owner cannot be changed through member lifecycle actions.",
        changeRole: "Change role",
        suspend: "Review suspension",
        reactivate: "Review reactivation",
        restart: "Review activation restart",
        revoke: "Review revocation",
        confirmTitle: "Confirm member action",
        confirmAction: "Apply member action",
        actionSuccess: "The member action was completed using the current version.",
        actionFailure: "The member action could not be completed.",
        confirm: {
          ROLE: "Change {{name}}'s role? Their permitted actions will change immediately.",
          SUSPEND: "Suspend {{name}}? They will lose workspace access.",
          REACTIVATE: "Reactivate {{name}}? Their permitted workspace access will return.",
          RESTART:
            "Restart activation for {{name}}? Previous activation evidence will stop working.",
          REVOKE: "Revoke {{name}}? This membership cannot be restored through reactivation.",
        },
      },
      memberStatus: {
        PENDING: "Pending",
        ACTIVE: "Active",
        SUSPENDED: "Suspended",
        REVOKED: "Revoked",
      },
      ownership: {
        title: "Transfer workspace ownership",
        description:
          "Move the sole Admin ownership to one active member. This high-impact action has a separate confirmation step.",
        target: "New owner",
        chooseTarget: "Choose an active member",
        noCandidates: "An active Contributor or Advisor is required before ownership can transfer.",
        formerRole: "Your role after transfer",
        consequences:
          "I understand the selected member becomes the sole Admin, my role changes, and both accounts will be signed out when the transfer completes.",
        review: "Review ownership transfer",
        confirmTitle: "Initiate ownership transfer?",
        confirmDescription:
          "Your current password will reauthenticate this request. The new owner must confirm with single-use evidence before expiry.",
        initiate: "Initiate transfer",
        reauthenticationFailure:
          "The current password could not reauthenticate this ownership request.",
        failure:
          "Ownership transfer could not be initiated. Non-secret selections remain unchanged.",
        pendingTitle: "Ownership transfer outcome",
        transferId: "Transfer ID",
        status: "Status",
        expires: "Confirmation expires",
        cancelTransfer: "Cancel pending transfer",
        cancelFailure: "The pending transfer could not be cancelled.",
        confirmationTitle: "Confirm new workspace ownership",
        confirmationDescription:
          "Sign in as the selected target member, then enter the transfer ID and single-use confirmation code. Neither value is placed in the URL.",
        confirmationValue: "Ownership confirmation code",
        confirmationConsequences:
          "I understand I will become the sole Admin owner and both affected accounts will be signed out.",
        complete: "Confirm ownership transfer",
        confirmationFailure:
          "Ownership could not be confirmed. The evidence may be invalid, expired, foreign, or already used.",
        outcome: {
          INITIATED: "Waiting for confirmation",
          CONFIRMED: "Confirmed",
          CANCELLED: "Cancelled",
          EXPIRED: "Expired",
          COMPLETED: "Completed",
        },
      },
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
