# Google sign-in and personal notebooks

The app uses Streamlit's native OpenID Connect integration with Google. Streamlit
validates the identity token; the app accepts a Google issuer and a nonempty
Google subject (`sub`) only. Each subject maps to a stable ID:
`google_` plus the SHA-256 hash of `sub`. Email changes do not change this ID.
The user's notebook lives at `user_notebooks/{user_id}`. No email, profile photo,
Google token, or password is saved in Firestore. The app has no user-ID input.

## Configure Google (one-time setup)

1. Open [Google Auth Platform](https://console.cloud.google.com/auth/overview) in
   the Google Cloud project associated with your Firebase project.
2. Configure Branding and Audience. Use an External audience for personal Google
   accounts. While in Testing, add the Google accounts you want to test with.
3. Create an OAuth client with application type **Web application**. Register
   these exact **Authorized redirect URIs**:
   - `https://mynba-event-generator.streamlit.app/oauth2callback`
   - `http://localhost:8501/oauth2callback` (for local development)
4. Copy its client ID and client secret directly into Streamlit Secrets. These
   are OAuth client credentials, separate from the Firebase service-account key.
5. When ready for everyone, change the OAuth audience publishing status to
   Production and complete any requirements shown by Google.

See the [official Google/Streamlit tutorial](https://docs.streamlit.io/develop/tutorials/authentication/google).

## Configure Streamlit

In your deployed app's settings, open **Secrets**. Keep the existing `[firebase]`
section and add the `[auth]` block from
[the example](../.streamlit/secrets.toml.example). Replace the placeholders.
Generate a cookie secret using:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Keep that secret stable across server restarts. Never commit real secrets.
For local development, use the same auth block in `.streamlit/secrets.toml`,
with `redirect_uri = "http://localhost:8501/oauth2callback"`.
Install `requirements.txt` (now includes `streamlit[auth]>=1.66.0`) and restart.
Push the code to the deployment's GitHub branch to update the hosted app.
The code intentionally blocks notebook access until sign-in is configured.

## Firestore access controls

This app accesses Firestore only from Python through the Firebase Admin SDK.
That SDK uses service-account IAM and bypasses Firestore client Security Rules;
per-user authorization happens on the server using Streamlit's verified identity.
Both startup and save callbacks check the identity. Only the database client is
cached globally; notebooks and document references are not shared across users.

For a Firebase project dedicated to this app, publish the supplied
[`firestore.rules`](../firestore.rules) in **Firestore Database → Rules**. It denies
all direct browser/mobile client access while allowing the Admin SDK to operate.
This file is a deployment artifact: committing it does not publish the rules.
If the project serves other apps, review their rules before replacing them; a
broader existing `allow` rule can override a narrower deny rule. A Streamlit Google
login is not Firebase Authentication, so a `request.auth.uid` rule is not how this
server establishes ownership.

Source: [Firestore server access and rules](https://firebase.google.com/docs/firestore/security/rules-conditions).

## Existing notes

The former shared `mynba/event_notepad` document and any local JSON file are left
untouched and are never used as a fallback. Every Google account starts with an
empty notebook. To retain the old shared notes for the owner, explicitly copy
that document to the owner's `user_notebooks/{user_id}` after establishing their
ID. Do not copy shared notes into every user's account.

Signing out clears the current session's notebook and drafts. Other already-open
browser tabs may retain their authenticated session until they sign out or reload;
Streamlit logout is not global Google-account logout.

## Tests

```bash
python -m unittest discover -s tests
MYNBA_TEST_FIRESTORE=1 python -m unittest discover -s tests -p test_firestore_live.py
```

`tests/test_user_auth.py` simulates the verified callback identity in Streamlit's
AppTest. It clicks sign-in, draws and saves an event, reloads it, signs out, switches
accounts, and checks that a second user cannot see or change the first user's
notes. Invalid identities and stale save callbacks are rejected. Google itself
is mocked: these tests do not validate Google credentials, consent screens,
redirect URLs, cookies, or Google's token-signature verification.

The opt-in live tests use the real Firestore SDK and credentials, including a
simulated Google callback followed by real UI event saving to two separate random
user documents. The tests delete all temporary documents afterward. They never
write to an existing user's notebook.

After configuring OAuth, perform the real browser check:

1. Open the deployed app in an incognito window and sign in with Google account A.
2. Draw an event, save its note, and refresh: it should still be present.
3. Sign out and sign in with Google account B: A's notes must not appear.
4. Save a different note as B, then return as A: only A's original note appears.
5. Cancel a Google sign-in: the app must stay on the sign-in screen.

## Storage

One Firestore document holds a user's active season and saved notes. Sign-in alone
creates no document; the first save does. Storage grows with the number and length
of saved notes, not with the number of sign-ins or draws. Firestore also stores
index entries; JSON file size is not the billed size. This design has Firestore's
1 MiB per-document limit, so it is intended for season notebooks, not unlimited
archives. Season rollover removes departing-season notes.

For lower index overhead, you can exempt `items` from single-field indexing for
the `user_notebooks` collection group in Firestore's index settings: the app reads
whole documents by ID and does not query individual notes. This is optional and
is not changed automatically by this code.

Sources: [storage calculations](https://firebase.google.com/docs/firestore/storage-size),
[Firestore limits and free quota](https://firebase.google.com/docs/firestore/quotas).

Measured against the three notes in the existing local notebook, note data ranges
from 446–549 bytes (average 505 bytes) using Firestore's documented size formula.
With the new document path and current metadata, estimated document storage is:

| Saved notes per user | Document data (before indexes) |
| --- | --- |
| 10 | 5.2 KiB |
| 100 | 49.6 KiB |
| 1,000 | 493.7 KiB |

These are estimates for similar-length notes, not fixed allocations. Default
indexing adds storage; allowing roughly twice the document size is a useful rough
budget for these short notes, not a billing guarantee. Longer instructions and
extra indexes change the result. The free database quota is 1 GiB across all users,
and daily read/write quotas apply separately.
