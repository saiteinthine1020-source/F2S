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
      home: "Home",
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
