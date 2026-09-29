from flask import Flask, render_template, request, jsonify, session, redirect, url_for

import os
import pyodbc
import requests

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from datetime import datetime


load_dotenv()

app = Flask(__name__)

app.secret_key = "college-chatbot-secret-key"

# ==========================================
# FREE WEB SEARCH
# ==========================================
def web_search(query):

    try:

        url = "https://api.duckduckgo.com/"

        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 0
        }

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )

        print("WEB STATUS:", response.status_code)

        if response.status_code != 200:
            return None

        data = response.json()

        # Direct answer
        if data.get("AbstractText"):

            return data["AbstractText"]

        # Related topics
        topics = data.get("RelatedTopics", [])

        results = []

        for topic in topics:

            if isinstance(topic, dict):

                text = topic.get("Text")

                if text:
                    results.append(text)

        if results:

            return "\n\n".join(results[:3])

        return None

    except Exception as e:

        print("WEB SEARCH ERROR:", e)

        return None


# ==========================================
# USER REGISTRATION
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # Password check
        if password != confirm_password:

            return render_template(
                "register.html",
                error="Passwords do not match."
            )

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            # Check existing email
            cursor.execute("""
                SELECT Id
                FROM Users
                WHERE Email = ?
            """, email)

            existing_user = cursor.fetchone()

            if existing_user:

                return render_template(
                    "register.html",
                    error="This email is already registered."
                )

            # Create user
            cursor.execute("""
                INSERT INTO Users
                (Name, Email, Password)
                VALUES (?, ?, ?)
            """,
            name,
            email,
            password)

            connection.commit()

            return redirect(url_for("login"))

        except Exception as e:

            print("REGISTRATION ERROR:", e)

            return render_template(
                "register.html",
                error="Registration failed. Please try again."
            )

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("register.html")

# ==========================================
# USER LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT Id, Name, Email
                FROM Users
                WHERE Email = ?
                AND Password = ?
            """,
            email,
            password)

            user = cursor.fetchone()

            if user:

                session["user_id"] = user[0]
                session["user_name"] = user[1]
                session["user_email"] = user[2]

                return redirect(url_for("home"))

            return render_template(
                "student_login.html",
                error="Invalid email or password."
            )

        except Exception as e:

            print("LOGIN ERROR:", e)

            return render_template(
                "student_login.html",
                error="Database connection error."
            )

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("student_login.html")

@app.route("/logout")
def logout():

    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("user_email", None)

    return redirect(url_for("login"))

# ==========================================
# ADMIN LOGIN
# ==========================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                SELECT Id, Username
                FROM Admins
                WHERE Username = ?
                AND Password = ?
            """, username, password)

            admin = cursor.fetchone()

            if admin:

                session["admin_id"] = admin[0]
                session["admin_username"] = admin[1]

                return redirect(url_for("admin_dashboard"))

            return render_template(
                "login.html",
                error="Invalid username or password."
            )

        except Exception as e:

            print("LOGIN ERROR:", e)

            return render_template(
                "login.html",
                error="Database connection error."
            )

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("login.html")


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route("/admin")
def admin_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        # FAQs
        cursor.execute("SELECT COUNT(*) FROM FAQs")
        total_faqs = cursor.fetchone()[0]

        # Total Chats
        cursor.execute("SELECT COUNT(*) FROM ChatHistory")
        total_chats = cursor.fetchone()[0]

        # Total Admins
        cursor.execute("SELECT COUNT(*) FROM Admins")
        total_admins = cursor.fetchone()[0]

        # Recent Chat History
        cursor.execute("""
            SELECT TOP 10
                Id,
                UserMessage,
                BotResponse,
                CreatedAt
            FROM ChatHistory
            ORDER BY Id DESC
        """)

        chats = cursor.fetchall()

        # FAQs
        cursor.execute("""
            SELECT
                Id,
                Question,
                Answer,
                Category,
                Keywords
            FROM FAQs
            ORDER BY Id DESC
        """)

        faqs = cursor.fetchall()

        return render_template(
            "admin.html",
            faqs=faqs,
            chats=chats,
            total_faqs=total_faqs,
            total_chats=total_chats,
            total_admins=total_admins,
            username=session.get("admin_username")
        )

    except Exception as e:

        print("ADMIN DASHBOARD ERROR:", e)

        return "Database error."

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# ADD FAQ
# ==========================================

