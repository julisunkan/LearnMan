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
import bleach
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_file, make_response, after_this_request
from markupsafe import Markup
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

# HTML sanitization configuration
ALLOWED_TAGS = [
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'a', 'strong', 'em', 'b', 'i',
    'code', 'pre', 'blockquote', 'img', 'table', 'tr', 'td', 'th', 'thead', 'tbody', 'hr', 'br',
    'div', 'span'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'table': ['class'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
    'div': ['class'],
    'span': ['class']
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

def sanitize_html(content):
    """Sanitize HTML content to prevent XSS while allowing safe formatting"""
    if not content:
        return ""

    # First clean with bleach
    cleaned_content = bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )

    # Add rel="noopener noreferrer" to external links for security
    def add_rel_attributes(attrs, new=False):
        attrs[None, 'rel'] = 'noopener noreferrer'
        return attrs

    cleaned_content = bleach.linkify(
        cleaned_content,
        parse_email=True,
        callbacks=[add_rel_attributes]
    )

    return cleaned_content

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
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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

    # Create site configuration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS site_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            data_type TEXT DEFAULT 'string'
        )
    ''')

    # Create certificate templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS certificate_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT 'Certificate of Completion',
            subtitle TEXT DEFAULT 'This certifies that you have successfully completed:',
            font_size_title INTEGER DEFAULT 24,
            font_size_subtitle INTEGER DEFAULT 16,
            font_size_module INTEGER DEFAULT 20,
            font_size_date INTEGER DEFAULT 12,
            margin_top INTEGER DEFAULT 100,
            margin_subtitle INTEGER DEFAULT 200,
            margin_module INTEGER DEFAULT 250,
            margin_date INTEGER DEFAULT 350,
            background_color TEXT DEFAULT '#ffffff',
            text_color TEXT DEFAULT '#000000',
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    ''')

    # Add new columns if they don't exist (database migration)
    new_columns = [
        ('header_text', 'TEXT DEFAULT ""'),
        ('footer_text', 'TEXT DEFAULT ""'),
        ('company_name', 'TEXT DEFAULT ""'),
        ('logo_url', 'TEXT DEFAULT ""'),
        ('signature_url', 'TEXT DEFAULT ""'),
        ('signature_name', 'TEXT DEFAULT ""'),
        ('signature_title', 'TEXT DEFAULT ""'),
        ('font_size_header', 'INTEGER DEFAULT 14'),
        ('font_size_footer', 'INTEGER DEFAULT 10'),
        ('font_size_signature', 'INTEGER DEFAULT 12'),
        ('margin_footer', 'INTEGER DEFAULT 400'),
        ('margin_signature', 'INTEGER DEFAULT 420'),
        ('logo_width', 'INTEGER DEFAULT 100'),
        ('logo_height', 'INTEGER DEFAULT 50'),
        ('signature_width', 'INTEGER DEFAULT 150'),
        ('signature_height', 'INTEGER DEFAULT 40')
    ]

    for column_name, column_def in new_columns:
        try:
            cursor.execute(f'ALTER TABLE certificate_templates ADD COLUMN {column_name} {column_def}')
        except sqlite3.OperationalError:
            # Column already exists, skip
            pass

    conn.commit()
    conn.close()

# Initialize database on startup
init_database()

# JSON migration functions removed - all data now stored in database

# Config migration removed - configuration now stored in database

