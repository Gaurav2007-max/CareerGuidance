# CareerPulse - Complete Code Archive
**Date:** February 10, 2026  
**All application code consolidated into one file**

---

## TABLE OF CONTENTS
1. app.py (Flask Backend)
2. static/script.js
3. static/style.css
4. templates/base.html
5. templates/index.html
6. templates/login.html
7. templates/register.html
8. templates/dashboard.html
9. templates/profile.html
10. templates/ai_guidance.html
11. templates/discussions.html

---

## 1. app.py (Flask Backend)

```python
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
```

---

## 2. static/script.js

```javascript
document.addEventListener('DOMContentLoaded', () => {
    // Dark Mode Toggle
    const darkModeToggle = document.getElementById('darkModeToggle');
    const htmlElement = document.documentElement;
    
    // Check for saved dark mode preference or default to light mode
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    if (isDarkMode) {
        document.body.classList.add('dark-mode');
        darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    }
    
    darkModeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        const isNowDarkMode = document.body.classList.contains('dark-mode');
        localStorage.setItem('darkMode', isNowDarkMode);
        
        // Update icon
        if (isNowDarkMode) {
            darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
        } else {
            darkModeToggle.innerHTML = '<i class="fas fa-moon"></i>';
        }
    });

    // Handle Goal Status Updates via AJAX
    const actionButtons = document.querySelectorAll('.goal-action');
    actionButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const goalId = btn.dataset.id;
            const status = btn.dataset.status;
            
            try {
                const response = await fetch(`/update_goal/${goalId}/${status}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    location.reload(); // Refresh to update charts and lists
                } else {
                    alert('Failed to update goal status.');
                }
            } catch (err) {
                console.error('Error:', err);
            }
        });
    });

    // Charting Logic (if on dashboard)
    const ctx = document.getElementById('statsChart');
    if (ctx) {
        const achievedCount = parseInt(ctx.dataset.achieved);
        const missedCount = parseInt(ctx.dataset.missed);
        const pendingCount = parseInt(ctx.dataset.pending);

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Achieved', 'Missed', 'Pending'],
                datasets: [{
                    data: [achievedCount, missedCount, pendingCount],
                    backgroundColor: ['#10b981', '#ef4444', '#f59e0b'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    // Dynamic AI Prompt Length Visual
    const aiForm = document.getElementById('aiForm');
    if (aiForm) {
        aiForm.addEventListener('submit', () => {
            const btn = aiForm.querySelector('button');
            btn.innerHTML = 'AI thinking... <span class="loader"></span>';
            btn.disabled = true;
        });
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('goalCalendar');
    if (!calendarEl) return;

    // Set minimum height for calendar container
    calendarEl.style.minHeight = '500px';

    fetch('/api/goals')
        .then(res => res.json())
        .then(events => {
            if (!window.FullCalendar) {
                console.error('FullCalendar not loaded');
                return;
            }
            const calendar = new FullCalendar.Calendar(calendarEl, {
                initialView: 'dayGridMonth',
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,listMonth'
                },
                contentHeight: 'auto',
                events: events,
                eventDisplay: 'block'
            });
            calendar.render();
        })
        .catch(err => console.error('Failed to load goals:', err));
});

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.reply-link').forEach(a => {
        a.addEventListener('click', (e) => {
            e.preventDefault();
            const disc = a.dataset.discussion;
            const reply = a.dataset.reply;
            const formId = `reply-form-${disc}-${reply}`;
            const form = document.getElementById(formId);
            
            if (form) {
                // Toggle visibility and scroll into view
                if (form.style.display === 'none') {
                    form.style.display = 'block';
                    form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    form.querySelector('textarea').focus();
                } else {
                    form.style.display = 'none';
                }
            }
        });
    });
});
```

---

## 3. static/style.css

```css
:root {
  --primary-color: #4f46e5;
  --secondary-color: #06b6d4;
  --danger-color: #ef4444;
  --success-color: #22c55e;
  --bg-color: #f9fafb;
  --text-color: #1f2937;
  --card-bg: #ffffff;
  --border-color: #d1d5db;
  --border-radius: 10px;
  --shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  --transition: all 0.3s ease;
  --font-main: 'Inter', sans-serif;
}

