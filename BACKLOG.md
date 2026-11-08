# Backlog

- [ ] Protect notebook saves from simultaneous edits in two sessions of the same account. Use a Firestore transaction or write precondition so the version check and write are atomic. Preserve the losing session's draft and explain the conflict. Test two saves against the same starting version and confirm neither silently overwrites the other.

- [ ] Add a public welcome page and privacy page accessible without signing in. Explain the app's purpose, Google account information used, notebook storage, retention (including season rollover), and how users can request data deletion. Link the privacy page from the welcome screen and use consistent app naming in Google OAuth branding. Verify both pages are accessible while signed out.
