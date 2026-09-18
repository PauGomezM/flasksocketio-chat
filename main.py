from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import os
import secrets
from string import ascii_uppercase


app = Flask(__name__)

secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable must be set.")

app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_COOKIE_SECURE", "").lower()
    in {"1", "true", "yes"},
)

socketio = SocketIO(app)

rooms = {}
used_colors = []


@app.after_request
def set_security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' ws: wss:; "
        "img-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def generate_code(length):
    # Generate a cryptographically unpredictable room code.
    while True:
        code = "".join(secrets.choice(ascii_uppercase) for _ in range(length))
        if code not in rooms:
            return code


def generate_color():
    global used_colors

    r = 255
    g = secrets.randbelow(256)
    b = secrets.randbelow(256)

    colors = [r, g, b]
    secrets.SystemRandom().shuffle(colors)
    return tuple(colors)


@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:40]
        code = (request.form.get("code") or "").strip().upper()
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template(
                "home.html", error="Provide a valid name", code=code, name=name
            )

        if join is not False:
            valid_code = (
                len(code) == 4
                and all(character in ascii_uppercase for character in code)
            )
            if not valid_code:
                return render_template(
                    "home.html",
                    error="Please enter a valid room code",
                    code=code,
                    name=name,
                )

        room = code
        if create is not False:
            room = generate_code(4)
            rooms[room] = {"n_users": 0, "users": []}
        elif code not in rooms:
            return render_template(
                "home.html",
                error="Specified room does not exist",
                code=code,
                name=name,
            )

        session["room"] = room
        session["name"] = name

        return redirect(url_for("room"))

    return render_template("home.html")


@app.route("/room")
def room():
    room_code = session.get("room")
    name = session.get("name")

    existent_user = False
    existent_lobby = False

    if name is not None and room_code in rooms:
        existent_lobby = True
        for user in rooms[room_code]["users"]:
            if user["name"] == name:
                existent_user = True
                break

    if (
        room_code is None
        or name is None
        or room_code not in rooms
        or existent_user
        or not existent_lobby
    ):
        return redirect(url_for("home"))

    return render_template("room.html", code=room_code)


@socketio.on("message")
def message(data):
    room_code = session.get("room")
    user_name = session.get("name")

    if room_code not in rooms or not user_name or not isinstance(data, dict):
        return

    raw_message = data.get("data")
    if not isinstance(raw_message, str):
        return

    message_text = raw_message.strip()
    if not message_text:
        return

    message_text = message_text[:300]

    existent_user = False
    position = None
    color = None

    for index, user in enumerate(rooms[room_code]["users"]):
        if user["name"] == user_name:
            existent_user = True
            position = index
            color = user["color"]
            break

    if not existent_user:
        color = generate_color()

    content = {
        "name": user_name,
        "color": color,
        "message": message_text,
    }

    if existent_user and position is not None:
        rooms[room_code]["users"][position] = content
    else:
        rooms[room_code]["users"].append(content)

    send(content, to=room_code)


@socketio.on("connect")
def connect(auth):
    room_code = session.get("room")
    name = session.get("name")

    if not room_code or not name or room_code not in rooms:
        return False

    if any(user["name"] == name for user in rooms[room_code]["users"]):
        return False

    join_room(room_code)

    color = generate_color()
    content = {
        "name": name,
        "color": color,
        "message": "has joined the lobby",
    }

    send(content, to=room_code)

    rooms[room_code]["users"].append(content)
    rooms[room_code]["n_users"] += 1


@socketio.on("disconnect")
def disconnect():
    room_code = session.get("room")
    name = session.get("name")

    if not room_code or not name or room_code not in rooms:
        return

    leave_room(room_code)

    color = (255, 255, 255)
    user_list = rooms[room_code]["users"]

    for user in list(user_list):
        if user["name"] == name:
            color = user["color"]
            user_list.remove(user)
            break

    rooms[room_code]["n_users"] = max(0, rooms[room_code]["n_users"] - 1)
    if rooms[room_code]["n_users"] <= 0:
        del rooms[room_code]
        return

    content = {
        "name": name,
        "color": color,
        "message": "has left the lobby",
    }

    send(content, to=room_code)


if __name__ == "__main__":
    debug_enabled = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    socketio.run(app, debug=debug_enabled)