body.dark-mode {
  --bg-color: #1f2937;
  --text-color: #f9fafb;
  --card-bg: #374151;
  --border-color: #4b5563;
  --shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

/* Global Reset */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-main);
  background: var(--bg-color);
  color: var(--text-color);
  line-height: 1.6;
  min-height: 100vh;
}

/* Navigation */
nav {
  background: var(--card-bg);
  box-shadow: var(--shadow);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  position: sticky;
  top: 0;
  z-index: 100;
}

nav .logo {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--primary-color);
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

nav ul {
  list-style: none;
  display: flex;
  gap: 1.5rem;
}

nav ul li a {
  text-decoration: none;
  color: var(--text-color);
  font-weight: 500;
  transition: var(--transition);
}

nav ul li a:hover {
  color: var(--primary-color);
}

.dark-mode-toggle {
  background: none;
  border: none;
  color: var(--text-color);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0.5rem;
  transition: var(--transition);
  border-radius: 50%;
}

.dark-mode-toggle:hover {
  background: var(--bg-color);
  color: var(--primary-color);
}

body.dark-mode .dark-mode-toggle i::before {
  content: '\f185';
}

/* Container */
.container {
  max-width: 1100px;
  margin: 2rem auto;
  padding: 0 1rem;
}

/* Alerts */
.alert {
  padding: 1rem;
  border-radius: var(--border-radius);
  margin-bottom: 1rem;
  font-weight: 500;
}

.alert-success {
  background: #dcfce7;
  color: #166534;
}

.alert-danger {
  background: #fee2e2;
  color: #991b1b;
}

/* Hero Section */
.hero {
  text-align: center;
  padding: 4rem 1rem;
  background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
  color: white;
  border-radius: var(--border-radius);
  box-shadow: var(--shadow);
}

.hero h1 {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.hero p {
  font-size: 1.1rem;
  opacity: 0.9;
}

/* Buttons */
.btn {
  display: inline-block;
  padding: 0.7rem 1.4rem;
  border-radius: var(--border-radius);
  border: none;
  cursor: pointer;
  font-weight: 600;
  text-decoration: none;
  transition: var(--transition);
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover {
  background: #4338ca;
}

.btn-secondary {
  background: var(--secondary-color);
  color: white;
}

.btn-secondary:hover {
  background: #0891b2;
}

.btn-danger {
  background: var(--danger-color);
  color: white;
}

.btn-danger:hover {
  background: #dc2626;
}

/* Cards */
.card {
  background: var(--card-bg);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  transition: var(--transition);
}

.card:hover {
  transform: translateY(-3px);
}

.card h2, .card h3 {
  color: var(--primary-color);
  margin-bottom: 0.8rem;
}

/* Forms */
.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.4rem;
}

input[type="text"],
input[type="password"],
input[type="date"],
textarea,
select {
  width: 100%;
  padding: 0.7rem;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  font-size: 1rem;
  transition: var(--transition);
  background: var(--card-bg);
  color: var(--text-color);
}

input:focus,
textarea:focus,
select:focus {
  border-color: var(--primary-color);
  outline: none;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2);
}

/* Grid Layout */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}

/* Goals */
.goal-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f3f4f6;
  padding: 1rem;
  border-radius: var(--border-radius);
  margin-bottom: 0.8rem;
}

body.dark-mode .goal-item {
  background: #4b5563;
}

.goal-info h4 {
  margin-bottom: 0.3rem;
}

.goal-info h4.strikethrough {
  text-decoration: line-through;
  color: #9ca3af;
}

.goal-date {
  font-size: 0.9rem;
  color: #6b7280;
}

.status-badge {
  padding: 0.3rem 0.7rem;
  border-radius: 20px;
  font-size: 0.8rem;
  text-transform: capitalize;
  font-weight: 600;
}

.status-badge.pending {
  background: #fef9c3;
  color: #854d0e;
}