def create_default_certificate_template():
    """Create default certificate template if none exists"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()

    # Check if default template exists
    cursor.execute('SELECT COUNT(*) FROM certificate_templates WHERE is_default = 1')
    if cursor.fetchone()[0] == 0:
        print("Creating default certificate template...")

        template_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO certificate_templates (
                id, name, title, subtitle, header_text, footer_text, company_name, logo_url, signature_url, signature_name, signature_title,
                font_size_title, font_size_subtitle, font_size_module, font_size_date, font_size_header, font_size_footer, font_size_signature,
                margin_top, margin_subtitle, margin_module, margin_date, margin_footer, margin_signature,
                logo_width, logo_height, signature_width, signature_height,
                background_color, text_color, is_default, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            template_id,
            'Default Certificate',
            'Certificate of Completion',
            'This certifies that you have successfully completed:',
            'Official Transcript', # Default header_text
            'Congratulations on your achievement!', # Default footer_text
            'Your Company', # Default company_name
            '', # Default logo_url
            '', # Default signature_url
            '', # Default signature_name
            '', # Default signature_title
            24, 16, 20, 12, 14, 10, 12, # Font sizes
            100, 200, 250, 350, 400, 420, # Margins
            100, 50, 150, 40, # Logo and signature dimensions
            '#ffffff', '#000000',
            1,
            datetime.now().isoformat()
        ))

        print("Default certificate template created")

    conn.commit()
    conn.close()

# Run configuration migration and create default template
# Migration call removed - config already in database
create_default_certificate_template()

# Load configuration from database
def load_config():
    """Load configuration from SQLite database"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()

    cursor.execute('SELECT key, value, data_type FROM site_config')
    config_rows = cursor.fetchall()
    conn.close()

    if not config_rows:
        # Return default configuration if none exists
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

    # Reconstruct nested configuration from flattened database format
    config = {}
    for key, value, data_type in config_rows:
        if data_type == 'json':
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value
        else:
            parsed_value = value

        # Handle nested keys (e.g., "header_customization.title_color")
        keys = key.split('.')
        current = config
        for i, k in enumerate(keys[:-1]):
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = parsed_value

    return config

def save_config(config):
    """Save configuration to SQLite database"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()

    # Clear existing configuration
    cursor.execute('DELETE FROM site_config')

    # Flatten configuration and insert into database
    def insert_config_recursive(prefix, data):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                insert_config_recursive(full_key, value)
            else:
                cursor.execute(
                    'INSERT INTO site_config (key, value, data_type) VALUES (?, ?, ?)',
                    (full_key, json.dumps(value) if not isinstance(value, str) else value, 
                     'json' if not isinstance(value, str) else 'string')
                )

    insert_config_recursive('', config)

    conn.commit()
    conn.close()

# Certificate template management functions
def get_certificate_templates():
    """Get all certificate templates from database"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, name, title, subtitle, header_text, footer_text, company_name, logo_url, signature_url, signature_name, signature_title,
               font_size_title, font_size_subtitle, font_size_module, font_size_date, font_size_header, font_size_footer, font_size_signature,
               margin_top, margin_subtitle, margin_module, margin_date, margin_footer, margin_signature,
               logo_width, logo_height, signature_width, signature_height,
               background_color, text_color, is_default, created_at
        FROM certificate_templates ORDER BY is_default DESC, name ASC
    ''')

    templates = []
    for row in cursor.fetchall():
        template = {
            'id': row[0],
            'name': row[1],
            'title': row[2],
            'subtitle': row[3],
            'header_text': row[4],
            'footer_text': row[5],
            'company_name': row[6],
            'logo_url': row[7],
            'signature_url': row[8],
            'signature_name': row[9],
            'signature_title': row[10],
            'font_size_title': row[11],
            'font_size_subtitle': row[12],
            'font_size_module': row[13],
            'font_size_date': row[14],
            'font_size_header': row[15],
            'font_size_footer': row[16],
            'font_size_signature': row[17],
            'margin_top': row[18],
            'margin_subtitle': row[19],
            'margin_module': row[20],
            'margin_date': row[21],
            'margin_footer': row[22],
            'margin_signature': row[23],
            'logo_width': row[24],
            'logo_height': row[25],
            'signature_width': row[26],
            'signature_height': row[27],
            'background_color': row[28],
            'text_color': row[29],
            'is_default': row[30],
            'created_at': row[31]
        }
        templates.append(template)

    conn.close()
    return templates

def get_certificate_template(template_id):
    """Get a specific certificate template by ID"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, name, title, subtitle, header_text, footer_text, company_name, logo_url, signature_url, signature_name, signature_title,
               font_size_title, font_size_subtitle, font_size_module, font_size_date, font_size_header, font_size_footer, font_size_signature,
               margin_top, margin_subtitle, margin_module, margin_date, margin_footer, margin_signature,
               logo_width, logo_height, signature_width, signature_height,
               background_color, text_color, is_default, created_at
        FROM certificate_templates WHERE id = ?
    ''', (template_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        'id': row[0],
        'name': row[1],
        'title': row[2],
        'subtitle': row[3],
        'header_text': row[4],
        'footer_text': row[5],
        'company_name': row[6],
        'logo_url': row[7],
        'signature_url': row[8],
        'signature_name': row[9],
        'signature_title': row[10],
        'font_size_title': row[11],
        'font_size_subtitle': row[12],
        'font_size_module': row[13],
        'font_size_date': row[14],
        'font_size_header': row[15],
        'font_size_footer': row[16],
        'font_size_signature': row[17],
        'margin_top': row[18],
        'margin_subtitle': row[19],
        'margin_module': row[20],
        'margin_date': row[21],
        'margin_footer': row[22],
        'margin_signature': row[23],
        'logo_width': row[24],
        'logo_height': row[25],
        'signature_width': row[26],
        'signature_height': row[27],
        'background_color': row[28],
        'text_color': row[29],
        'is_default': row[30],
        'created_at': row[31]
    }

