from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = "eduswap_secret_key"

app.config["MONGO_URI"] = "mongodb://localhost:27017/eduswap"
app.config["UPLOAD_FOLDER"] = "uploads/certificates"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

mongo = PyMongo(app)

ADMIN_SECRET_KEY = "EDUSWAP_ADMIN_2025"

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_current_user():
    if "user_id" in session:
        return mongo.db.users.find_one({"_id": ObjectId(session["user_id"])})
    return None

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper

# ── Public routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    user = get_current_user()
    all_sessions = list(mongo.db.sessions.find({"status": "open"}).sort("created_at", -1).limit(6))
    total_users = mongo.db.users.count_documents({})
    certified = mongo.db.users.count_documents({"is_certified": True})
    session_count = mongo.db.sessions.count_documents({})
    stats = {
        "total_users": total_users,
        "certified": certified,
        "sessions": session_count,
    }
    return render_template("index.html", user=user, skills=all_sessions, stats=stats)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        if mongo.db.users.find_one({"email": email}):
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        user_doc = {
            "name": request.form["name"],
            "email": email,
            "password": generate_password_hash(request.form["password"]),
            "area": request.form.get("area", "Unknown"),
            "college": request.form.get("college", "Unknown"),
            "gender": request.form.get("gender", ""),
            "coins": 100,
            "is_certified": False,
            "cert_status": "none",
            "skills_offered": [],
            "skills_wanted": [],
            "sessions_completed": 0,
            "bio": "",
            "created_at": datetime.utcnow(),
        }

        result = mongo.db.users.insert_one(user_doc)
        session["user_id"] = str(result.inserted_id)
        flash("Welcome to EduSwap! You have 100 starter coins.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = mongo.db.users.find_one({"email": request.form["email"].strip().lower()})
        if user and check_password_hash(user["password"], request.form["password"]):
            session["user_id"] = str(user["_id"])
            session["is_admin"] = False
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ── User routes ───────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    my_sessions = list(mongo.db.sessions.find({"teacher_id": str(user["_id"])}))

    # Enrich sessions with highest bidder name
    for s in my_sessions:
        s["bids_count"] = s.get("bids_count", 0)
        if s.get("highest_bidder_id"):
            hb = mongo.db.users.find_one({"_id": ObjectId(s["highest_bidder_id"])})
            s["highest_bidder_name"] = hb["name"] if hb else "Unknown"
        else:
            s["highest_bidder_name"] = None

    raw_bids = list(mongo.db.bids.find({"bidder_id": str(user["_id"])}).sort("created_at", -1))
    # Enrich bids with session title and status
    my_bids = []
    for bid in raw_bids:
        sess = mongo.db.sessions.find_one({"_id": ObjectId(bid["session_id"])}) if bid.get("session_id") else None
        bid["session_title"] = sess["title"] if sess else "Session deleted"
        bid["status"] = bid.get("status", "placed")
        my_bids.append(bid)

    return render_template("dashboard.html", user=user, my_sessions=my_sessions, my_bids=my_bids)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()

    if request.method == "POST":
        skills_offered_raw = request.form.get("skills_offered", "")
        skills_wanted_raw = request.form.get("skills_wanted", "")

        update = {
            "skills_offered": [s.strip() for s in skills_offered_raw.split(",") if s.strip()],
            "skills_wanted": [s.strip() for s in skills_wanted_raw.split(",") if s.strip()],
            "bio": request.form.get("bio", ""),
        }

        file = request.files.get("certificate")
        if file and file.filename:
            filename = secure_filename(file.filename)
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(path)
            update["certificate_path"] = path
            update["cert_status"] = "pending"
            flash("Certificate uploaded. Awaiting admin verification.", "success")

        mongo.db.users.update_one({"_id": user["_id"]}, {"$set": update})
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)


@app.route("/skills")
def skills():
    query = request.args.get("q", "").strip()
    area = request.args.get("area", "").strip()
    subject = request.args.get("subject", "").strip()

    filters = {"status": "open"}
    if query:
        filters["$or"] = [
            {"title": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}},
            {"subject": {"$regex": query, "$options": "i"}},
        ]
    if area:
        filters["area"] = {"$regex": area, "$options": "i"}
    if subject:
        filters["subject"] = subject

    sessions = list(mongo.db.sessions.find(filters).sort("created_at", -1))
    return render_template("skills.html", sessions=sessions, query=query, area=area, subject=subject)


