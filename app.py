import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_key_123')

# 1. AI Configuration (Defined globally)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# Using gemini-1.5-flash (Ensure library is updated)
model = genai.GenerativeModel('gemini-flash-latest') 

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            database=os.getenv('MYSQL_DB', 'career_pulse')
        )
        return connection
    except Error as e:
        print(f"CRITICAL: Database connection failed! Error: {e}")
        return None

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        full_name = request.form['full_name']
        education = request.form['education']
        goal = request.form['goal']
        interest = request.form['interest']
        skills = request.form['skills']

        conn = get_db_connection()
        
        # FIX: Check if conn is None BEFORE calling cursor()
        if conn is None:
            flash("Database Error: Check if MySQL is running.", "danger")
            return render_template('register.html')

        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, password, full_name, education, goal, interest, skills) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, password, full_name, education, goal, interest, skills))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Username already exists!', 'danger')
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')


@app.context_processor
def inject_user():
    return dict(is_logged_in='user_id' in session)

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if conn is None:
            flash("Database Error: Check if MySQL is running.", "danger")
            return render_template('login.html')
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn is None:
        flash("Database Error: Check if MySQL is running.", "danger")
        return redirect(url_for('login'))

    cursor = conn.cursor(dictionary=True)

    # Auto-mark goals as missed when their target_date has passed
    try:
        today = datetime.now().date()
        cursor.execute(
            """
            UPDATE goals SET status='missed'
            WHERE user_id = %s AND status = 'pending' AND target_date < %s
            """,
            (session['user_id'], today)
        )
        conn.commit()
    except Exception:
        # non-fatal: continue to fetch data
        pass

    # Fetch user details
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user_data = cursor.fetchone()

    # Fetch goals
    cursor.execute("SELECT * FROM goals WHERE user_id = %s ORDER BY target_date ASC", (session['user_id'],))
    goals = cursor.fetchall()

    # Fetch recent advice history (last 5)
    cursor.execute("SELECT * FROM advice_history WHERE user_id = %s ORDER BY created_at DESC LIMIT 5", (session['user_id'],))
    advice_history = cursor.fetchall()

    cursor.close()
    conn.close()
    
    today = datetime.now().date()
    return render_template('dashboard.html', user=user_data, goals=goals, advice_history=advice_history, today=today)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        full_name = request.form['full_name']
        education = request.form['education']
        goal = request.form['goal']
        interest = request.form['interest']
        skills = request.form['skills']
        
        cursor.execute("""
            UPDATE users SET full_name=%s, education=%s, goal=%s, interest=%s, skills=%s
            WHERE id=%s
        """, (full_name, education, goal, interest, skills, session['user_id']))
        conn.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('profile.html', user=user_data)

@app.route('/add_goal', methods=['POST'])
def add_goal():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    title = request.form['title']
    target_date = request.form['target_date']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO goals (user_id, title, target_date) VALUES (%s, %s, %s)",
                   (session['user_id'], title, target_date))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Goal added successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/update_goal/<int:goal_id>/<string:status>', methods=['POST'])
