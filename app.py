import os
from functools import wraps

import requests
from flask import (
    Flask, redirect, url_for, session,
    abort
)
from authlib.integrations.flask_client import OAuth
from authlib.jose import jwt, JsonWebKey
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

oauth = OAuth(app)

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")

ISSUER = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"

oauth.register(
    name="keycloak",
    client_id=CLIENT_ID,
    client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET"),
    server_metadata_url=(
        f"{ISSUER}/.well-known/openid-configuration"
    ),
    client_kwargs={
        "scope": "openid profile email"
    },
)


def get_realm_roles(access_token):
    """Verify the Keycloak access token and extract realm roles."""

    jwks_url = f"{ISSUER}/protocol/openid-connect/certs"

    response = requests.get(jwks_url, timeout=10)
    response.raise_for_status()

    key_set = JsonWebKey.import_key_set(response.json())

    claims = jwt.decode(access_token, key_set)

    # Validate token expiration and other standard claims.
    claims.validate()

    # Verify that this token was issued by our Keycloak realm.
    if claims.get("iss") != ISSUER:
        raise ValueError("Invalid token issuer")

    # Verify the authorized client.
    if claims.get("azp") != CLIENT_ID:
        raise ValueError("Unexpected authorized client")

    return claims.get("realm_access", {}).get("roles", [])


def role_required(required_role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user"):
                return redirect(url_for("login"))

            roles = session.get("roles", [])

            # Admin inherits standard user permissions
            if "admin" in roles:
                roles.append("user")

            if required_role not in roles:
                abort(403)

            return view(*args, **kwargs)

        return wrapped
    return decorator


@app.route("/")
def home():
    user = session.get("user")

    if user:
        return f"""
        <h1>Keycloak IAM Lab</h1>
        <p>Welcome, {user.get('preferred_username')}!</p>
        <p>Your roles: {', '.join(session.get('roles', []))}</p>
        <a href="/user">User page</a><br>
        <a href="/admin">Admin page</a><br>
        <a href="/logout">Logout</a>
        """

    return """
    <h1>Keycloak IAM Lab</h1>
    <a href="/login">Login with Keycloak</a>
    """


@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True)
    return oauth.keycloak.authorize_redirect(redirect_uri)


@app.route("/callback")
def callback():
    token = oauth.keycloak.authorize_access_token()

    user = token.get("userinfo")

    if not user:
        user = oauth.keycloak.userinfo()

    roles = get_realm_roles(token["access_token"])

    session["user"] = dict(user)
    session["roles"] = roles

    return redirect(url_for("home"))


@app.route("/user")
@role_required("user")
def user_page():
    return """
    <h1>User Dashboard</h1>
    <p>You have standard user access.</p>
    <a href="/">Home</a>
    """


@app.route("/admin")
@role_required("admin")
def admin_page():
    return """
    <h1>Admin Dashboard</h1>
    <p>You have administrative access.</p>
    <a href="/">Home</a>
    """


@app.route("/logout")
def logout():
    session.clear()

    logout_url = (
        f"{ISSUER}/protocol/openid-connect/logout"
    )

    return redirect(
        f"{logout_url}?post_logout_redirect_uri="
        f"{url_for('home', _external=True)}"
        f"&client_id={CLIENT_ID}"
    )


@app.errorhandler(403)
def forbidden(error):
    return """
    <h1>403 - Access Denied</h1>
    <p>You do not have permission to access this page.</p>
    <a href="/">Return home</a>
    """, 403


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