@app.route("/session/create", methods=["GET", "POST"])
@login_required
def create_session():
    user = get_current_user()

    if not user.get("is_certified"):
        flash("Only certified teachers can create sessions.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        mongo.db.sessions.insert_one({
            "teacher_id": str(user["_id"]),
            "teacher_name": user["name"],
            "teacher_area": user.get("area", ""),
            "title": request.form["title"],
            "subject": request.form["subject"],
            "description": request.form["description"],
            "area": request.form.get("area", user.get("area", "")),
            "schedule": request.form.get("schedule", "Flexible"),
            "min_bid": int(request.form.get("min_bid", 50)),
            "current_highest_bid": 0,
            "highest_bidder_id": None,
            "bids_count": 0,
            "status": "open",
            "created_at": datetime.utcnow(),
        })
        flash("Session created successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("create_session.html", user=user)


@app.route("/session/<session_id>")
def session_detail(session_id):
    sess = mongo.db.sessions.find_one({"_id": ObjectId(session_id)})
    if not sess:
        flash("Session not found.", "danger")
        return redirect(url_for("skills"))
    bids = list(mongo.db.bids.find({"session_id": session_id}).sort("amount", -1).limit(10))
    # Enrich bids with bidder name
    for bid in bids:
        bidder = mongo.db.users.find_one({"_id": ObjectId(bid["bidder_id"])})
        bid["bidder_name"] = bidder["name"] if bidder else "Unknown"
    user = get_current_user()
    return render_template("Session_detail.html", sess=sess, bids=bids, user=user)


@app.route("/bid/<session_id>", methods=["POST"])
@login_required
def place_bid(session_id):
    user = get_current_user()
    sess = mongo.db.sessions.find_one({"_id": ObjectId(session_id)})

    if not sess or sess["status"] != "open":
        flash("Session is not open for bidding.", "danger")
        return redirect(url_for("skills"))

    if str(user["_id"]) == sess["teacher_id"]:
        flash("You cannot bid on your own session.", "danger")
        return redirect(url_for("session_detail", session_id=session_id))

    if user.get("is_certified"):
        flash("Certified teachers cannot bid on sessions.", "warning")
        return redirect(url_for("session_detail", session_id=session_id))

    amount = int(request.form["amount"])
    min_required = max(sess.get("current_highest_bid", 0) + 1, sess.get("min_bid", 10))

    if amount < min_required:
        flash(f"Bid must be at least {min_required} coins.", "danger")
        return redirect(url_for("session_detail", session_id=session_id))

    if amount > user["coins"]:
        flash("You don't have enough coins.", "danger")
        return redirect(url_for("session_detail", session_id=session_id))

    mongo.db.bids.insert_one({
        "session_id": session_id,
        "bidder_id": str(user["_id"]),
        "bidder_name": user["name"],
        "amount": amount,
        "status": "placed",
        "created_at": datetime.utcnow(),
    })

    mongo.db.sessions.update_one(
        {"_id": ObjectId(session_id)},
        {
            "$set": {
                "current_highest_bid": amount,
                "highest_bidder_id": str(user["_id"]),
            },
            "$inc": {"bids_count": 1},
        }
    )

    flash(f"Bid of {amount} coins placed!", "success")
    return redirect(url_for("session_detail", session_id=session_id))


@app.route("/session/<session_id>/complete", methods=["POST"])
@login_required
def complete_session(session_id):
    user = get_current_user()
    sess = mongo.db.sessions.find_one({"_id": ObjectId(session_id)})

    if not sess or str(user["_id"]) != sess["teacher_id"]:
        flash("Not authorised.", "danger")
        return redirect(url_for("dashboard"))

    mongo.db.sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"status": "completed"}}
    )

    # Reward teacher
    mongo.db.users.update_one({"_id": user["_id"]}, {"$inc": {"coins": 50, "sessions_completed": 1}})

    # Reward highest bidder
    if sess.get("highest_bidder_id"):
        mongo.db.users.update_one(
            {"_id": ObjectId(sess["highest_bidder_id"])},
            {"$inc": {"coins": 100, "sessions_completed": 1}}
        )

    flash("Session marked complete! You earned 50 coins.", "success")
    return redirect(url_for("dashboard"))