def update_goal(goal_id, status):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if status not in ['achieved', 'missed']:
        return jsonify({'error': 'Invalid status'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE goals SET status=%s WHERE id=%s AND user_id=%s", 
                   (status, goal_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'success': True})


@app.route('/delete_advice/<int:advice_id>', methods=['POST'])
def delete_advice(advice_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    # Ensure user can only delete their own advice history
    cursor.execute("DELETE FROM advice_history WHERE id=%s AND user_id=%s", (advice_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'success': True})


@app.route('/ai_guidance', methods=['GET', 'POST'])
def ai_guidance():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    response_text = ""
    
    if request.method == 'POST':
        query = request.form.get('query', '')
        length = request.form.get('length', 'Medium')
        
        conn = get_db_connection()
        if conn is None:
            return "Database connection failed. Ensure MySQL is running.", 500
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        # Fetch user's goals with status breakdown
        cursor.execute("""
            SELECT title, status FROM goals 
            WHERE user_id = %s
            ORDER BY target_date DESC
        """, (session['user_id'],))
        goals = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Build goal statistics
        pending_goals = [g['title'] for g in goals if g['status'] == 'pending']
        achieved_goals = [g['title'] for g in goals if g['status'] == 'achieved']
        missed_goals = [g['title'] for g in goals if g['status'] == 'missed']
        
        # Format goals for prompt
        goals_context = f"""
User's Goal Progress:
- Completed Goals ({len(achieved_goals)}): {', '.join(achieved_goals) if achieved_goals else 'None yet'}
- Pending Goals ({len(pending_goals)}): {', '.join(pending_goals) if pending_goals else 'None'}
- Missed Goals ({len(missed_goals)}): {', '.join(missed_goals) if missed_goals else 'None'}
        """
        
        prompt = f"""
        Act as a professional career coach. 
        User: {user['full_name']}, Edu: {user['education']}, Skills: {user['skills']}
        
        {goals_context}
        
        Question: {query}
        
        Provide {length} advice tailored to their goal progress and career profile.
        """
        
        try:
            # 1️⃣ Generate FULL AI response (shown to user)
            response = model.generate_content(prompt)
            response_text = response.text

            # 2️⃣ Generate SUMMARY for dashboard storage
            summary_prompt = f"""
            Summarize the following career advice in short bullet points.
            Keep it concise and dashboard-friendly.

            Advice:
            {response_text}
            """

            summary_response = model.generate_content(summary_prompt)
            summary_text = summary_response.text

            # 3️⃣ Store ONLY summary in database
            conn = get_db_connection()
            if conn is not None:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO advice_history (user_id, query, summary, length)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (session['user_id'], query, summary_text, length)
                )
                conn.commit()
                cursor.close()
                conn.close()
        except Exception as e:
            # Check for 404 specifically
            response_text = f"AI Error: {str(e)}. Tip: Try running 'pip install -U google-generativeai' in your terminal."

    return render_template('ai_guidance.html', response=response_text)


@app.route('/discussions', methods=['GET', 'POST'])
def discussions():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash('Database Error', 'danger')
        return redirect(url_for('dashboard'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        title = request.form.get('title')
        body = request.form.get('body')
        username = session.get('username')
        full_name = session.get('full_name')

        cursor.execute(
            "INSERT INTO discussions (user_id, username, full_name, title, body) VALUES (%s, %s, %s, %s, %s)",
            (session['user_id'], username, full_name, title, body)
        )
        conn.commit()
        # refresh listing after post
        return redirect(url_for('discussions'))

    # fetch discussions and replies
    cursor.execute("SELECT * FROM discussions ORDER BY created_at DESC LIMIT 50")
    discussions = cursor.fetchall()

    # fetch replies for all fetched discussions
    disc_ids = [d['id'] for d in discussions] if discussions else []
    replies_map = {}
    if disc_ids:
        format_ids = ','.join(['%s'] * len(disc_ids))
        cursor.execute(f"SELECT * FROM discussion_replies WHERE discussion_id IN ({format_ids}) ORDER BY created_at ASC", tuple(disc_ids))
        replies = cursor.fetchall()

        # organize replies by discussion and parent
        for r in replies:
            replies_map.setdefault(r['discussion_id'], []).append(r)

    # build nested replies per discussion
    def nest_replies(flat):
        by_id = {r['id']: dict(r, replies=[]) for r in (flat or [])}
        roots = []
        for r in (flat or []):
            pid = r['parent_id']
            if pid and pid in by_id:
                by_id[pid]['replies'].append(by_id[r['id']])
            else:
                roots.append(by_id[r['id']])
        return roots

    for d in discussions:
        d['replies'] = nest_replies(replies_map.get(d['id']))

    cursor.close()
    conn.close()
    return render_template('discussions.html', discussions=discussions)


@app.route('/discussions/reply', methods=['POST'])
def post_reply():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    discussion_id = request.form.get('discussion_id')
    parent_id = request.form.get('parent_id')
    body = request.form.get('body')
    username = session.get('username')
    full_name = session.get('full_name')

    # Convert "0" (direct reply to discussion) to None (NULL in DB)
    parent_id = None if parent_id in ['0', ''] else parent_id

    conn = get_db_connection()
    if conn is None:
        flash('Database Error', 'danger')
        return redirect(url_for('discussions'))

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO discussion_replies (discussion_id, parent_id, user_id, username, full_name, body) VALUES (%s, %s, %s, %s, %s, %s)",
        (discussion_id, parent_id, session['user_id'], username, full_name, body)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('discussions'))


@app.route('/discussions/<int:discussion_id>/delete', methods=['POST'])
def delete_discussion(discussion_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash('Database Error', 'danger')
        return redirect(url_for('discussions'))

    cursor = conn.cursor(dictionary=True)
    
    # Verify user owns this discussion
    cursor.execute("SELECT user_id FROM discussions WHERE id = %s", (discussion_id,))
    discussion = cursor.fetchone()
    
    if not discussion or discussion['user_id'] != session['user_id']:
        flash('Unauthorized', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('discussions'))

    # Delete discussion (cascades to replies via foreign key)
    cursor.execute("DELETE FROM discussions WHERE id = %s", (discussion_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Discussion deleted successfully', 'success')
    return redirect(url_for('discussions'))


@app.route('/discussions/reply/<int:reply_id>/delete', methods=['POST'])
def delete_reply(reply_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash('Database Error', 'danger')
        return redirect(url_for('discussions'))

    cursor = conn.cursor(dictionary=True)
    
    # Verify user owns this reply
    cursor.execute("SELECT user_id, discussion_id FROM discussion_replies WHERE id = %s", (reply_id,))
    reply = cursor.fetchone()
    
    if not reply or reply['user_id'] != session['user_id']:
        flash('Unauthorized', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('discussions'))

    # Delete this reply and all its nested replies (child replies that reference this as parent)
    cursor.execute("DELETE FROM discussion_replies WHERE id = %s OR parent_id = %s", (reply_id, reply_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Reply deleted successfully', 'success')
    return redirect(url_for('discussions'))


@app.route('/api/goals')
def api_goals():
    if 'user_id' not in session:
        return jsonify([])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Auto-mark missed goals where date passed
    try:
        today = datetime.now().date()
        cursor.execute(
            """
            UPDATE goals SET status='missed'
            WHERE user_id = %s AND status = 'pending' AND target_date < %s
            """,
            (session['user_id'], today)
        )
        conn.commit()
    except Exception:
        pass

    cursor.execute("""
        SELECT id, title, target_date, status
        FROM goals
        WHERE user_id = %s
    """, (session['user_id'],))

    goals = cursor.fetchall()
    cursor.close()
    conn.close()

    events = []
    today = datetime.now().date()

    for g in goals:
        # Color mapping: missed=red, achieved=green, pending=yellow
        if g['status'] == 'missed':
            color = '#ef4444'  # red
        elif g['status'] == 'achieved':
            color = '#10b981'  # green
        else:
            color = '#f59e0b'  # yellow (pending)

        events.append({
            "title": g['title'],
            "start": g['target_date'].isoformat(),
            "color": color
        })

    return jsonify(events)


if __name__ == '__main__':
    app.run(debug=True)
