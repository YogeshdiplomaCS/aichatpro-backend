from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import requests
import hashlib
import os

app = Flask(__name__)
CORS(app)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "database": os.environ.get("DB_NAME", "chatapp"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "yogesh"),
    "port": int(os.environ.get("DB_PORT", "5433"))
}


def get_db():
    config = DB_CONFIG.copy()
    config["sslmode"] = "require"
    return psycopg2.connect(**config)

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()


@app.route("/")
def home():
    return jsonify({"status": "AI Chat Pro Backend Running!"})


@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name", "")
    age = data.get("age", 0)
    email = data.get("email", "")
    password = hash_pw(data.get("password", ""))
    try:
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
                    INSERT INTO users (email, name, age, password)
                    VALUES (%s, %s, %s, %s) RETURNING id, email, name, age
                    """, (email, name, age, password))
        user = cur.fetchone()
        db.commit()
        cur.close()
        db.close()
        return jsonify({
            "user_id": user["id"],
            "name": user["name"],
            "email": user["email"],
        })
    except Exception as e:
        return jsonify({"error": "Email already exists"}), 400


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email", "")
    password = hash_pw(data.get("password", ""))
    try:
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
                    SELECT id, name, email
                    FROM users
                    WHERE email = %s
                      AND password = %s
                    """, (email, password))
        user = cur.fetchone()
        cur.close()
        db.close()

        if not user:
            return jsonify({"error": "Email or Password is wrong"}), 401

        return jsonify({
            "user_id": user["id"],
            "name": user["name"],
            "email": user["email"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_id = data.get("user_id", 1)
    message = data.get("message", "")

    system_prompt = (
        "You are a helpful AI assistant called AI Chat Pro. "
        "Always reply in English. "
        "Be friendly, helpful and concise."
    )

    models = [
        "openrouter/auto",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-3-27b-it:free",
        "qwen/qwen3-coder-480b-a35b:free",
        "nousresearch/hermes-3-llama-3.1-405b:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "liquid/lfm2.5-1.2b-instruct:free",
    ]

    reply = "All AI models are busy. Please try again."

    for model in models:
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": "Bearer " + OPENROUTER_API_KEY,
                    "HTTP-Referer": "http://localhost",
                    "Content-Type": "application/json",
                    "X-Title": "AI Chat Pro"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 500
                },
                timeout=30
            )
            resp_json = response.json()
            if "choices" in resp_json:
                content = resp_json["choices"][0]["message"]["content"]
                if content and len(content.strip()) > 0:
                    reply = content.strip()
                    break
        except Exception as e:
            continue

    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO messages (user_id, role, content, language) VALUES (%s,%s,%s,%s)",
            (user_id, "user", message, "en")
        )
        cur.execute(
            "INSERT INTO messages (user_id, role, content, language) VALUES (%s,%s,%s,%s)",
            (user_id, "assistant", reply, "en")
        )
        db.commit()
        cur.close()
        db.close()
    except Exception:
        pass

    return jsonify({"reply": reply})


@app.route("/history/<int:user_id>", methods=["GET"])
def history(user_id):
    try:
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT role, content FROM messages WHERE user_id=%s ORDER BY created_at",
            (user_id,)
        )
        messages = cur.fetchall()
        cur.close()
        db.close()
        return jsonify(list(messages))
    except Exception:
        return jsonify([])


if __name__ == "__main__":
    print("=" * 50)
    print("  AI Chat Pro Backend")
    print("  Created by Yogesh")
    print("=" * 50)
    app.run(host="0.0.0.0", port=8080, debug=True)
