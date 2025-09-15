import os
import json
import uuid
from datetime import datetime
from functools import wraps
from PIL import Image
import markdown
import trafilatura
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename

# Blueprint integration reference for OpenAI
# the newest OpenAI model is "gpt-5" which was released August 7, 2025.
# do not change this unless explicitly requested by the user
from openai import OpenAI

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize OpenAI client if API key is available
openai_client = None
if os.environ.get('OPENAI_API_KEY'):
    openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Load configuration
def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "site_title": "Tutorial Platform",
            "site_description": "Interactive learning platform",
            "admin_passcode": "admin123",
            "max_file_size": 10485760,
            "image_dimensions": {"width": 800, "height": 500}
        }

def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)

# Load courses data
def load_courses():
    try:
        with open('data/courses.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"modules": []}

def save_courses(data):
    with open('data/courses.json', 'w') as f:
        json.dump(data, f, indent=2)

# Load progress data
def load_progress():
    try:
        with open('data/progress.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_progress(data):
    with open('data/progress.json', 'w') as f:
        json.dump(data, f, indent=2)

# Admin authentication decorator
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Generate CSRF token
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = str(uuid.uuid4())
    return session['csrf_token']

app.jinja_env.globals.update(csrf_token=generate_csrf_token)

# Validate CSRF token
def validate_csrf_token():
    token = session.get('csrf_token')
    form_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    return token and token == form_token

# Routes
@app.route('/')
def index():
    courses_data = load_courses()
    config = load_config()
    return render_template('index.html', 
                         courses=courses_data,
                         config=config)

@app.route('/module/<module_id>')
def module_detail(module_id):
    courses_data = load_courses()
    module = None
    
    for m in courses_data.get('modules', []):
        if m['id'] == module_id:
            module = m
            break
    
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('index'))
    
    # Load module content if it exists
    content_file = f"data/modules/{module_id}.html"
    try:
        with open(content_file, 'r') as f:
            module['content'] = f.read()
    except FileNotFoundError:
        module['content'] = "<p>No content available for this module.</p>"
    
    config = load_config()
    return render_template('module.html', 
                         module=module,
                         config=config)

@app.route('/quiz/<module_id>')
def quiz(module_id):
    courses_data = load_courses()
    module = None
    
    for m in courses_data.get('modules', []):
        if m['id'] == module_id:
            module = m
            break
    
    if not module or not module.get('quiz'):
        flash('Quiz not found', 'error')
        return redirect(url_for('index'))
    
    config = load_config()
    return render_template('quiz.html', 
                         module=module,
                         config=config)

@app.route('/api/quiz-submit', methods=['POST'])
def quiz_submit():
    data = request.get_json()
    module_id = data.get('module_id')
    answers = data.get('answers', {})
    
    courses_data = load_courses()
    module = None
    
    for m in courses_data.get('modules', []):
        if m['id'] == module_id:
            module = m
            break
    
    if not module or not module.get('quiz'):
        return jsonify({'error': 'Quiz not found'}), 404
    
    # Calculate score
    total_questions = len(module['quiz'].get('questions', []))
    correct_answers = 0
    
    for i, question in enumerate(module['quiz'].get('questions', [])):
        user_answer = answers.get(str(i))
        correct_answer = question.get('correct_answer')
        
        if user_answer == correct_answer:
            correct_answers += 1
    
    score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    passed = score >= module['quiz'].get('passing_score', 70)
    
    return jsonify({
        'score': score,
        'correct': correct_answers,
        'total': total_questions,
        'passed': passed
    })

@app.route('/certificate/<module_id>')
def generate_certificate(module_id):
    courses_data = load_courses()
    module = None
    
    for m in courses_data.get('modules', []):
        if m['id'] == module_id:
            module = m
            break
    
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('index'))
    
    # Generate PDF certificate
    filename = f"certificate_{module_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = f"static/resources/{filename}"
    
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    # Certificate content
    c.setFont("Helvetica-Bold", 24)
    text = "Certificate of Completion"
    c.drawString((width - c.stringWidth(text)) / 2, height - 100, text)
    
    c.setFont("Helvetica", 16)
    text = "This certifies that you have successfully completed:"
    c.drawString((width - c.stringWidth(text)) / 2, height - 200, text)
    
    c.setFont("Helvetica-Bold", 20)
    text = module['title']
    c.drawString((width - c.stringWidth(text)) / 2, height - 250, text)
    
    c.setFont("Helvetica", 12)
    text = f"Date: {datetime.now().strftime('%B %d, %Y')}"
    c.drawString((width - c.stringWidth(text)) / 2, height - 350, text)
    
    c.save()
    
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/api/scrape-url', methods=['POST'])
def scrape_url():
    if not validate_csrf_token():
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        # Extract text content using trafilatura
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded)
        
        if not text:
            return jsonify({'error': 'Could not extract content from URL'}), 400
        
        # Generate quiz questions using OpenAI if available
        quiz_questions = []
        if openai_client:
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {
                            "role": "system",
                            "content": "Generate 3-5 multiple choice quiz questions based on the provided text content. Respond with JSON in this format: {'questions': [{'question': 'Question text', 'options': ['A', 'B', 'C', 'D'], 'correct_answer': 0, 'type': 'multiple_choice'}]}"
                        },
                        {"role": "user", "content": f"Generate quiz questions for this content:\n\n{text[:2000]}"}
                    ],
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                if content:
                    quiz_data = json.loads(content)
                else:
                    quiz_data = {}
                quiz_questions = quiz_data.get('questions', [])
            except Exception as e:
                print(f"Error generating quiz questions: {e}")
        
        return jsonify({
            'content': text,
            'quiz_questions': quiz_questions
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        passcode = request.form.get('passcode')
        config = load_config()
        
        if passcode == config.get('admin_passcode', 'admin123'):
            session['admin_authenticated'] = True
            session.permanent = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid passcode', 'error')
    
    config = load_config()
    return render_template('admin/login.html', config=config)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_authenticated', None)
    return redirect(url_for('index'))

@app.route('/admin')
@require_admin
def admin_dashboard():
    courses_data = load_courses()
    config = load_config()
    return render_template('admin/dashboard.html', 
                         courses=courses_data,
                         config=config)

@app.route('/admin/module/new', methods=['GET', 'POST'])
@require_admin
def admin_new_module():
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid CSRF token', 'error')
            return redirect(url_for('admin_new_module'))
        
        title = request.form.get('title')
        description = request.form.get('description')
        video_url = request.form.get('video_url')
        content = request.form.get('content')
        
        if not title:
            flash('Title is required', 'error')
            return redirect(url_for('admin_new_module'))
        
        # Generate unique module ID
        module_id = str(uuid.uuid4())
        
        # Create module data
        module_data = {
            'id': module_id,
            'title': title,
            'description': description or '',
            'video_url': video_url or '',
            'created_at': datetime.now().isoformat(),
            'order': 0
        }
        
        # Save module content to file
        if content:
            content_file = f"data/modules/{module_id}.html"
            with open(content_file, 'w') as f:
                f.write(content)
        
        # Add module to courses data
        courses_data = load_courses()
        courses_data['modules'].append(module_data)
        save_courses(courses_data)
        
        flash('Module created successfully', 'success')
        return redirect(url_for('admin_dashboard'))
    
    config = load_config()
    return render_template('admin/module_form.html', 
                         config=config,
                         module=None,
                         action='Create')

@app.route('/admin/module/<module_id>/edit', methods=['GET', 'POST'])
@require_admin
def admin_edit_module(module_id):
    courses_data = load_courses()
    module = None
    
    for m in courses_data.get('modules', []):
        if m['id'] == module_id:
            module = m
            break
    
    if not module:
        flash('Module not found', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid CSRF token', 'error')
            return redirect(url_for('admin_edit_module', module_id=module_id))
        
        module['title'] = request.form.get('title', module['title'])
        module['description'] = request.form.get('description', module['description'])
        module['video_url'] = request.form.get('video_url', module.get('video_url', ''))
        
        content = request.form.get('content')
        if content:
            content_file = f"data/modules/{module_id}.html"
            with open(content_file, 'w') as f:
                f.write(content)
        
        save_courses(courses_data)
        flash('Module updated successfully', 'success')
        return redirect(url_for('admin_dashboard'))
    
    # Load module content
    content_file = f"data/modules/{module_id}.html"
    try:
        with open(content_file, 'r') as f:
            module['content'] = f.read()
    except FileNotFoundError:
        module['content'] = ''
    
    config = load_config()
    return render_template('admin/module_form.html', 
                         config=config,
                         module=module,
                         action='Edit')

@app.route('/admin/module/<module_id>/delete', methods=['POST'])
@require_admin
def admin_delete_module(module_id):
    if not validate_csrf_token():
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    courses_data = load_courses()
    courses_data['modules'] = [m for m in courses_data['modules'] if m['id'] != module_id]
    save_courses(courses_data)
    
    # Delete content file
    content_file = f"data/modules/{module_id}.html"
    try:
        os.remove(content_file)
    except FileNotFoundError:
        pass
    
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)