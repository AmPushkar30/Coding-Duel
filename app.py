import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from datetime import datetime, timezone
from bson import ObjectId
import re
import requests
from threading import Timer
import json   
from collections import defaultdict
from calendar import monthrange
from itsdangerous import URLSafeTimedSerializer
from flask import current_app




# -------------------- Basic Setup --------------------

app = Flask(__name__)
app.secret_key = "supersecretkey"
serializer = URLSafeTimedSerializer(app.secret_key)


# ✅ Database setup
client = MongoClient("mongodb://127.0.0.1:27017/")
db = client["Coding_Duel"]
users_col = db["users"]
matches_col = db["matches"]
questions_col = db["questions"]  # added question collection
leaderboard_col = db["leaderboard"]



# ✅ Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")


# -------------------- Routes --------------------

@app.route('/')
def home():
    return redirect(url_for('register'))

# Display player profile 
@app.route('/profile')
def profile():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    user = users_col.find_one(
        {"email": session['user_email']},
        {"password": 0}
    )

    # Fetch matches played by this user
    matches = list(matches_col.find({
        "$or": [
            {"player1.email": user["email"]},
            {"player2.email": user["email"]}
        ]
    }))

    total_matches = len(matches)
    wins = sum(1 for m in matches if m.get("winner") == user["name"])
    losses = sum(1 for m in matches if m.get("winner") not in [user["name"], "Draw"])
    draws = sum(1 for m in matches if m.get("winner") == "Draw")

    return render_template(
        "profile.html",
        user=user,
        stats={
            "matches": total_matches,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            
        }
    )


# Players match history
@app.route("/history")
def history():
    if "user_email" not in session:
        return redirect(url_for("login"))

    email = session["user_email"]
    name = session["user_name"]

    matches = list(
        matches_col.find({
            "$or": [
                {"player1.email": email},
                {"player2.email": email}
            ]
        }).sort("created_at", -1)
    )

    history_data = []

    for m in matches:
        is_p1 = m["player1"]["email"] == email
        me = m["player1"] if is_p1 else m["player2"]
        opp = m["player2"] if is_p1 else m["player1"]

        if m.get("winner") == name:
            result = "Win"
        elif m.get("winner") == "Draw":
            result = "Draw"
        else:
            result = "Loss"

        # ✅ SAFE question fetch
        qids = m.get("attempted_questions", {}).get(name, [])
        questions = []
        if qids:
            questions = list(
                questions_col.find(
                    {"_id": {"$in": qids}},
                    {"description": 1}
                )
            )

        history_data.append({
    "id": str(m["_id"]),   
    "date": m["created_at"],
    "opponent": opp["name"],
    "language": m["language"],
    "result": result,
    "points": me["points"],
    "questions": [q["description"] for q in questions]
})


    return render_template(
        "history.html",
        history=history_data,
        total_matches=len(history_data)
    )


@app.route("/match/<match_id>")
def match_detail(match_id):
    if "user_email" not in session:
        return redirect(url_for("login"))

    email = session["user_email"]
    name = session["user_name"]

    match = matches_col.find_one({"_id": ObjectId(match_id)})
    if not match:
        return redirect(url_for("history"))

    is_p1 = match["player1"]["email"] == email
    me = match["player1"] if is_p1 else match["player2"]
    opp = match["player2"] if is_p1 else match["player1"]

    if match.get("winner") == name:
        result = "Win"
    elif match.get("winner") == "Draw":
        result = "Draw"
    else:
        result = "Loss"

    qids = match.get("attempted_questions", {}).get(name, [])
    questions = list(
        questions_col.find({"_id": {"$in": qids}})
    )

    return render_template(
        "match_detail.html",
        match={
            "date": match["created_at"],
            "language": match["language"],
            "result": result,
            "points": me["points"],
            "opponent": opp["name"],
            "questions": [q["description"] for q in questions]
        }
    )

# Leaderboard