@app.route("/admin/add", methods=["POST"])
def add_faq():

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    question = request.form.get("question")
    answer = request.form.get("answer")
    category = request.form.get("category")
    keywords = request.form.get("keywords")

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO FAQs
        (Question, Answer, Category, Keywords)
        VALUES (?, ?, ?, ?)
    """,
    question,
    answer,
    category,
    keywords)

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("admin_dashboard"))


# ==========================================
# DELETE FAQ
# ==========================================

@app.route("/admin/delete/<int:faq_id>", methods=["POST"])
def delete_faq(faq_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM FAQs WHERE Id = ?",
        faq_id
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("admin_dashboard"))

# ==========================================
# EDIT FAQ
# ==========================================

@app.route("/admin/edit/<int:faq_id>", methods=["GET", "POST"])
def edit_faq(faq_id):

    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        if request.method == "POST":

            question = request.form.get("question")
            answer = request.form.get("answer")
            category = request.form.get("category")
            keywords = request.form.get("keywords")

            cursor.execute("""
                UPDATE FAQs
                SET Question = ?,
                    Answer = ?,
                    Category = ?,
                    Keywords = ?
                WHERE Id = ?
            """,
            question,
            answer,
            category,
            keywords,
            faq_id)

            connection.commit()

            return redirect(url_for("admin_dashboard"))

        cursor.execute("""
            SELECT Id, Question, Answer, Category, Keywords
            FROM FAQs
            WHERE Id = ?
        """, faq_id)

        faq = cursor.fetchone()

        if not faq:
            return "FAQ not found."

        return render_template(
            "edit_faq.html",
            faq=faq
        )

    except Exception as e:

        print("EDIT ERROR:", e)

        return "Database error."

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

# ==========================================
# LOGOUT
# ==========================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(url_for("admin_login"))


# ==========================================
# SQL SERVER DATABASE CONNECTION
# ==========================================

def get_db_connection():

    connection = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={os.getenv('DB_SERVER')};"
        f"DATABASE={os.getenv('DB_NAME')};"
        f"UID={os.getenv('DB_USER')};"
        f"PWD={os.getenv('DB_PASSWORD')};"
        "TrustServerCertificate=yes;"
    )

    return connection



# ==========================================
# TEST DATABASE CONNECTION
# ==========================================

@app.route("/test-db")
def test_db():

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute("SELECT 1")

        result = cursor.fetchone()

        cursor.close()
        connection.close()

        return "Database connected successfully! ✅"

    except Exception as e:

        return f"Database connection failed: {str(e)}"


# ==========================================
# HOME PAGE
# ==========================================



# ==========================================
# CHATBOT
# ==========================================

@app.route("/chat", methods=["POST"])
def chat():

    connection = None
    cursor = None

    try:

        data = request.get_json()
        message = data.get("message", "").strip()

        if not message:
            return jsonify({
                "reply": "Please apna question type karein."
            })

        # ==========================================
        # DATABASE CONNECTION
        # ==========================================

        connection = get_db_connection()
        cursor = connection.cursor()

        message_lower = message.lower().strip()

        # ==========================================
        # GREETINGS
        # ==========================================

        greetings = [
            "hi",
            "hii",
            "hello",
            "hey",
            "good morning",
            "good afternoon",
            "good evening"
        ]

        if message_lower in greetings:

            bot_response = (
                "Hello! 👋<br><br>"
                "Welcome to the <b>AI College Assistant</b>.<br><br>"
                "How can I help you today?"
            )

        # ==========================================
        # CURRENT TIME
        # ==========================================

        elif any(word in message_lower for word in [
            "time",
            "what time",
            "current time",
            "abhi kitna time",
            "abhi ka time",
            "samay"
        ]):

            current_time = datetime.now().strftime("%I:%M %p")

            bot_response = (
                f"🕐 Abhi ka time hai "
                f"<b>{current_time}</b>."
            )

        # ==========================================
        # CURRENT DATE / DAY
        # ==========================================

        elif any(word in message_lower for word in [
            "today",
            "aaj",
            "aaj ka din",
            "which day",
            "what day",
            "kon sa din",
            "kaunsa din",
            "kaun sa din"
        ]):

            current_date = datetime.now()

            day_name = current_date.strftime("%A")
            date = current_date.strftime("%d %B %Y")

            bot_response = (
                f"📅 Aaj <b>{day_name}</b> hai.<br>"
                f"Date: <b>{date}</b>"
            )

        else:

            # ==========================================
            # CONVERT QUESTION INTO WORDS
            # ==========================================

            words = (
                message_lower
                .replace("?", "")
                .replace(",", "")
                .replace(".", "")
                .split()
            )

            stop_words = {
                "me",
                "mai",
                "mujhe",
                "hai",
                "hain",
                "ka",
                "ke",
                "ki",
                "kya",
                "ko",
                "se",
                "par",
                "aur",
                "batao",
                "baare",
                "the",
                "is",
                "a",
                "an"
            }

            keywords = [
                word
                for word in words
                if len(word) >= 3
                and word not in stop_words
            ]

            # ==========================================
            # GET FAQ DATA
            # ==========================================

            cursor.execute("""
                SELECT
                    Id,
                    Question,
                    Answer,
                    Category,
                    Keywords
                FROM FAQs
            """)

            faqs = cursor.fetchall()

            best_faq = None
            best_score = 0

            # ==========================================
            # FIND BEST FAQ
            # ==========================================

            for faq in faqs:

                question = str(faq[1]).lower()
                category = str(faq[3]).lower()
                faq_keywords = str(faq[4]).lower()

                score = 0

                for word in keywords:

                    if word in faq_keywords:
                        score += 3

                    if word in question:
                        score += 2

                    if word in category:
                        score += 4

                if score > best_score:

                    best_score = score
                    best_faq = faq

            # ==========================================
            # COLLEGE FAQ ANSWER
            # ==========================================

            if best_faq and best_score > 0:

                bot_response = best_faq[2]

            else:

                # ==========================================
                # REAL-TIME WEB SEARCH
                # ==========================================

                web_result = web_search(message)

                if web_result:

                    bot_response = (
                        "🌐 <b>Real-time information:</b>"
                        "<br><br>"
                        + web_result.replace(
                            "\n",
                            "<br><br>"
                        )
                    )

                else:

                    bot_response = """
                    Sorry 😕, mujhe is question ka answer
                    database ya web search se nahi mila.

                    Aap in topics ke baare me pooch sakte hain:

                    <br>🎓 Admission
                    <br>💰 Fees
                    <br>📚 Library
                    <br>📝 Exam
                    <br>👨‍🎓 Attendance
                    <br>🏠 Hostel
                    <br>💻 IT Department
                    """

        # ==========================================
        # SAVE CHAT HISTORY
        # ==========================================

        if "user_id" in session:

            cursor.execute("""
                INSERT INTO ChatHistory
                (
                    UserId,
                    UserMessage,
                    BotResponse
                )
                VALUES (?, ?, ?)
            """,
            session["user_id"],
            message,
            bot_response)

            connection.commit()

        # ==========================================
        # SEND RESPONSE
        # ==========================================

        return jsonify({
            "reply": bot_response
        })

    except Exception as e:

        print("CHAT ERROR:", e)

        return jsonify({
            "reply": "Database ya web search me problem aa gayi hai."
        })

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

@app.route("/")
def home():

    return render_template(
        "index.html",
        user_name=session.get("user_name")
    )


# ==========================================
# History Page
# ==========================================
@app.route("/history")
def history():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                UserMessage,
                BotResponse,
                CreatedAt
            FROM ChatHistory
            WHERE UserId = ?
            ORDER BY Id DESC
        """, session["user_id"])

        chats = cursor.fetchall()

        return render_template(
            "history.html",
            chats=chats,
            user_name=session.get("user_name")
        )

    except Exception as e:

        print("HISTORY ERROR:", e)

        return "Unable to load chat history."

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# RUN SERVER
# ==========================================

if __name__ == "__main__":

    app.run(debug=True)