.status-badge.achieved {
  background: #dcfce7;
  color: #166534;
}

.status-badge.missed {
  background: #fee2e2;
  color: #991b1b;
}

/* AI Output */
.ai-output {
  background: #f9fafb;
  border-left: 4px solid var(--primary-color);
  padding: 1rem;
  border-radius: var(--border-radius);
  margin-top: 1.5rem;
  white-space: pre-wrap;
}

body.dark-mode .ai-output {
  background: #4b5563;
}

/* Advice History */
.advice-history ul {
  list-style: disc;
  padding-left: 1.5rem;
}

.advice-history li {
  margin-bottom: 1rem;
}

/* Chart Canvas */
canvas {
  width: 100% !important;
  height: 250px !important;
}

/* FullCalendar Styling */
#goalCalendar {
  width: 100%;
  min-height: 500px;
}

.fc {
  font-family: var(--font-main);
}

.fc .fc-button-primary {
  background-color: var(--primary-color);
  border-color: var(--primary-color);
}

.fc .fc-button-primary:not(:disabled).fc-button-active,
.fc .fc-button-primary:not(:disabled):hover {
  background-color: var(--secondary-color);
  border-color: var(--secondary-color);
}

.fc .fc-daygrid-day.fc-day-other {
  background-color: #f3f4f6;
}

.fc .fc-col-header-cell {
  background-color: #f3f4f6;
  border-color: #e5e7eb;
}

.fc .fc-daygrid-day {
  border-color: #e5e7eb;
}

body.dark-mode .fc .fc-daygrid-day {
  border-color: var(--border-color);
  background-color: var(--card-bg);
}

body.dark-mode .fc .fc-daygrid-day.fc-day-other {
  background-color: #4b5563;
}

body.dark-mode .fc .fc-col-header-cell {
  background-color: #4b5563;
  border-color: var(--border-color);
}

body.dark-mode .fc {
  color: var(--text-color);
}

.fc-event {
  border-radius: 4px;
}

/* Responsive */
@media (max-width: 768px) {
  nav ul {
    flex-direction: column;
    gap: 1rem;
  }

  .hero h1 {
    font-size: 2rem;
  }

  .container {
    padding: 0 1rem;
  }
}
```

---

## 4. templates/base.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CareerPulse | AI Career Coach</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.css" rel="stylesheet">

</head>
<body>
    <nav>
        <a href="/" class="logo"><i class="fas fa-rocket"></i> CareerPulse</a>
        <ul>
            {% if is_logged_in %}
                <li><a href="{{ url_for('dashboard') }}">Dashboard</a></li>
                <li><a href="{{ url_for('ai_guidance') }}">AI Coach</a></li>
                <li><a href="{{ url_for('profile') }}">Profile</a></li>
                <li><a href="{{ url_for('discussions') }}">Discussions</a></li>
                <li><a href="{{ url_for('logout') }}"><i class="fas fa-sign-out-alt"></i></a></li>
            {% else %}
                <li><a href="{{ url_for('login') }}">Login</a></li>
                <li><a href="{{ url_for('register') }}">Register</a></li>
            {% endif %}
            <li><button id="darkModeToggle" class="dark-mode-toggle" title="Toggle Dark Mode"><i class="fas fa-moon"></i></button></li>
        </ul>
    </nav>

    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.js"></script>
    <script src="{{ url_for('static', filename='script.js') }}"></script>

</body>
</html>
```

---

## 5. templates/index.html

```html
{% extends 'base.html' %}
{% block content %}
<div class="hero">
    <h1>Welcome to CareerPulse</h1>
    <p>Your AI-powered Career Coach & Goal Tracking Companion</p>
    <div style="margin-top: 2rem;">
        <a href="{{ url_for('login') }}" class="btn btn-primary" style="margin-right: 1rem;">Login</a>
        <a href="{{ url_for('register') }}" class="btn btn-secondary">Get Started</a>
    </div>
</div>

<div class="grid" style="margin-top: 3rem;">
    <div class="card">
        <h3><i class="fas fa-gauge"></i> Track Goals</h3>
        <p>Set career milestones, track progress, and celebrate achievements with an interactive calendar.</p>
    </div>
    <div class="card">
        <h3><i class="fas fa-brain"></i> AI Coaching</h3>
        <p>Get personalized career advice powered by Google's Gemini AI, tailored to your profile.</p>
    </div>
    <div class="card">
        <h3><i class="fas fa-users"></i> Community</h3>
        <p>Join discussions, share experiences, and learn from other career-focused professionals.</p>
    </div>
</div>
{% endblock %}
```

