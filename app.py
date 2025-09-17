import os
import json
import uuid
import ipaddress
import socket
import sqlite3
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse
import requests
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
app.secret_key = os.environ.get("SESSION_SECRET")
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize OpenAI client if API key is available
openai_client = None
if os.environ.get('OPENAI_API_KEY'):
    openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Database initialization
def init_database():
    """Initialize SQLite database with required tables"""
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()
    
    # Create modules table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            video_url TEXT,
            created_at TEXT NOT NULL,
            order_num INTEGER DEFAULT 0,
            quiz_data TEXT
        )
    ''')
    
    # Create module_content table for storing HTML content
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS module_content (
            module_id TEXT PRIMARY KEY,
            content TEXT,
            FOREIGN KEY (module_id) REFERENCES modules (id) ON DELETE CASCADE
        )
    ''')
    
    # Create progress table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_database()

# Migrate existing JSON data to SQLite
def migrate_json_to_sqlite():
    """Migrate existing JSON data to SQLite database if it exists"""
    json_file = 'data/courses.json'
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r') as f:
                json_data = json.load(f)
            
            # Check if there are modules to migrate
            if json_data.get('modules'):
                conn = sqlite3.connect('data/tutorial_platform.db')
                cursor = conn.cursor()
                
                # Check if database is empty
                cursor.execute('SELECT COUNT(*) FROM modules')
                if cursor.fetchone()[0] == 0:
                    print("Migrating existing modules from JSON to SQLite...")
                    
                    # Migrate modules
                    for module in json_data['modules']:
                        quiz_data = None
                        if 'quiz' in module:
                            quiz_data = json.dumps(module['quiz'])
                            
                        cursor.execute('''
                            INSERT INTO modules (id, title, description, video_url, created_at, order_num, quiz_data)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            module['id'],
                            module['title'],
                            module.get('description', ''),
                            module.get('video_url', ''),
                            module['created_at'],
                            module.get('order', 0),
                            quiz_data
                        ))
                        
                        # Migrate content files
                        content_file = f"data/modules/{module['id']}.html"
                        if os.path.exists(content_file):
                            with open(content_file, 'r') as cf:
                                content = cf.read()
                                cursor.execute('''
                                    INSERT INTO module_content (module_id, content)
                                    VALUES (?, ?)
                                ''', (module['id'], content))
                    
                    conn.commit()
                    print(f"Successfully migrated {len(json_data['modules'])} modules to SQLite")
                
                conn.close()
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Migration skipped: {e}")

# Run migration
migrate_json_to_sqlite()

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
            "image_dimensions": {"width": 800, "height": 500},
            "header_customization": {
                "title_color": "#000000",
                "title_size": "1.5rem",
                "nav_text_color": "#000000", 
                "nav_text_size": "1rem",
                "background_gradient_start": "#ff006e",
                "background_gradient_middle": "#00f5ff", 
                "background_gradient_end": "#ffbe0b",
                "show_emoji": True,
                "custom_emoji": "✨"
            }
        }

def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)

# Load courses data from SQLite
def load_courses():
    """Load courses from SQLite database"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, description, video_url, created_at, order_num, quiz_data 
        FROM modules ORDER BY order_num, created_at
    ''')
    
    modules = []
    for row in cursor.fetchall():
        module = {
            'id': row[0],
            'title': row[1],
            'description': row[2] or '',
            'video_url': row[3] or '',
            'created_at': row[4],
            'order': row[5]
        }
        
        # Parse quiz data if it exists
        if row[6]:
            try:
                module['quiz'] = json.loads(row[6])
            except json.JSONDecodeError:
                pass
        
        modules.append(module)
    
    conn.close()
    return {"modules": modules}