def update_leaderboard(user_email, user_name, points_delta):
    month = datetime.now(timezone.utc).strftime("%Y-%m")

    leaderboard_col.update_one(
        {
            "user_email": user_email,
            "month": month
        },
        {
            "$setOnInsert": {
                "user_name": user_name,
                "month": month
            },
            "$inc": {
                "points": points_delta
            },
            "$set": {
                "last_updated": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

@app.route("/leaderboard")
def leaderboard():
    if "user_email" not in session:
        return redirect(url_for("login"))

    month = datetime.utcnow().strftime("%B %Y")
    month_key = datetime.utcnow().strftime("%Y-%m")

    players = list(
        leaderboard_col.find(
            {"month": month_key},
            {"_id": 0}
        ).sort("points", -1)
    )

    leaderboard_data = []
    for i, p in enumerate(players, start=1):
        leaderboard_data.append({
            "rank": i,
            "name": p["user_name"],
            "points": p["points"]
        })

    return render_template(
        "leaderboard.html",
        leaderboard=leaderboard_data,
        month=month
    )


# Registration page route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm = request.form['confirm_password']

        # Validation
        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for('register'))

        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for('register'))

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return redirect(url_for('register'))

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email format.", "error")
            return redirect(url_for('register'))

        if users_col.find_one({"email": email}):
            flash("Email already registered.", "error")
            return redirect(url_for('login'))

        users_col.insert_one({
            "name": name,
            "email": email,
            "password": generate_password_hash(password),
            "created_at": datetime.utcnow()
        })

        session['user_email'] = email
        session['user_name'] = name
        flash("Registration successful!", "success")
        return redirect(url_for('index'))

    return render_template('register.html')


# Login page route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        user = users_col.find_one({"email": email})
        if not user or not check_password_hash(user['password'], password):
            flash("Invalid credentials.", "error")
            return redirect(url_for('login'))

        session['user_email'] = user['email']
        session['user_name'] = user['name']
        flash(f"Welcome {user['name']}!", "success")
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        user = users_col.find_one({"email": email})
        if not user:
            flash("Email not found", "error")
            return redirect(url_for("forgot_password"))

        token = serializer.dumps(email, salt="password-reset")

        reset_link = url_for("reset_password", token=token, _external=True)

        # For now: print link in terminal
        print("Password reset link:", reset_link)

        flash("Password reset link sent (check console for now)", "info")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(
            token,
            salt="password-reset",
            max_age=1800  # 30 minutes
        )
    except Exception:
        flash("Invalid or expired link", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        password = request.form["password"]
        confirm = request.form["confirm"]

        if password != confirm:
            flash("Passwords do not match", "error")
            return redirect(request.url)

        users_col.update_one(
            {"email": email},
            {"$set": {"password": generate_password_hash(password)}}
        )

        flash("Password updated successfully", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")



@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))


@app.route('/index')
def index():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', name=session['user_name'])


# -------------------- MATCHMAKING --------------------

waiting_queue = []  # in-memory matchmaking queue

@app.route('/start_duel')
def start_duel():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template(
        'waiting.html',
        name=session['user_name'],
        email=session['user_email']
    )


@socketio.on('connect')
def on_connect():
    print("🟢 Socket connected:", request.sid)


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    global waiting_queue
    waiting_queue = [p for p in waiting_queue if p['sid'] != sid]
    print("🔴 Socket disconnected:", sid)


@socketio.on('join_queue')
def handle_join_queue(data):
    global waiting_queue
    sid = request.sid
    name = data.get('name')
    email = data.get('email')
    language = data.get('language')

    print(f"🟢 Player joined matchmaking: {name} ({email}) | Language: {language}")

    if not all([name, email, language]):
        emit('error', {'message': 'Invalid matchmaking data'})
        return

    # Find opponent with same language
    opponent = None
    for p in waiting_queue:
        if p['language'] == language:
            opponent = p
            waiting_queue.remove(p)
            break

    if opponent:
        opponent_sid = opponent['sid']
        opponent_name = opponent['name']
        opponent_email = opponent['email']

        # 🧠 Pick random question for the selected language
        question_doc = questions_col.aggregate([
            {"$match": {"language": language}},
            {"$sample": {"size": 1}}
        ])
        question = next(question_doc, None)

        if not question:
            question = {
                "title": "Default Question",
                "description": f"Write a {language.capitalize()} program to print 'Hello World'.",
                "test_input": "",
                "expected_output": "Hello World"
            }

        # ✅ Create match document
        # 🧠 Pick a random question for the selected language
        question_doc = questions_col.aggregate([
            {"$match": {"language": language}},
            {"$sample": {"size": 1}}
        ])
        question = next(question_doc, None)

        # Fallback if no question found
        if not question:
            question = {
                "title": "Default Question",
                "description": f"Write a {language.capitalize()} program to print 'Hello World'.",
                "test_input": "",
                "expected_output": "Hello World",
                "eval_type": "stdin"
            }
            # Insert fallback question in DB to get an _id
            inserted = questions_col.insert_one(question)
            question_id = inserted.inserted_id
        else:
            question_id = question["_id"]

        # ✅ Create match with question and question_id
        match = {
            "player1": {
                "email": opponent_email,
                "name": opponent_name,
                "points": 0,
                "questions_answered": 0
            },
            "player2": {
                "email": email,
                "name": name,
                "points": 0,
                "questions_answered": 0
            },
            
            "language": language,
            "current_questions": {},  # stores current question for each player
            "status": "active",
            "created_at": datetime.now(timezone.utc)
        }



        result = matches_col.insert_one(match)
        room_id = str(result.inserted_id)

        socketio.emit('match_found', {'opponent': name, 'room_id': room_id}, to=opponent_sid)
        emit('match_found', {'opponent': opponent_name, 'room_id': room_id})
        print(f"✅ MATCH FOUND ({language}): {opponent_name} vs {name} | Room {room_id}")

    else:
        # No opponent → wait
        waiting_queue.append({
            'sid': sid,
            'name': name,
            'email': email,
            'language': language,
            'joined_at': datetime.now(timezone.utc)
        })
        emit('waiting', {'message': f'Waiting for another {language} player...'})
        print(f"🕐 {name} added to {language} queue | size={len(waiting_queue)}")


# -------------------- DUEL PAGE --------------------

@app.route('/duel')
def duel():
    if 'user_email' not in session:
        return redirect(url_for('login'))

    room_id = request.args.get('room_id')
    if not room_id:
        flash("Room ID missing.", "error")
        return redirect(url_for('index'))

    match = matches_col.find_one({'_id': ObjectId(room_id)})
    if not match:
        flash("Invalid room ID.", "error")
        return redirect(url_for('index'))

    current_player = session['user_name']
    language = match['language']

    # 🧠 Try to get the player’s current question
    question_id_field = f'current_question_{current_player}'
    qid = match.get(question_id_field)

    # 🧩 If not found, assign a new random question
    if not qid:
        question_doc = questions_col.aggregate([
            {"$match": {"language": language}},
            {"$sample": {"size": 1}}
        ])
        question = next(question_doc, None)
        if not question:
            question = {
                "_id": ObjectId(),
                "description": f"Write a {language.capitalize()} program to print 'Hello World'.",
                "stdin": "",
                "expected_output": "Hello World"
            }
            questions_col.insert_one(question)

        # Attach question to match
        matches_col.update_one(
            {'_id': ObjectId(room_id)},
            {'$set': {question_id_field: question['_id']}}
        )
        qid = question['_id']
    else:
        question = questions_col.find_one({'_id': ObjectId(qid)})

    # 🧾 Safety fallback if still missing
    if not question:
        question = {
            "description": f"Write a {language.capitalize()} program to print 'Hello World'."
        }

    return render_template(
        'duel.html',
        room_id=room_id,
        current_player=current_player,
        player1_name=match['player1']['name'],
        player2_name=match['player2']['name'],
        player1_points=match['player1']['points'],
        player2_points=match['player2']['points'],
        question=question['description']
    )




# -------------------- SOCKET.IO EVENTS --------------------

active_rooms = {}

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data.get('room_id')
    name = data.get('name')
    sid = request.sid

    if not room_id or not name:
        emit('error', {'message': 'Invalid room join'})
        return

    join_room(room_id)
    print(f"🟢 {name} joined room {room_id}")

    if room_id not in active_rooms:
        active_rooms[room_id] = {'players': [], 'scores': {}, 'codes': {}}

    if sid not in active_rooms[room_id]['players']:
        active_rooms[room_id]['players'].append(sid)

    if len(active_rooms[room_id]['players']) == 2:
        print(f"⏰ Starting timer for room {room_id}")
        socketio.emit('start_timer', {'time': 600}, room=room_id)  # 10 minutes
        Timer(600, lambda: handle_time_up({'room_id': room_id})).start()

# Code to check the answer using AI
def ai_judge(question, code, output):
    """
    AI is used ONLY for explanation and hardcode suspicion.
    It must NOT decide correctness.
    """

    prompt = f"""
You are an assistant reviewing a coding submission.

Question:
{question}

User Code:
{code}

Program Output:
{output.strip()}

Tasks:
1. Briefly explain what the code is doing.
2. Say if the solution looks hardcoded or logically general.
3. Do NOT decide accepted or wrong.
4. Keep the response short (2–3 lines).

Respond in plain text.
"""

    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "gemma:2b",
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": 0}
            },
            stream=True,
            timeout=60
        )

        full_resp = ""
        for line in response.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
                full_resp += data.get("response", "")
            except Exception:
                continue

        analysis = full_resp.strip()
        print(f"🤖 AI Review:\n{analysis}")
        return analysis

    except Exception as e:
        print(f"⚠️ AI Judge error: {e}")
        return "AI review unavailable."