def get_default_certificate_template():
    """Get the default certificate template"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, name, title, subtitle, header_text, footer_text, company_name, logo_url, signature_url, signature_name, signature_title,
               font_size_title, font_size_subtitle, font_size_module, font_size_date, font_size_header, font_size_footer, font_size_signature,
               margin_top, margin_subtitle, margin_module, margin_date, margin_footer, margin_signature,
               logo_width, logo_height, signature_width, signature_height,
               background_color, text_color, is_default, created_at
        FROM certificate_templates WHERE is_default = 1 LIMIT 1
    ''')

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        'id': row[0],
        'name': row[1],
        'title': row[2],
        'subtitle': row[3],
        'header_text': row[4],
        'footer_text': row[5],
        'company_name': row[6],
        'logo_url': row[7],
        'signature_url': row[8],
        'signature_name': row[9],
        'signature_title': row[10],
        'font_size_title': row[11],
        'font_size_subtitle': row[12],
        'font_size_module': row[13],
        'font_size_date': row[14],
        'font_size_header': row[15],
        'font_size_footer': row[16],
        'font_size_signature': row[17],
        'margin_top': row[18],
        'margin_subtitle': row[19],
        'margin_module': row[20],
        'margin_date': row[21],
        'margin_footer': row[22],
        'margin_signature': row[23],
        'logo_width': row[24],
        'logo_height': row[25],
        'signature_width': row[26],
        'signature_height': row[27],
        'background_color': row[28],
        'text_color': row[29],
        'is_default': row[30],
        'created_at': row[31]
    }

def save_certificate_template(template_data):
    """Save or update a certificate template"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()

    # If this is set as default, unset all other defaults
    if template_data.get('is_default'):
        cursor.execute('UPDATE certificate_templates SET is_default = 0')

    if template_data.get('id'):
        # Update existing template
        cursor.execute('''
            UPDATE certificate_templates SET
                name = ?, title = ?, subtitle = ?, header_text = ?, footer_text = ?, company_name = ?, logo_url = ?, signature_url = ?, signature_name = ?, signature_title = ?,
                font_size_title = ?, font_size_subtitle = ?, font_size_module = ?, font_size_date = ?, font_size_header = ?, font_size_footer = ?, font_size_signature = ?,
                margin_top = ?, margin_subtitle = ?, margin_module = ?, margin_date = ?, margin_footer = ?, margin_signature = ?,
                logo_width = ?, logo_height = ?, signature_width = ?, signature_height = ?,
                background_color = ?, text_color = ?, is_default = ?
            WHERE id = ?
        ''', (
            template_data['name'],
            template_data['title'],
            template_data['subtitle'],
            template_data.get('header_text', ''),
            template_data.get('footer_text', ''),
            template_data.get('company_name', ''),
            template_data.get('logo_url', ''),
            template_data.get('signature_url', ''),
            template_data.get('signature_name', ''),
            template_data.get('signature_title', ''),
            template_data['font_size_title'],
            template_data['font_size_subtitle'],
            template_data['font_size_module'],
            template_data['font_size_date'],
            template_data['font_size_header'],
            template_data['font_size_footer'],
            template_data['font_size_signature'],
            template_data['margin_top'],
            template_data['margin_subtitle'],
            template_data['margin_module'],
            template_data['margin_date'],
            template_data['margin_footer'],
            template_data['margin_signature'],
            template_data['logo_width'],
            template_data['logo_height'],
            template_data['signature_width'],
            template_data['signature_height'],
            template_data['background_color'],
            template_data['text_color'],
            template_data.get('is_default', 0),
            template_data['id']
        ))
    else:
        # Create new template
        template_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO certificate_templates (
                id, name, title, subtitle, header_text, footer_text, company_name, logo_url, signature_url, signature_name, signature_title,
                font_size_title, font_size_subtitle, font_size_module, font_size_date, font_size_header, font_size_footer, font_size_signature,
                margin_top, margin_subtitle, margin_module, margin_date, margin_footer, margin_signature,
                logo_width, logo_height, signature_width, signature_height,
                background_color, text_color, is_default, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            template_id,
            template_data['name'],
            template_data['title'],
            template_data['subtitle'],
            template_data.get('header_text', ''),
            template_data.get('footer_text', ''),
            template_data.get('company_name', ''),
            template_data.get('logo_url', ''),
            template_data.get('signature_url', ''),
            template_data.get('signature_name', ''),
            template_data.get('signature_title', ''),
            template_data['font_size_title'],
            template_data['font_size_subtitle'],
            template_data['font_size_module'],
            template_data['font_size_date'],
            template_data['font_size_header'],
            template_data['font_size_footer'],
            template_data['font_size_signature'],
            template_data['margin_top'],
            template_data['margin_subtitle'],
            template_data['margin_module'],
            template_data['margin_date'],
            template_data['margin_footer'],
            template_data['margin_signature'],
            template_data['logo_width'],
            template_data['logo_height'],
            template_data['signature_width'],
            template_data['signature_height'],
            template_data['background_color'],
            template_data['text_color'],
            template_data.get('is_default', 0),
            datetime.now().isoformat()
        ))
        template_data['id'] = template_id

    conn.commit()
    conn.close()
    return template_data['id']