---

## 6. templates/login.html

```html
{% extends 'base.html' %}
{% block content %}
<div class="grid">
    <div style="grid-column: 1; min-height: auto;">
    </div>
    <div class="card" style="grid-column: 2;">
        <h2 style="text-align: center;">Login to CareerPulse</h2>
        <form method="POST" style="margin-top: 1.5rem;">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 1rem;">Login</button>
        </form>
        <p style="text-align: center; margin-top: 1rem;">Don't have an account? <a href="{{ url_for('register') }}">Register here</a></p>
    </div>
    <div style="grid-column: 3; min-height: auto;">
    </div>
</div>
{% endblock %}
```

---

## 7. templates/register.html

```html
{% extends 'base.html' %}
{% block content %}
<div class="grid">
    <div class="card" style="grid-column: span 3;">
        <h2 style="text-align: center;">Register for CareerPulse</h2>
        <form method="POST" style="margin-top: 1.5rem;">
            <div class="form-group">
                <label>Full Name</label>
                <input type="text" name="full_name" required>
            </div>
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <div class="form-group">
                <label>Education Level</label>
                <select name="education" required>
                    <option value="">-- Select --</option>
                    <option value="High School">High School</option>
                    <option value="Bachelor's">Bachelor's Degree</option>
                    <option value="Master's">Master's Degree</option>
                    <option value="PhD">PhD</option>
                </select>
            </div>
            <div class="form-group">
                <label>Career Goal</label>
                <input type="text" name="goal" placeholder="e.g. Become a Full Stack Developer" required>
            </div>
            <div class="form-group">
                <label>Interests</label>
                <input type="text" name="interest" placeholder="e.g. Web Development, AI/ML" required>
            </div>
            <div class="form-group">
                <label>Current Skills</label>
                <input type="text" name="skills" placeholder="e.g. Python, JavaScript, React" required>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%;">Register</button>
        </form>
        <p style="text-align: center; margin-top: 1rem;">Already have an account? <a href="{{ url_for('login') }}">Login here</a></p>
    </div>
</div>
{% endblock %}
```

---

## 8. templates/dashboard.html