@socketio.on('submit_code')
def handle_submit_code(data):
    room_id = data.get('room_id')
    name = data.get('name')
    code = data.get('code')

    if not room_id or not code:
        emit('error', {'message': 'Invalid code submission'})
        return

    try:
        match = matches_col.find_one({'_id': ObjectId(room_id)})
    except Exception:
        emit('error', {'message': 'Invalid room id'})
        return

    if not match:
        emit('error', {'message': 'Match not found'})
        return

    # Determine player field name
    player = 'player1' if match['player1']['name'] == name else 'player2'

    # ✅ FIX: Get the player’s own question reference
    qid_field = f'current_question_{name}'
    qid = match.get(qid_field)
    if not qid:
        emit('error', {'message': 'Question not attached to match'})
        return

    question = questions_col.find_one({'_id': ObjectId(qid)})
    if not question:
        emit('error', {'message': 'Question not found'})
        return

    language = match.get('language', 'python').lower()

    # --- Piston setup ---
    PISTON_URL = "https://emkc.org/api/v2/piston/execute"
    headers = {"Content-Type": "application/json"}

    stdin = question.get("stdin", "")
    expected_output = question.get("expected_output", "").strip()

    payload = {
        "language": language,
        "version": "*",
        "files": [{"name": "main", "content": code}],
        "stdin": stdin
    }

    try:
        resp = requests.post(PISTON_URL, json=payload, headers=headers, timeout=20)
        result = resp.json()
        output = result.get("run", {}).get("output", "").strip()
    except Exception as e:
        emit('error', {'message': f'Code execution failed: {e}'})
        return


    # Run Piston for execution
    piston_output = output.strip()

    
   
    # Ask AI if the code logically produces this output (not hardcoded)
    question_text = question.get("description", "")
    # Deterministic output check FIRST
    expected_output = question.get("expected_output", "").strip()

    if piston_output == expected_output:
        verdict = "Accepted"
    else:
        verdict = "Wrong"



    if verdict == "Accepted":
        points = 10
    elif verdict.startswith("Wrong"):
        points = -5
    else:
        points = 0


    update_leaderboard(
    user_email=session["user_email"],
    user_name=name,
    points_delta=points
)


    # ✅ Update player's points + increment question count
    matches_col.update_one(
        {"_id": ObjectId(room_id)},
        {
            "$set": {
                f"{player}.last_verdict": verdict
            },
            "$inc": {
                f"{player}.points": points,
                f"{player}.questions_answered": 1
            },
            "$addToSet": {
                f"attempted_questions.{name}": qid
            }
        }
    )


   
    # Force fresh read
    updated_match = matches_col.find_one({"_id": ObjectId(room_id)})


    # Emit verdict + updated scores
    emit('verdict', {'verdict': verdict, 'output': output})
    socketio.emit('update_scores', {
        'player1_points': updated_match['player1']['points'],
        'player2_points': updated_match['player2']['points']
    }, room=room_id)

    # ✅ Handle next question logic
    player_data = updated_match[player]
    if player_data['questions_answered'] < 5:
        new_q = list(questions_col.aggregate([
            {"$match": {"language": language}},
            {"$sample": {"size": 1}}
        ]))[0]

        matches_col.update_one(
            {"_id": ObjectId(room_id)},
            {"$set": {f"current_question_{name}": new_q["_id"]}}
        )
        emit('next_question', {'question': new_q['description']})
    else:
        emit('waiting_for_opponent', {'message': 'You’ve completed all questions. Waiting for opponent...'})

        # ✅ If both players finished, decide winner
        if (updated_match['player1']['questions_answered'] >= 5 and
            updated_match['player2']['questions_answered'] >= 5):
            p1_points = updated_match['player1']['points']
            p2_points = updated_match['player2']['points']
            winner = (
                updated_match['player1']['name'] if p1_points > p2_points
                else updated_match['player2']['name'] if p2_points > p1_points
                else "Draw"
            )
            matches_col.update_one(
                {"_id": ObjectId(room_id)},
                {"$set": {"status": "completed", "winner": winner}}
            )
            socketio.emit('duel_result', {'winner': winner}, room=room_id)