def save_courses(data):
    """Save courses to SQLite database - safer update approach"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    conn.execute('PRAGMA foreign_keys=ON')  # Enable foreign key constraints
    cursor = conn.cursor()
    
    # Get existing module IDs
    cursor.execute('SELECT id FROM modules')
    existing_ids = set(row[0] for row in cursor.fetchall())
    
    # Get new module IDs
    new_ids = set(module['id'] for module in data.get('modules', []))
    
    # Delete modules that are no longer present
    for module_id in existing_ids - new_ids:
        cursor.execute('DELETE FROM modules WHERE id = ?', (module_id,))
    
    # Update or insert modules
    for module in data.get('modules', []):
        quiz_data = None
        if 'quiz' in module:
            quiz_data = json.dumps(module['quiz'])
            
        cursor.execute('''
            INSERT OR REPLACE INTO modules (id, title, description, video_url, created_at, order_num, quiz_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            module['id'],
            module['title'],
            module.get('description', ''),
            module.get('video_url', ''),
            module['created_at'],
            module.get('order', 0),
            quiz_data
        ))
    
    conn.commit()
    conn.close()

def update_module_in_db(module):
    """Update a single module in the database"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    conn.execute('PRAGMA foreign_keys=ON')
    cursor = conn.cursor()
    
    quiz_data = None
    if 'quiz' in module:
        quiz_data = json.dumps(module['quiz'])
        
    cursor.execute('''
        INSERT OR REPLACE INTO modules (id, title, description, video_url, created_at, order_num, quiz_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        module['id'],
        module['title'],
        module.get('description', ''),
        module.get('video_url', ''),
        module['created_at'],
        module.get('order', 0),
        quiz_data
    ))
    
    conn.commit()
    conn.close()

def save_module_content(module_id, content):
    """Save module content to database"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    conn.execute('PRAGMA foreign_keys=ON')  # Enable foreign key constraints
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO module_content (module_id, content)
        VALUES (?, ?)
    ''', (module_id, content))
    
    conn.commit()
    conn.close()

