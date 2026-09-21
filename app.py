"""HR dashboard - Flask entry point (Vercel looks for the `app` object in app.py)."""
from flask import Flask, jsonify, render_template

from hr.api import bp as api_bp

app = Flask(__name__, static_folder="public", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # Vercel rejects bodies above ~4.5 MB
app.register_blueprint(api_bp)


@app.get("/")
def index():
    return render_template("index.html")


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "too_large", "message": "ไฟล์ใหญ่เกิน 4 MB"}), 413


if __name__ == "__main__":
    app.run(debug=True)