@socketio.on('time_up')
def handle_time_up(data):
    room_id = data.get('room_id')
    if not room_id:
        return

    match = matches_col.find_one({'_id': ObjectId(room_id)})
    if not match:
        return

    # read points from nested player objects
    p1_points = match.get('player1', {}).get('points', 0)
    p2_points = match.get('player2', {}).get('points', 0)

    if p1_points > p2_points:
        winner = match['player1']['name']
    elif p2_points > p1_points:
        winner = match['player2']['name']
    else:
        winner = "Draw"


    matches_col.update_one(
        {'_id': ObjectId(room_id)},
        {'$set': {'status': 'completed', 'winner': winner}}
    )

    socketio.emit('duel_result', {'winner': winner}, room=room_id)
    print(f"🏁 Duel finished in room {room_id}. Winner: {winner}")

@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin_login"))

    total_users = users_col.count_documents({})
    total_questions = questions_col.count_documents({})
    total_matches = matches_col.count_documents({})
    live_matches = matches_col.count_documents({"status": "active"})

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_questions=total_questions,
        total_matches=total_matches,
        live_matches=live_matches
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        admin_id = request.form.get("admin_id")
        admin_pass = request.form.get("admin_pass")

        if admin_id == "admin" and admin_pass == "1234":
            session["admin_logged_in"] = True
            session["admin_id"] = admin_id
            return redirect("/admin/dashboard")
        else:
            flash("Invalid Admin Credentials", "error")
            return redirect("/admin/login")

    return render_template("admin/login.html")