# ── Trial ─────────────────────────────────────────────────────────────────────

@app.route("/trial/<session_id>")
@login_required
def trial(session_id):
    user = get_current_user()
    existing = mongo.db.trials.find_one({"user_id": str(user["_id"]), "session_id": session_id})
    if existing:
        flash("You have already used your trial for this session.", "warning")
        return redirect(url_for("session_detail", session_id=session_id))
    mongo.db.trials.insert_one({
        "user_id": str(user["_id"]),
        "session_id": session_id,
        "start_time": datetime.utcnow(),
    })
    return render_template("trial.html")


# ── Leaderboard ───────────────────────────────────────────────────────────────

@app.route("/leaderboard")
def leaderboard():
    selected_area = request.args.get("area", "")
    selected_gender = request.args.get("gender", "")

    filters = {}
    if selected_area:
        filters["area"] = selected_area
    if selected_gender:
        filters["gender"] = selected_gender

    top_users = list(mongo.db.users.find(filters).sort("coins", -1).limit(20))
    areas = mongo.db.users.distinct("area")
    areas = [a for a in areas if a and a not in ("Unknown", "a")]

    return render_template(
        "leaderboard.html",
        top_users=top_users,
        areas=areas,
        selected_area=selected_area,
        selected_gender=selected_gender,
    )


# ── Career ────────────────────────────────────────────────────────────────────

@app.route("/career")
def career():
    skill_tree = {
        "Programming": ["Python", "JavaScript", "Java", "C++", "Flask", "React"],
        "Design": ["UI Basics", "Figma", "UX Research", "Prototyping", "Brand Design"],
        "Business": ["Excel", "Finance", "Marketing", "Product Management", "Strategy"],
        "Data": ["Statistics", "Python", "SQL", "Machine Learning", "Deep Learning"],
        "Languages": ["English", "French", "Spanish", "Japanese", "German"],
    }
    return render_template("career.html", skill_tree=skill_tree)


# ── Heatmap ───────────────────────────────────────────────────────────────────