def load_module_content(module_id):
    """Load module content from database"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    conn.execute('PRAGMA foreign_keys=ON')  # Enable foreign key constraints
    cursor = conn.cursor()
    
    cursor.execute('SELECT content FROM module_content WHERE module_id = ?', (module_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else None

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

# Enhanced URL validation for SSRF protection
def is_safe_url(url):
    """Validate URL to prevent SSRF attacks with comprehensive IPv4/IPv6 checking"""
    try:
        parsed = urlparse(url)
        
        # Only allow HTTP and HTTPS schemes
        if parsed.scheme not in ['http', 'https']:
            return False, 'Only HTTP and HTTPS schemes are allowed'
        
        # Ensure hostname is present
        if not parsed.hostname:
            return False, 'Invalid hostname'
        
        hostname = parsed.hostname.lower()
        
        # Block IP literals in URLs (both IPv4 and IPv6)
        try:
            ip_literal = ipaddress.ip_address(hostname)
            return False, 'IP literal addresses are not allowed'
        except ValueError:
            # Not an IP literal, continue with hostname validation
            pass
        
        # Block localhost and other dangerous hostnames
        dangerous_hostnames = [
            'localhost', '127.0.0.1', '::1',
            'metadata.google.internal',
            '169.254.169.254',  # AWS/GCP metadata
            '100.100.100.200',  # Alibaba metadata
            '192.0.0.192',      # Oracle metadata
        ]
        
        if hostname in dangerous_hostnames:
            return False, f'Hostname "{hostname}" is not allowed'
        
        # Resolve hostname to ALL IP addresses (both IPv4 and IPv6)
        try:
            # Get all address info for both IPv4 and IPv6
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            resolved_ips = [info[4][0] for info in addr_info]
            
            if not resolved_ips:
                return False, 'Could not resolve hostname'
        except (socket.gaierror, ValueError):
            return False, 'Could not resolve hostname'
        
        # Validate ALL resolved IP addresses
        for ip_str in resolved_ips:
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                
                # Block private IP ranges (both IPv4 and IPv6)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                    return False, f'Private, loopback, and link-local IPs are not allowed (resolved: {ip_str})'
                
                # Block reserved IP ranges
                if ip_obj.is_reserved or ip_obj.is_multicast:
                    return False, f'Reserved and multicast IPs are not allowed (resolved: {ip_str})'
                
                # Block cloud metadata endpoints and other dangerous IPs
                dangerous_ips = [
                    '169.254.169.254',  # AWS/GCP metadata
                    '100.100.100.200',  # Alibaba metadata  
                    '192.0.0.192',      # Oracle metadata
                    '::1',              # IPv6 localhost
                    'fd00:ec2::254',    # AWS IPv6 metadata
                ]
                
                if str(ip_obj) in dangerous_ips:
                    return False, f'Access to dangerous IP {ip_obj} is not allowed'
                
                # Additional IPv6 checks
                if ip_obj.version == 6:
                    # Block unique local addresses (fc00::/7)
                    if ipaddress.IPv6Address(ip_str) in ipaddress.IPv6Network('fc00::/7'):
                        return False, f'IPv6 unique local addresses are not allowed (resolved: {ip_str})'
                    
                    # Block site-local addresses (fec0::/10) - deprecated but still blocked
                    if ipaddress.IPv6Address(ip_str) in ipaddress.IPv6Network('fec0::/10'):
                        return False, f'IPv6 site-local addresses are not allowed (resolved: {ip_str})'
                        
            except ValueError:
                return False, f'Invalid IP address resolved: {ip_str}'
        
        # Block common internal service ports
        dangerous_ports = [22, 23, 25, 53, 135, 139, 445, 993, 995, 1433, 3306, 3389, 5432, 5984, 6379, 8080, 9200, 27017]
        if parsed.port and parsed.port in dangerous_ports:
            return False, f'Access to port {parsed.port} is not allowed'
        
        return True, 'URL is safe'
        
    except Exception as e:
        return False, f'URL validation error: {str(e)}'

def secure_fetch_url(url, timeout=10, max_size=5*1024*1024, max_redirects=3):
    """Securely fetch URL content with manual redirect handling and comprehensive SSRF protection"""
    try:
        visited_urls = set()
        redirect_count = 0
        current_url = url
        
        while redirect_count <= max_redirects:
            # Check for redirect loops
            if current_url in visited_urls:
                raise ValueError('Redirect loop detected')
            visited_urls.add(current_url)
            
            # Validate current URL
            is_safe, message = is_safe_url(current_url)
            if not is_safe:
                raise ValueError(f'Unsafe URL: {message}')
            
            # Make request with security headers and NO automatic redirects
            headers = {
                'User-Agent': 'Tutorial-Platform-Scraper/1.0',
                'Accept': 'text/html,application/xhtml+xml,text/plain',
                'Accept-Language': 'en-US,en;q=0.9',
                'DNT': '1',
                'Connection': 'close'
            }
            
            response = requests.get(
                current_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,  # CRITICAL: Disable automatic redirects
                stream=True,
                verify=True
            )
            
            # Handle redirects manually
            if response.status_code in [301, 302, 303, 307, 308]:
                if redirect_count >= max_redirects:
                    raise ValueError(f'Too many redirects (max: {max_redirects})')
                
                location = response.headers.get('Location')
                if not location:
                    raise ValueError('Redirect response missing Location header')
                
                # Resolve relative URLs
                if location.startswith('/'):
                    from urllib.parse import urljoin
                    current_url = urljoin(current_url, location)
                elif not location.startswith(('http://', 'https://')):
                    from urllib.parse import urljoin
                    current_url = urljoin(current_url, location)
                else:
                    current_url = location
                
                # CRITICAL: Re-validate redirect target for SSRF protection
                is_safe, safety_message = is_safe_url(current_url)
                if not is_safe:
                    raise ValueError(f'Redirect to unsafe URL blocked: {safety_message}')
                
                redirect_count += 1
                continue
            
            # Not a redirect, process the response
            response.raise_for_status()
            
            # Check response size before reading content
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > max_size:
                raise ValueError(f'Content too large: {content_length} bytes (max: {max_size})')
            
            # Read content with size limit
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > max_size:
                    raise ValueError(f'Content too large (max: {max_size} bytes)')
            
            # Return the final content
            return content.decode('utf-8', errors='replace')
        
        raise ValueError(f'Too many redirects (max: {max_redirects})')
        
    except requests.exceptions.Timeout:
        raise ValueError('Request timeout')
    except requests.exceptions.SSLError:
        raise ValueError('SSL certificate verification failed')
    except requests.exceptions.ConnectionError:
        raise ValueError('Connection error')
    except requests.exceptions.HTTPError as e:
        raise ValueError(f'HTTP error: {e.response.status_code}')
    except requests.exceptions.TooManyRedirects:
        raise ValueError('Too many redirects')
    except UnicodeDecodeError:
        raise ValueError('Unable to decode response content')
    except Exception as e:
        raise ValueError(f'Request failed: {str(e)}')

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
    
    # Load module content from database
    module['content'] = load_module_content(module_id)
    if not module['content']:
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
    # CSRF protection for quiz submissions
    if not validate_csrf_token():
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
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

@app.route('/sw.js')
def service_worker():
    """Serve the service worker from root scope for PWA installability"""
    response = app.send_static_file('sw.js')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Add cache control for static files in development
@app.after_request
def after_request(response):
    if app.debug:  # Only in debug mode
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

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
@require_admin
def scrape_url():
    if not validate_csrf_token():
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Validate and sanitize URL
    url = str(url).strip()
    if len(url) > 2048:  # Reasonable URL length limit
        return jsonify({'error': 'URL too long'}), 400
    
    try:
        # Securely fetch URL content
        html_content = secure_fetch_url(url, timeout=10, max_size=5*1024*1024)
        
        # Extract text content using trafilatura
        text = trafilatura.extract(html_content)
        
        if not text:
            return jsonify({'error': 'Could not extract content from URL'}), 400
        
        # Limit extracted text size
        if len(text) > 50000:  # 50KB text limit
            text = text[:50000] + '... [truncated]'
        
        # Generate quiz questions using OpenAI if available
        quiz_questions = []
        if openai_client:
            try:
                # Limit content sent to OpenAI
                content_for_ai = text[:2000] if len(text) > 2000 else text
                
                response = openai_client.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {
                            "role": "system",
                            "content": "Generate 3-5 multiple choice quiz questions based on the provided text content. Respond with JSON in this format: {'questions': [{'question': 'Question text', 'options': ['A', 'B', 'C', 'D'], 'correct_answer': 0, 'type': 'multiple_choice'}]}"
                        },
                        {"role": "user", "content": f"Generate quiz questions for this content:\n\n{content_for_ai}"}
                    ],
                    response_format={"type": "json_object"}
                )
                
                ai_content = response.choices[0].message.content
                if ai_content:
                    quiz_data = json.loads(ai_content)
                else:
                    quiz_data = {}
                quiz_questions = quiz_data.get('questions', [])
            except Exception as e:
                print(f"Error generating quiz questions: {e}")
                # Don't fail the entire request if AI generation fails
        
        return jsonify({
            'content': text,
            'quiz_questions': quiz_questions
        })
        
    except ValueError as e:
        # These are our custom validation errors
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # Log the error but don't expose internal details
        print(f"Scraping error: {e}")
        return jsonify({'error': 'Failed to process URL'}), 500

# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid CSRF token', 'error')
            return redirect(url_for('admin_login'))
            
        passcode = request.form.get('passcode')
        config = load_config()
        
        if passcode == config.get('admin_passcode', 'admin123'):
            session['admin_authenticated'] = True
            session.permanent = True
            session['csrf_token'] = str(uuid.uuid4())  # Regenerate token
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid passcode', 'error')
    
    config = load_config()
    return render_template('admin/login.html', config=config)

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    if not validate_csrf_token():
        flash('Invalid CSRF token', 'error')
        return redirect(url_for('admin_dashboard'))
    
    session.pop('admin_authenticated', None)
    session.pop('csrf_token', None)
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
        
        # Save module content to database
        if content:
            save_module_content(module_id, content)
        
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
            save_module_content(module_id, content)
        
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
    
    # Content is automatically deleted by the database foreign key constraint
    
    return jsonify({'success': True})

@app.route('/admin/config', methods=['POST'])
@require_admin
def admin_update_config():
    if not validate_csrf_token():
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    data = request.get_json()
    config = load_config()
    
    # Update basic configuration
    for key, value in data.items():
        if key in ['site_title', 'site_description', 'admin_passcode']:
            config[key] = value
    
    # Update header customization with validation
    if 'header_customization' in data:
        if 'header_customization' not in config:
            config['header_customization'] = {}
        
        header_data = data['header_customization']
        
        # Validate and sanitize header values
        validated_header = {}
        
        # Color validation (hex colors only)
        import re
        hex_color_pattern = r'^#[0-9A-Fa-f]{6}$'
        for color_key in ['title_color', 'nav_text_color', 'background_gradient_start', 'background_gradient_middle', 'background_gradient_end']:
            if color_key in header_data:
                color_value = str(header_data[color_key])
                if re.match(hex_color_pattern, color_value):
                    validated_header[color_key] = color_value
        
        # Size validation (rem units only)
        size_pattern = r'^\d+(\.\d+)?rem$'
        for size_key in ['title_size', 'nav_text_size']:
            if size_key in header_data:
                size_value = str(header_data[size_key])
                if re.match(size_pattern, size_value):
                    validated_header[size_key] = size_value
        
        # Boolean validation
        if 'show_emoji' in header_data:
            validated_header['show_emoji'] = bool(header_data['show_emoji'])
        
        # Emoji validation (limited length and basic sanitization)
        if 'custom_emoji' in header_data:
            emoji_value = str(header_data['custom_emoji'])
            # Limit to 4 characters and strip any HTML/script-like content
            if len(emoji_value) <= 4 and not any(char in emoji_value for char in ['<', '>', '"', "'", '&']):
                validated_header['custom_emoji'] = emoji_value
        
        # Update config with validated values only
        config['header_customization'].update(validated_header)
    
    save_config(config)
    return jsonify({'success': True})

@app.route('/admin/modules/reorder', methods=['POST'])
@require_admin
def admin_reorder_modules():
    if not validate_csrf_token():
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    data = request.get_json()
    module_order = data.get('module_order', [])
    
    courses_data = load_courses()
    modules = courses_data.get('modules', [])
    
    # Reorder modules based on provided order
    reordered_modules = []
    for module_id in module_order:
        for module in modules:
            if module['id'] == module_id:
                module['order'] = len(reordered_modules)
                reordered_modules.append(module)
                break
    
    courses_data['modules'] = reordered_modules
    save_courses(courses_data)
    
    return jsonify({'success': True})

@app.route('/admin/upload-image', methods=['POST'])
@require_admin
def admin_upload_image():
    # Check if request is from CKEditor (different field name and CSRF handling)
    is_ckeditor = 'upload' in request.files
    
    if not is_ckeditor and not validate_csrf_token():
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    # Handle different field names for different upload sources
    file_field = 'upload' if is_ckeditor else 'image'
    
    if file_field not in request.files:
        error_response = {'error': {'message': 'No image file'}} if is_ckeditor else {'error': 'No image file'}
        return jsonify(error_response), 400
    
    file = request.files[file_field]
    if not file.filename or file.filename == '':
        error_response = {'error': {'message': 'No file selected'}} if is_ckeditor else {'error': 'No file selected'}
        return jsonify(error_response), 400
    
    if file and file.filename and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join('static/resources', filename)
        
        # Get crop and resize parameters
        crop_mode = request.form.get('crop_mode', 'smart')  # smart, center, square
        max_width = int(request.form.get('max_width', 800))
        max_height = int(request.form.get('max_height', 600))
        
        try:
            image = Image.open(file.stream)
            
            # Apply cropping based on mode
            if crop_mode == 'square':
                # Crop to square aspect ratio
                min_dimension = min(image.width, image.height)
                left = (image.width - min_dimension) // 2
                top = (image.height - min_dimension) // 2
                right = left + min_dimension
                bottom = top + min_dimension
                image = image.crop((left, top, right, bottom))
            elif crop_mode == 'center':
                # Crop to center with target aspect ratio
                target_ratio = max_width / max_height
                current_ratio = image.width / image.height
                
                if current_ratio > target_ratio:
                    # Image is wider, crop width
                    new_width = int(image.height * target_ratio)
                    left = (image.width - new_width) // 2
                    image = image.crop((left, 0, left + new_width, image.height))
                elif current_ratio < target_ratio:
                    # Image is taller, crop height
                    new_height = int(image.width / target_ratio)
                    top = (image.height - new_height) // 2
                    image = image.crop((0, top, image.width, top + new_height))
            
            # Resize while maintaining aspect ratio if needed
            if image.width > max_width or image.height > max_height:
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Convert to RGB if needed (for JPEG)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if 'A' in image.mode else None)
                image = background
            
            image.save(filepath, 'JPEG', quality=85, optimize=True)
            
            image_url = url_for('static', filename=f'resources/{filename}')
            
            # Return different response format for CKEditor vs regular upload
            if is_ckeditor:
                return jsonify({'url': image_url})
            else:
                return jsonify({
                    'success': True,
                    'url': image_url
                })
        except Exception as e:
            error_response = {'error': {'message': f'Error processing image: {str(e)}'}} if is_ckeditor else {'error': f'Error processing image: {str(e)}'}
            return jsonify(error_response), 500
    
    error_response = {'error': {'message': 'Invalid file type'}} if is_ckeditor else {'error': 'Invalid file type'}
    return jsonify(error_response), 400

@app.route('/admin/export')
@require_admin
def admin_export_data():
    import zipfile
    import io
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add configuration
        zip_file.write('config.json', 'config.json')
        
        # Add data files
        for data_file in ['data/courses.json', 'data/progress.json', 'data/feedback.json']:
            if os.path.exists(data_file):
                zip_file.write(data_file, data_file)
        
        # Add module content files
        module_dir = 'data/modules'
        if os.path.exists(module_dir):
            for filename in os.listdir(module_dir):
                filepath = os.path.join(module_dir, filename)
                if os.path.isfile(filepath):
                    zip_file.write(filepath, filepath)
        
        # Add static resources
        resources_dir = 'static/resources'
        if os.path.exists(resources_dir):
            for filename in os.listdir(resources_dir):
                filepath = os.path.join(resources_dir, filename)
                if os.path.isfile(filepath):
                    zip_file.write(filepath, filepath)
    
    zip_buffer.seek(0)
    
    return send_file(
        io.BytesIO(zip_buffer.read()),
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'tutorial_platform_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)