# -------------------- ADMIN QUICK OPTIONS --------------------

@app.route("/admin/live_matches")
def admin_live_matches():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin_login"))

    # Active matches only
    live_matches = list(matches_col.find({"status": "active"}).sort("created_at", -1))

    return render_template("admin/live_matches.html", matches=live_matches)


@app.route("/admin/manage_questions")
def admin_manage_questions():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin_login"))

    questions = list(questions_col.find().sort("_id", -1))
    return render_template("admin/manage_questions.html", questions=questions)


@app.route("/admin/add_question", methods=["POST"])
def admin_add_question():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin_login"))

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    language = request.form.get("language", "").strip().lower()
    stdin = request.form.get("stdin", "").strip()
    expected_output = request.form.get("expected_output", "").strip()

    if not title or not description or not language or not expected_output:
        flash("All fields are required!", "error")
        return redirect(url_for("admin_manage_questions"))

    questions_col.insert_one({
        "title": title,
        "description": description,
        "language": language,
        "stdin": stdin,
        "expected_output": expected_output,
        "created_at": datetime.utcnow()
    })

    flash("✅ Question added successfully!", "success")
    return redirect(url_for("admin_manage_questions"))


@app.route("/admin/delete_question/<qid>")
def admin_delete_question(qid):
    if "admin_logged_in" not in session:
        return redirect(url_for("admin_login"))

    try:
        questions_col.delete_one({"_id": ObjectId(qid)})
        flash("🗑 Question deleted!", "success")
    except:
        flash("❌ Invalid Question ID", "error")

    return redirect(url_for("admin_manage_questions"))


@app.route("/admin/leaderboard")
def admin_leaderboard():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin_login"))

    month_key = datetime.utcnow().strftime("%Y-%m")
    month_label = datetime.utcnow().strftime("%B %Y")

    players = list(
        leaderboard_col.find({"month": month_key}, {"_id": 0})
        .sort("points", -1)
    )

    leaderboard = []
    for i, p in enumerate(players, start=1):
        leaderboard.append({
            "rank": i,
            "name": p.get("user_name"),
            "points": p.get("points", 0)
        })

    return render_template("admin/leaderboard.html", leaderboard=leaderboard, month=month_label)


@app.route("/admin/match_history")
def admin_match_history():
    if "admin_logged_in" not in session:
        return redirect(url_for("admin_login"))

    matches = list(matches_col.find().sort("created_at", -1))

    return render_template("admin/match_history.html", matches=matches)



# -------------------- Start Server --------------------
if __name__ == "__main__":
    print("✅ Flask server running with Socket.IO")
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)