@app.route("/heatmap")
def heatmap():
    data = list(mongo.db.users.aggregate([
        {
            "$match": {
                "area": {"$nin": ["", "a", None, "Unknown"]},
                "college": {"$nin": ["", "Unknown", None]},
            }
        },
        {
            "$group": {
                "_id": {"area": "$area", "college": "$college"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
    ]))
    return render_template("heatmap.html", data=data)


# ── Rewards ───────────────────────────────────────────────────────────────────

@app.route("/rewards")
@login_required
def rewards():
    user = get_current_user()
    coupons = [
        {"id": 1, "title": "Udemy Course Coupon", "provider": "Udemy", "category": "Programming", "cost": 1000},
        {"id": 2, "title": "Coursera Certificate", "provider": "Coursera", "category": "Data Science", "cost": 2000},
        {"id": 3, "title": "LinkedIn Learning Pass", "provider": "LinkedIn", "category": "Business", "cost": 1500},
        {"id": 4, "title": "Skillshare 1-Month", "provider": "Skillshare", "category": "Design", "cost": 800},
    ]
    transactions = list(mongo.db.transactions.find({"user_id": str(user["_id"])}).sort("created_at", -1).limit(20))
    return render_template("rewards.html", user=user, coupons=coupons, transactions=transactions)


@app.route("/redeem/<int:coupon_id>", methods=["POST"])
@login_required
def redeem_coupon(coupon_id):
    user = get_current_user()
    costs = {1: 1000, 2: 2000, 3: 1500, 4: 800}
    titles = {1: "Udemy Course Coupon", 2: "Coursera Certificate", 3: "LinkedIn Learning Pass", 4: "Skillshare 1-Month"}
    cost = costs.get(coupon_id)
    if not cost:
        flash("Invalid coupon.", "danger")
        return redirect(url_for("rewards"))
    if user["coins"] < cost:
        flash("Not enough coins.", "danger")
        return redirect(url_for("rewards"))
    mongo.db.users.update_one({"_id": user["_id"]}, {"$inc": {"coins": -cost}})
    mongo.db.transactions.insert_one({
        "user_id": str(user["_id"]),
        "type": "spend",
        "reason": f"Redeemed: {titles[coupon_id]}",
        "amount": -cost,
        "created_at": datetime.utcnow(),
    })
    flash(f"Coupon redeemed! Check your email for the code.", "success")
    return redirect(url_for("rewards"))


# ── Admin auth routes ─────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        admin = mongo.db.admins.find_one({"email": request.form["email"].strip().lower()})
        if admin and check_password_hash(admin["password"], request.form["password"]):
            session.clear()
            session["is_admin"] = True
            session["admin_id"] = str(admin["_id"])
            session["admin_name"] = admin["name"]
            flash("Welcome, Admin!", "success")
            return redirect(url_for("admin"))
        flash("Invalid admin credentials.", "danger")
    return render_template("admin_login.html")


@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        if request.form.get("secret_key") != ADMIN_SECRET_KEY:
            flash("Invalid secret key.", "danger")
            return redirect(url_for("admin_register"))
        email = request.form["email"].strip().lower()
        if mongo.db.admins.find_one({"email": email}):
            flash("Admin with this email already exists.", "danger")
            return redirect(url_for("admin_register"))
        mongo.db.admins.insert_one({
            "name": request.form["name"],
            "email": email,
            "password": generate_password_hash(request.form["password"]),
            "created_at": datetime.utcnow(),
        })
        flash("Admin account created. Please log in.", "success")
        return redirect(url_for("admin_login"))
    return render_template("admin_register.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


# ── Admin dashboard ───────────────────────────────────────────────────────────

@app.route("/admin/dashboard")
@admin_required
def admin():
    all_users = list(mongo.db.users.find())
    all_sessions = list(mongo.db.sessions.find())
    pending_certs = list(mongo.db.users.find({"cert_status": "pending"}))
    total_bids = mongo.db.bids.count_documents({})

    # Enrich sessions for table display
    for s in all_sessions:
        s["bids_count"] = s.get("bids_count", 0)

    stats = {
        "total_users": len(all_users),
        "certified_users": sum(1 for u in all_users if u.get("is_certified")),
        "open_sessions": sum(1 for s in all_sessions if s.get("status") == "open"),
        "completed_sessions": sum(1 for s in all_sessions if s.get("status") == "completed"),
        "pending_certs": len(pending_certs),
        "total_bids": total_bids,
    }

    admin_user = {
        "name": session.get("admin_name", "Admin"),
    }

    return render_template(
        "admin.html",
        stats=stats,
        pending_certs=pending_certs,
        all_sessions=all_sessions,
        all_users=all_users,
        admin_user=admin_user,
    )


@app.route("/admin/verify/<user_id>", methods=["POST"])
@admin_required
def verify_certificate(user_id):
    action = request.form.get("action")
    if action == "approve":
        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_certified": True, "cert_status": "approved"}, "$inc": {"coins": 500}}
        )
        flash("Certificate approved. User earned 500 coins.", "success")
    else:
        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"cert_status": "rejected"}}
        )
        flash("Certificate rejected.", "warning")
    return redirect(url_for("admin"))


@app.route("/admin/toggle-certify/<user_id>", methods=["POST"])
@admin_required
def admin_toggle_certify(user_id):
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        new_status = not user.get("is_certified", False)
        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_certified": new_status, "cert_status": "approved" if new_status else "none"}}
        )
        flash(f"User {'certified' if new_status else 'decertified'}.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/delete-session/<session_id>", methods=["POST"])
@admin_required
def admin_delete_session(session_id):
    mongo.db.sessions.delete_one({"_id": ObjectId(session_id)})
    mongo.db.bids.delete_many({"session_id": session_id})
    flash("Session deleted.", "success")
    return redirect(url_for("admin"))


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/coins")
@login_required
def coins():
    user = get_current_user()
    return jsonify({"coins": user.get("coins", 0)})


# ── Legacy / extra ────────────────────────────────────────────────────────────

@app.route("/fusion")
def fusion():
    s1 = request.args.get("s1", "")
    s2 = request.args.get("s2", "")
    fusion_map = {
        ("Python", "Design"): "Data Visualization",
        ("Marketing", "Data"): "Growth Analytics",
    }
    result = fusion_map.get((s1, s2)) or fusion_map.get((s2, s1))
    return jsonify({"fusion": result if result else "None"})


if __name__ == "__main__":
    app.run(debug=True)