"""Google identity boundary. Claims must come from Streamlit's verified st.user."""

from hashlib import sha256
import streamlit as st

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"


def google_user_id(user) -> str:
    """Use Google's immutable subject, never an email or browser-supplied ID."""
    if not user.get("is_logged_in", False):
        raise ValueError("Sign in with Google to access your notebook.")
    if user.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
        raise ValueError("Please sign in using a Google account.")
    subject = user.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("Google did not provide an account ID. Please sign in again.")
    return "google_" + sha256(subject.encode("utf-8")).hexdigest()


def sign_out():
    st.session_state.clear()
    st.logout()


def require_google_user() -> str:
    """Stop before any notebook access and discard state when identity changes."""
    try:
        user_id = google_user_id(st.user)
    except ValueError as exc:
        st.session_state.clear()
        st.title("MyNBA | The Front Office")
        st.write("Sign in with Google to keep your own season and event notebook.")
        if st.user.get("is_logged_in", False):
            st.error(str(exc))
            st.button("Sign out", key="sign_out", on_click=sign_out)
        else:
            try:
                auth = st.secrets.get("auth", {})
            except FileNotFoundError:
                auth = {}
            configured = all(auth.get(key) for key in ("redirect_uri", "cookie_secret", "client_id", "client_secret")) and auth.get("server_metadata_url") == GOOGLE_METADATA_URL
            if configured:
                st.button("Sign in with Google", key="google_sign_in", on_click=st.login, type="primary")
            else:
                st.info("Google sign-in is not configured yet. The app owner must add the Google OAuth settings to Streamlit Secrets (see docs/GOOGLE_SIGN_IN.md).")
        st.stop()
    if st.session_state.get("notebook_user_id") != user_id:
        st.session_state.clear()
        st.session_state.notebook_user_id = user_id
    with st.sidebar:
        st.write("Signed in as", st.user.get("name") or st.user.get("email") or "Google user")
        st.button("Sign out", key="sign_out", on_click=sign_out)
    return user_id