```html
{% extends 'base.html' %}
{% block content %}
<div class="grid">
    <div class="card" style="grid-column: span 2;">
        <h2>Welcome, {{ user.full_name }}!</h2>
        <p><strong>Your Current Goal:</strong> {{ user.goal }}</p>
        <p><strong>Skills:</strong> {{ user.skills }}</p>
    </div>

    <div class="card">
        <h3>Progress Overview</h3>
        <canvas id="statsChart" 
            data-achieved="{{ goals|selectattr('status', 'equalto', 'achieved')|list|length }}"
            data-missed="{{ goals|selectattr('status', 'equalto', 'missed')|list|length }}"
            data-pending="{{ goals|selectattr('status', 'equalto', 'pending')|list|length }}">
        </canvas>
    </div>
</div>

<div class="grid">
    <div class="card">
        <h3><i class="fas fa-plus-circle"></i> Add New Goal</h3>
        <form action="{{ url_for('add_goal') }}" method="POST" style="margin-top: 1rem;">
            <div class="form-group">
                <label>Goal Title</label>
                <input type="text" name="title" placeholder="e.g. Complete AWS Certification" required>
            </div>
            <div class="form-group">
                <label>Target Date</label>
                <input type="date" name="target_date" required>
            </div>
            <button type="submit" class="btn btn-secondary" style="width: 100%;">Set Goal</button>
        </form>
    </div>

    <!-- MY GOALS -->
    <div class="card" style="grid-column: span 2;">
        <h3>My Goals</h3>
        <div class="goals-list" style="margin-top: 1rem;">
            {% for goal in goals %}
            <div class="goal-item">
                <div class="goal-info">
                    <h4 class="{% if goal.status != 'pending' %}strikethrough{% endif %}">
                        {{ goal.title }}
                    </h4>
                    <span class="goal-date">Deadline: {{ goal.target_date }}</span>
                    <span class="status-badge {{ goal.status }}">
                        {{ goal.status }}
                    </span>
                </div>

                {% if goal.status == 'pending' %}
                <div class="goal-actions">
                    <button class="btn btn-secondary goal-action"
                            data-id="{{ goal.id }}"
                            data-status="achieved"
                            title="Mark as Achieved">
                        <i class="fas fa-check"></i>
                    </button>
                    <button class="btn btn-danger goal-action"
                            data-id="{{ goal.id }}"
                            data-status="missed"
                            title="Mark as Missed">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                {% endif %}
            </div>
            {% else %}
            <p>No goals set yet. Start by adding your first milestone!</p>
            {% endfor %}
        </div>
    </div>
</div>

<!-- GOAL CALENDAR -->
<div class="grid">
    <div class="card" style="grid-column: span 3;">
        <h3>📅 Goal Calendar</h3>
        <div id="goalCalendar"></div>
    </div>
</div>


<div class="grid">
    <div class="card" style="grid-column: span 3;">
        <h3><i class="fas fa-lightbulb"></i> AI Advice History</h3>
        <div class="advice-history" style="margin-top: 1rem;">
            {% if advice_history %}
            <ul style="list-style-type: disc; padding-left: 2rem;">
                {% for advice in advice_history %}
                <li style="margin-bottom: 1rem;">
                    <strong>Q:</strong> {{ advice.query }}<br>
                    <strong>Summary:</strong>
                    {% if advice.summary %}
                    <ul>
                        {% for line in advice.summary.split('\n') %}
                            {% if line.strip() %}
                            <li>{{ line }}</li>
                            {% endif %}
                        {% endfor %}
                    </ul>
                    {% else %}
                    <p><em>No summary available</em></p>
                    {% endif %}
                    <small style="color:#666;">{{ advice.created_at }}</small>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p>No advice history yet. Visit <a href="{{ url_for('ai_guidance') }}">AI Guidance</a> to get started!</p>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}
```

---

## 9. templates/profile.html

```html
{% extends 'base.html' %}
{% block content %}
<div class="grid">
    <div class="card" style="grid-column: span 3;">
        <h2>Your Profile</h2>
        <form method="POST" action="{{ url_for('profile') }}" style="margin-top: 1.5rem;">
            <div class="form-group">
                <label>Full Name</label>
                <input type="text" name="full_name" value="{{ user.full_name }}" required>
            </div>
            <div class="form-group">
                <label>Education Level</label>
                <select name="education" required>
                    <option value="High School" {% if user.education == 'High School' %}selected{% endif %}>High School</option>
                    <option value="Bachelor's" {% if user.education == "Bachelor's" %}selected{% endif %}>Bachelor's Degree</option>
                    <option value="Master's" {% if user.education == "Master's" %}selected{% endif %}>Master's Degree</option>
                    <option value="PhD" {% if user.education == 'PhD' %}selected{% endif %}>PhD</option>
                </select>
            </div>
            <div class="form-group">
                <label>Career Goal</label>
                <input type="text" name="goal" value="{{ user.goal }}" required>
            </div>
            <div class="form-group">
                <label>Interests</label>
                <input type="text" name="interest" value="{{ user.interest }}" required>
            </div>
            <div class="form-group">
                <label>Current Skills</label>
                <input type="text" name="skills" value="{{ user.skills }}" required>
            </div>
            <button type="submit" class="btn btn-primary">Update Profile</button>
        </form>
    </div>
</div>
{% endblock %}
```

---

## 10. templates/ai_guidance.html