def delete_certificate_template(template_id):
    """Delete a certificate template"""
    conn = sqlite3.connect('data/tutorial_platform.db')
    cursor = conn.cursor()

    # Don't allow deleting the default template
    cursor.execute('SELECT is_default FROM certificate_templates WHERE id = ?', (template_id,))
    result = cursor.fetchone()

    if result and result[0] == 1:
        conn.close()
        return False, "Cannot delete the default template"

    cursor.execute('DELETE FROM certificate_templates WHERE id = ?', (template_id,))

    conn.commit()
    conn.close()
    return True, "Template deleted successfully"

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
    """Save module content to database with backward-compatible timestamps"""
    conn = None
    try:
        conn = sqlite3.connect('data/tutorial_platform.db')
        conn.execute('PRAGMA foreign_keys=ON')  # Enable foreign key constraints
        cursor = conn.cursor()

        # Check if the table has timestamp columns
        cursor.execute("PRAGMA table_info(module_content)")
        columns = [column[1] for column in cursor.fetchall()]
        has_timestamps = 'created_at' in columns and 'updated_at' in columns

        # Check if content already exists
        cursor.execute('SELECT content FROM module_content WHERE module_id = ?', (module_id,))
        existing = cursor.fetchone()

        current_time = datetime.now().isoformat()

        if existing:
            # Update existing content
            if has_timestamps:
                cursor.execute('''
                    UPDATE module_content 
                    SET content = ?, updated_at = ?
                    WHERE module_id = ?
                ''', (content, current_time, module_id))
            else:
                cursor.execute('''
                    UPDATE module_content 
                    SET content = ?
                    WHERE module_id = ?
                ''', (content, module_id))
        else:
            # Insert new content
            if has_timestamps:
                cursor.execute('''
                    INSERT INTO module_content (module_id, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (module_id, content, current_time, current_time))
            else:
                cursor.execute('''
                    INSERT INTO module_content (module_id, content)
                    VALUES (?, ?)
                ''', (module_id, content))

        conn.commit()
    finally:
        if conn:
            conn.close()

def load_module_content(module_id):
    """Load module content from database with legacy file migration"""
    conn = None
    try:
        conn = sqlite3.connect('data/tutorial_platform.db')
        conn.execute('PRAGMA foreign_keys=ON')  # Enable foreign key constraints
        cursor = conn.cursor()

        cursor.execute('SELECT content FROM module_content WHERE module_id = ?', (module_id,))
        result = cursor.fetchone()

        if result:
            return result[0]

        # Check for legacy HTML file and migrate it
        legacy_file_path = f'data/modules/{module_id}.html'
        if os.path.exists(legacy_file_path):
            try:
                with open(legacy_file_path, 'r', encoding='utf-8') as f:
                    legacy_content = f.read()

                # Save legacy content to database
                save_module_content(module_id, legacy_content)

                # Return the migrated content
                return legacy_content
            except Exception as e:
                print(f"Error migrating legacy content for module {module_id}: {e}")

        return None
    finally:
        if conn:
            conn.close()

# Load progress data
# Progress functions now use database - these JSON functions are removed
# All progress data is handled through user_progress table

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

# Global no-cache policy for all dynamic content
@app.after_request
def add_no_cache_headers(response):
    """Add no-cache headers to all dynamic responses to ensure fresh content loading"""
    # Only add no-cache headers to dynamic content, not static assets
    if (response.content_type and 
        (response.content_type.startswith('text/html') or 
         response.content_type.startswith('application/json'))):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

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
    response = make_response(render_template('index.html', 
                                           courses=courses_data,
                                           config=config))
    # Add no-cache headers to ensure fresh content loading
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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

    # Load module content from database and sanitize it
    raw_content = load_module_content(module_id)
    if raw_content:
        module['content'] = Markup(sanitize_html(raw_content))
    else:
        module['content'] = Markup("<p>No content available for this module.</p>")

    config = load_config()
    response = make_response(render_template('module.html', 
                                           module=module,
                                           config=config))
    # Add no-cache headers to ensure fresh content loading
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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

    # Get certificate template
    template = get_default_certificate_template()

    # If no template exists, create a default one
    if not template:
        default_template_data = {
            'name': 'Default Certificate',
            'title': 'Certificate of Completion',
            'subtitle': 'This certifies that you have successfully completed:',
            'header_text': 'Official Transcript',
            'footer_text': 'Congratulations on your achievement!',
            'company_name': 'Your Company',
            'logo_url': '',
            'signature_url': '',
            'signature_name': '',
            'signature_title': '',
            'font_size_title': 28,
            'font_size_subtitle': 16,
            'font_size_module': 22,
            'font_size_date': 12,
            'font_size_header': 14,
            'font_size_footer': 10,
            'font_size_signature': 12,
            'margin_top': 100,
            'margin_subtitle': 200,
            'margin_module': 250,
            'margin_date': 350,
            'margin_footer': 400,
            'margin_signature': 420,
            'logo_width': 100,
            'logo_height': 50,
            'signature_width': 150,
            'signature_height': 40,
            'background_color': '#FFFFFF',
            'text_color': '#000000',
            'is_default': 1
        }
        save_certificate_template(default_template_data)
        template = default_template_data

    # Generate PDF certificate using template
    filename = f"certificate_{module_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join("static", "resources", filename)

    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    # Parse colors (hex to RGB)
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        return (0, 0, 0)

    # Set background color
    bg_color = hex_to_rgb(template['background_color'])
    c.setFillColorRGB(*bg_color)
    c.rect(0, 0, width, height, fill=True, stroke=False)

    # Set text color
    text_color = hex_to_rgb(template['text_color'])
    c.setFillColorRGB(*text_color)

    # Add Company Logo
    if template.get('logo_url'):
        try:
            logo_path = template['logo_url'].lstrip('/') # Assuming logo_url is relative to static folder
            if not os.path.exists(logo_path): # If the URL path doesn't exist, try treating it as a file path directly
                logo_path = os.path.join('static', template['logo_url'].lstrip('/'))
            
            if os.path.exists(logo_path):
                c.drawInlineImage(logo_path, 
                                  (width - template['logo_width']) / 2, 
                                  height - template['margin_top'] - template['logo_height'],
                                  width=template['logo_width'], 
                                  height=template['logo_height'])
            else:
                print(f"Warning: Logo not found at {logo_path}")
        except Exception as e:
            print(f"Error drawing logo: {e}")

    # Certificate title
    c.setFont("Helvetica-Bold", template['font_size_title'])
    text = template['title']
    title_y = height - template['margin_top'] - (template['logo_height'] if template.get('logo_url') else 0) - (template['font_size_title'] * 0.5) # Adjust y based on logo
    c.drawCentredString(width / 2, title_y, text)

    # Certificate subtitle
    c.setFont("Helvetica", template['font_size_subtitle'])
    text = template['subtitle']
    subtitle_y = height - template['margin_subtitle']
    c.drawCentredString(width / 2, subtitle_y, text)

    # Module name
    c.setFont("Helvetica-Bold", template['font_size_module'])
    text = module['title']
    module_y = height - template['margin_module']
    c.drawCentredString(width / 2, module_y, text)

    # Date
    c.setFont("Helvetica", template['font_size_date'])
    text = f"Date: {datetime.now().strftime('%B %d, %Y')}"
    date_y = height - template['margin_date']
    c.drawCentredString(width / 2, date_y, text)

    # Header text (if provided)
    if template.get('header_text'):
        c.setFont("Helvetica-Bold", template['font_size_header'])
        text = template['header_text']
        header_y = height - template['margin_top'] / 2 # Position header above title
        c.drawCentredString(width / 2, header_y, text)

    # Footer text (if provided)
    if template.get('footer_text'):
        c.setFont("Helvetica", template['font_size_footer'])
        text = template['footer_text']
        footer_y = height - template['margin_footer']
        c.drawCentredString(width / 2, footer_y, text)

    # Signature
    if template.get('signature_url'):
        try:
            sig_path = template['signature_url'].lstrip('/')
            if not os.path.exists(sig_path):
                sig_path = os.path.join('static', template['signature_url'].lstrip('/'))

            if os.path.exists(sig_path):
                # Position signature based on margin_signature
                signature_base_y = height - template['margin_signature']
                
                # Draw the signature image
                c.drawInlineImage(sig_path,
                                  (width - template['signature_width']) / 2,
                                  signature_base_y - template['signature_height'],
                                  width=template['signature_width'],
                                  height=template['signature_height'])
                
                # Draw signature name and title below the signature image
                c.setFont("Helvetica-Bold", template['font_size_signature'])
                name_y = signature_base_y - template['signature_height'] - 15 # Position below image
                c.drawCentredString(width / 2, name_y, template['signature_name'])

                c.setFont("Helvetica", template['font_size_signature'] - 1) # Slightly smaller for title
                title_y = name_y - 15 # Position below name
                c.drawCentredString(width / 2, title_y, template['signature_title'])
            else:
                print(f"Warning: Signature not found at {sig_path}")
        except Exception as e:
            print(f"Error drawing signature: {e}")

    c.save()

    @after_this_request
    def remove_file(response):
        try:
            os.remove(filepath)
        except OSError:
            pass
        return response

    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

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
                    model="gpt-4o",
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

        # Add module to courses data first (this creates the module in database)
        courses_data = load_courses()
        courses_data['modules'].append(module_data)
        save_courses(courses_data)

        # Save module content to database (after module exists)
        if content:
            save_module_content(module_id, content)

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

        # Only save content if the form includes the content field
        if 'content' in request.form:
            save_module_content(module_id, request.form.get('content', ''))

        save_courses(courses_data)
        flash('Module updated successfully', 'success')
        return redirect(url_for('admin_dashboard'))

    # Load module content from database
    module['content'] = load_module_content(module_id) or ''

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
        # Export configuration and data from database to JSON files for backup
        # Note: Configuration and data are now stored in SQLite database
        # This export creates temporary JSON files for backup compatibility

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

# Certificate template management routes
@app.route('/admin/certificate-templates')
@require_admin
def admin_certificate_templates():
    templates = get_certificate_templates()
    config = load_config()
    return render_template('admin/certificate_templates.html', 
                         templates=templates,
                         config=config)

@app.route('/admin/certificate-template/new', methods=['GET', 'POST'])
@require_admin
def admin_new_certificate_template():
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid CSRF token', 'error')
            return redirect(url_for('admin_new_certificate_template'))

        template_data = {
            'name': request.form.get('name'),
            'title': request.form.get('title'),
            'subtitle': request.form.get('subtitle'),
            'header_text': request.form.get('header_text', ''),
            'footer_text': request.form.get('footer_text', ''),
            'company_name': request.form.get('company_name', ''),
            'logo_url': request.form.get('logo_url', ''),
            'signature_url': request.form.get('signature_url', ''),
            'signature_name': request.form.get('signature_name', ''),
            'signature_title': request.form.get('signature_title', ''),
            'font_size_title': int(request.form.get('font_size_title', 24)),
            'font_size_subtitle': int(request.form.get('font_size_subtitle', 16)),
            'font_size_module': int(request.form.get('font_size_module', 20)),
            'font_size_date': int(request.form.get('font_size_date', 12)),
            'font_size_header': int(request.form.get('font_size_header', 14)),
            'font_size_footer': int(request.form.get('font_size_footer', 10)),
            'font_size_signature': int(request.form.get('font_size_signature', 12)),
            'margin_top': int(request.form.get('margin_top', 100)),
            'margin_subtitle': int(request.form.get('margin_subtitle', 200)),
            'margin_module': int(request.form.get('margin_module', 250)),
            'margin_date': int(request.form.get('margin_date', 350)),
            'margin_footer': int(request.form.get('margin_footer', 400)),
            'margin_signature': int(request.form.get('margin_signature', 420)),
            'logo_width': int(request.form.get('logo_width', 100)),
            'logo_height': int(request.form.get('logo_height', 50)),
            'signature_width': int(request.form.get('signature_width', 150)),
            'signature_height': int(request.form.get('signature_height', 40)),
            'background_color': request.form.get('background_color', '#FFFFFF'),
            'text_color': request.form.get('text_color', '#000000'),
            'is_default': bool(request.form.get('is_default'))
        }

        if not template_data['name'] or not template_data['title']:
            flash('Name and title are required', 'error')
            return redirect(url_for('admin_new_certificate_template'))

        save_certificate_template(template_data)
        flash('Certificate template created successfully', 'success')
        return redirect(url_for('admin_certificate_templates'))

    config = load_config()
    return render_template('admin/certificate_template_form.html', 
                         config=config,
                         template=None,
                         action='Create')

@app.route('/admin/certificate-template/<template_id>/edit', methods=['GET', 'POST'])
@require_admin
def admin_edit_certificate_template(template_id):
    template = get_certificate_template(template_id)

    if not template:
        flash('Certificate template not found', 'error')
        return redirect(url_for('admin_certificate_templates'))

    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid CSRF token', 'error')
            return redirect(url_for('admin_edit_certificate_template', template_id=template_id))

        template_data = {
            'id': template_id,
            'name': request.form.get('name'),
            'title': request.form.get('title'),
            'subtitle': request.form.get('subtitle'),
            'header_text': request.form.get('header_text', ''),
            'footer_text': request.form.get('footer_text', ''),
            'company_name': request.form.get('company_name', ''),
            'logo_url': request.form.get('logo_url', ''),
            'signature_url': request.form.get('signature_url', ''),
            'signature_name': request.form.get('signature_name', ''),
            'signature_title': request.form.get('signature_title', ''),
            'font_size_title': int(request.form.get('font_size_title', 24)),
            'font_size_subtitle': int(request.form.get('font_size_subtitle', 16)),
            'font_size_module': int(request.form.get('font_size_module', 20)),
            'font_size_date': int(request.form.get('font_size_date', 12)),
            'font_size_header': int(request.form.get('font_size_header', 14)),
            'font_size_footer': int(request.form.get('font_size_footer', 10)),
            'font_size_signature': int(request.form.get('font_size_signature', 12)),
            'margin_top': int(request.form.get('margin_top', 100)),
            'margin_subtitle': int(request.form.get('margin_subtitle', 200)),
            'margin_module': int(request.form.get('margin_module', 250)),
            'margin_date': int(request.form.get('margin_date', 350)),
            'margin_footer': int(request.form.get('margin_footer', 400)),
            'margin_signature': int(request.form.get('margin_signature', 420)),
            'logo_width': int(request.form.get('logo_width', 100)),
            'logo_height': int(request.form.get('logo_height', 50)),
            'signature_width': int(request.form.get('signature_width', 150)),
            'signature_height': int(request.form.get('signature_height', 40)),
            'background_color': request.form.get('background_color', '#FFFFFF'),
            'text_color': request.form.get('text_color', '#000000'),
            'is_default': bool(request.form.get('is_default'))
        }

        if not template_data['name'] or not template_data['title']:
            flash('Name and title are required', 'error')
            return redirect(url_for('admin_edit_certificate_template', template_id=template_id))

        save_certificate_template(template_data)
        flash('Certificate template updated successfully', 'success')
        return redirect(url_for('admin_certificate_templates'))

    config = load_config()
    return render_template('admin/certificate_template_form.html', 
                         config=config,
                         template=template,
                         action='Edit')

@app.route('/admin/certificate-template/<template_id>/delete', methods=['POST'])
@require_admin
def admin_delete_certificate_template(template_id):
    if not validate_csrf_token():
        return jsonify({'error': 'Invalid CSRF token'}), 403

    success, message = delete_certificate_template(template_id)

    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': message}), 400

@app.route('/admin/certificate-template/<template_id>/set-default', methods=['POST'])
@require_admin
def admin_set_default_certificate_template(template_id):
    if not validate_csrf_token():
        return jsonify({'error': 'Invalid CSRF token'}), 403

    template = get_certificate_template(template_id)

    if not template:
        return jsonify({'error': 'Template not found'}), 404

    # Update template to set as default
    template['is_default'] = 1
    save_certificate_template(template)

    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)