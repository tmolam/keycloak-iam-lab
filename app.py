import os
from flask import Flask, redirect, url_for, session
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

oauth = OAuth(app)

oauth.register(
    name="keycloak",
    client_id=os.getenv("KEYCLOAK_CLIENT_ID"),
    client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET"),
    server_metadata_url=(
        f"{os.getenv('KEYCLOAK_URL')}/realms/"
        f"{os.getenv('KEYCLOAK_REALM')}/.well-known/openid-configuration"
    ),
    client_kwargs={
        "scope": "openid profile email"
    },
)

@app.route("/")
def home():
    user = session.get("user")

    if user:
        return f"""
        <h1>Keycloak IAM Lab</h1>
        <p>Welcome, {user.get('preferred_username')}!</p>
        <a href="/logout">Logout</a>
        """

    return """
    <h1>Keycloak IAM Lab</h1>
    <a href="/login">Login with Keycloak</a>
    """

@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True)
    print("OIDC redirect URI:", redirect_uri)
    return oauth.keycloak.authorize_redirect(redirect_uri)

@app.route("/callback")
def callback():
    token = oauth.keycloak.authorize_access_token()
    user = token.get("userinfo")

    if not user:
        user = oauth.keycloak.userinfo()

    session["user"] = dict(user)
    session["id_token"] = token.get("id_token")
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    id_token = session.get("id_token")
    session.clear()

    logout_url = (
        f"{os.getenv('KEYCLOAK_URL')}/realms/"
        f"{os.getenv('KEYCLOAK_REALM')}/protocol/openid-connect/logout"
    )

    return redirect(
        f"{logout_url}?post_logout_redirect_uri="
        f"{url_for('home', _external=True)}"
        f"&client_id={os.getenv('KEYCLOAK_CLIENT_ID')}"
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