```html
{% extends 'base.html' %}
{% block content %}
<div class="grid">
    <div class="card" style="grid-column: span 3;">
        <h2>AI Career Coach</h2>
        <p>Get personalized career advice based on your goals, education, and skills.</p>

        <form id="aiForm" method="POST" style="margin-top: 1.5rem;">
            <div class="form-group">
                <label>Your Question</label>
                <textarea name="query" rows="4" placeholder="e.g., How can I transition to cloud engineering?" required></textarea>
            </div>

            <div class="form-group">
                <label>Response Length</label>
                <select name="length">
                    <option value="Short">Short (1-2 paragraphs)</option>
                    <option value="Medium" selected>Medium (3-4 paragraphs)</option>
                    <option value="Long">Long (Detailed, 5+ paragraphs)</option>
                </select>
            </div>

            <button type="submit" class="btn btn-primary">Ask AI Coach</button>
        </form>

        {% if response %}
        <div class="ai-output">
            <h3>AI Response:</h3>
            {{ response }}
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

---

## 11. templates/discussions.html

```html
{% extends 'base.html' %}
{% block content %}
<div class="grid">
    <div class="card" style="grid-column: span 3;">
        <h2>Community Discussions</h2>

        <div style="margin-top:1rem;">
            <form id="new-discussion" method="POST" action="{{ url_for('discussions') }}">
                <input type="hidden" name="username" value="{{ session.username }}">
                <input type="hidden" name="full_name" value="{{ session.full_name }}">
                <div class="form-group">
                    <label>Title</label>
                    <input type="text" name="title" required placeholder="Discussion title">
                </div>
                <div class="form-group">
                    <label>Body</label>
                    <textarea name="body" rows="4" required placeholder="Share something..."></textarea>
                </div>
                <button class="btn btn-primary">Post Discussion</button>
            </form>
        </div>

        <hr style="margin:1.5rem 0;">

        <div class="discussions-list">
            {% if discussions %}
                {% for d in discussions %}
                <div class="discussion-item" style="padding:1rem; border-radius:8px; background:#f9fafb; margin-bottom:1rem;">
                    <div style="display:flex; justify-content:space-between; align-items:start;">
                        <div style="flex:1;">
                            <h3>{{ d.title }}</h3>
                            <p style="color:#666;">by <strong>{{ d.username or d.full_name }}</strong> · <small>{{ d.created_at }}</small></p>
                            <p>{{ d.body }}</p>
                        </div>
                        {% if d.user_id == session.get('user_id') %}
                        <form method="POST" action="{{ url_for('delete_discussion', discussion_id=d.id) }}" style="display:inline;">
                            <button type="submit" class="btn" style="background:#ef4444; color:white; padding:0.4rem 0.8rem; font-size:0.85rem; border:none; border-radius:4px; cursor:pointer;" onclick="return confirm('Delete this discussion and all replies?')">Delete</button>
                        </form>
                        {% endif %}
                    </div>

                    <a href="#" class="reply-link" data-discussion="{{ d.id }}" data-reply="0" style="color:#06b6d4; text-decoration:none; font-size:0.9rem;">↳ Reply</a>

                    <!-- Reply form for main discussion -->
                    <div class="reply-form" id="reply-form-{{ d.id }}-0" style="display:none; margin-top:0.8rem; padding:0.8rem; background:#fff; border-left:3px solid #06b6d4; border-radius:4px;">
                        <form method="POST" action="{{ url_for('post_reply') }}">
                            <input type="hidden" name="discussion_id" value="{{ d.id }}">
                            <input type="hidden" name="parent_id" value="0">
                            <input type="hidden" name="username" value="{{ session.username }}">
                            <input type="hidden" name="full_name" value="{{ session.full_name }}">
                            <div class="form-group">
                                <textarea name="body" rows="2" required placeholder="Write a reply..."></textarea>
                            </div>
                            <button class="btn btn-secondary" style="font-size:0.9rem; padding:0.4rem 0.8rem;">Post</button>
                            <button type="button" class="btn" style="font-size:0.9rem; padding:0.4rem 0.8rem;" onclick="document.getElementById('reply-form-{{ d.id }}-0').style.display='none'">Cancel</button>
                        </form>
                    </div>

                    <!-- Nested Replies -->
                    <div style="margin-left:1.5rem; margin-top:1rem;">
                        {% macro render_replies(replies, discussion_id) %}
                            {% for r in replies %}
                                <div style="border-left:2px solid #e5e7eb; padding-left:0.8rem; margin:0.8rem 0; padding-top:0.8rem;">
                                    <div style="display:flex; justify-content:space-between; align-items:start;">
                                        <div style="flex:1;">
                                            <p style="margin:0; font-size:0.95rem;"><strong style="color:#1f2937;">{{ r.username or r.full_name }}</strong> <span style="color:#999;">· {{ r.created_at }}</span></p>
                                            <p style="margin:0.4rem 0; color:#333;">{{ r.body }}</p>
                                        </div>
                                        {% if r.user_id == session.get('user_id') %}
                                        <form method="POST" action="{{ url_for('delete_reply', reply_id=r.id) }}" style="display:inline;">
                                            <button type="submit" class="btn" style="background:#ef4444; color:white; padding:0.3rem 0.6rem; font-size:0.8rem; border:none; border-radius:3px; cursor:pointer;" onclick="return confirm('Delete this reply and all nested replies?')">Delete</button>
                                        </form>
                                        {% endif %}
                                    </div>

                                    <a href="#" class="reply-link" data-discussion="{{ discussion_id }}" data-reply="{{ r.id }}" style="color:#06b6d4; text-decoration:none; font-size:0.85rem;">↳ Reply</a>

                                    <!-- Reply form for this specific reply -->
                                    <div class="reply-form" id="reply-form-{{ discussion_id }}-{{ r.id }}" style="display:none; margin-top:0.6rem; padding:0.6rem; background:#f9fafb; border-left:2px solid #06b6d4; border-radius:3px;">
                                        <form method="POST" action="{{ url_for('post_reply') }}">
                                            <input type="hidden" name="discussion_id" value="{{ discussion_id }}">
                                            <input type="hidden" name="parent_id" value="{{ r.id }}">
                                            <input type="hidden" name="username" value="{{ session.username }}">
                                            <input type="hidden" name="full_name" value="{{ session.full_name }}">
                                            <div class="form-group">
                                                <textarea name="body" rows="2" required placeholder="Write a reply..." style="font-size:0.9rem;"></textarea>
                                            </div>
                                            <button class="btn btn-secondary" style="font-size:0.85rem; padding:0.3rem 0.6rem;">Post</button>
                                            <button type="button" class="btn" style="font-size:0.85rem; padding:0.3rem 0.6rem;" onclick="document.getElementById('reply-form-{{ discussion_id }}-{{ r.id }}').style.display='none'">Cancel</button>
                                        </form>
                                    </div>

                                    <!-- Recursive nested replies -->
                                    {% if r.replies %}
                                        <div style="margin-left:0.8rem;">
                                            {{ render_replies(r.replies, discussion_id) }}
                                        </div>
                                    {% endif %}
                                </div>
                            {% endfor %}
                        {% endmacro %}

                        {{ render_replies(d.replies, d.id) }}
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <p>No discussions yet. Be the first to start one!</p>
            {% endif %}
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.reply-link').forEach(a => {
        a.addEventListener('click', (e) => {
            e.preventDefault();
            const disc = a.dataset.discussion;
            const reply = a.dataset.reply;
            const formId = `reply-form-${disc}-${reply}`;
            const form = document.getElementById(formId);
            
            if (form) {
                // Toggle visibility and scroll into view
                if (form.style.display === 'none') {
                    form.style.display = 'block';
                    form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    form.querySelector('textarea').focus();
                } else {
                    form.style.display = 'none';
                }
            }
        });
    });
});
</script>

{% endblock %}
```

---

## END OF ARCHIVE

**Total Files Documented:** 11  
**Code Types:** Python (Flask), JavaScript (Vanilla), CSS3, HTML5 + Jinja2 Templates

This file contains the complete, production-ready code for the CareerPulse application.
