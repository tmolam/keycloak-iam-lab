from flask import Flask, request
import json
import urllib.parse
import urllib.request
import urllib.error

app = Flask(__name__)

def check_keycloak_permission(path, scope="view"):
    access_token = request.headers.get("X-Forwarded-Access-Token")

    if not access_token:
        return False

    params = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:uma-ticket",
        "audience": "legacy-app",
        "permission": f"{path}#{scope}",
        "permission_resource_format": "uri",
        "permission_resource_matching_uri": "true",
        "response_mode": "decision"
    })

    req = urllib.request.Request(
        "http://keycloak:8080/realms/iam-lab/protocol/openid-connect/token",
        data=params.encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
            return result.get("result") is True
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return False

@app.route("/")
def home():
    return """
    <h1>Legacy Application</h1>
    <p>This application has no built-in authentication.</p>
    <p>If you can see this page, you have reached the application.</p>
    """

@app.route("/admin/dashboard")
def admin_dashboard():
    if not check_keycloak_permission("/admin/dashboard"):
        return {"error": "Access denied by Keycloak"}, 403

    return {
        "message": "Welcome to the Admin Dashboard",
        "authorization": "Granted by Keycloak"
    }

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
