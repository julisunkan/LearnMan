# Overview

This is a comprehensive Flask-based tutorial platform designed for creating and delivering interactive learning content. The application provides a complete learning management system with course modules, quizzes, progress tracking, and certificate generation. It features a user-friendly interface for learners and a powerful admin panel for content management, including web scraping capabilities and AI-powered quiz generation.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Flask with single-file architecture (app.py as main application)
- **Data Storage**: File-based JSON storage system with separate files for courses, feedback, and progress data
- **Session Management**: Flask sessions with configurable SECRET_KEY environment variable
- **File Handling**: Support for video, image, and resource file management with automatic image resizing
- **PDF Generation**: ReportLab integration for certificate generation
- **Content Processing**: Markdown rendering and HTML content sanitization

## Frontend Architecture
- **Template Engine**: Jinja2 templates with Bootstrap 5 for responsive design
- **JavaScript**: Vanilla JavaScript split into main.js (user features) and admin.js (admin panel)
- **Responsive Design**: Mobile-first approach with CSS custom properties and gradient-based card layouts
- **Progressive Web App**: PWA capabilities with service worker support
- **Rich Text Editing**: CKEditor 5 integration for WYSIWYG content creation

## Authentication & Security
- **User Access**: No authentication required for learners
- **Admin Access**: Passcode-based authentication system
- **Security Features**: CSRF protection, input validation, SSRF protection for URL imports
- **Session Security**: Secure session management with configurable secret keys

## Data Management
- **Progress Tracking**: localStorage-based system for user progress without accounts
- **Content Storage**: JSON-based module storage with support for rich HTML content
- **File Organization**: Static file serving for videos, images, and downloadable resources
- **Configuration**: JSON-based configuration system for site customization

## Learning Features
- **Module System**: Video-based learning modules with HTML5 player integration
- **Interactive Quizzes**: Multiple choice and true/false question support
- **Progress Tracking**: Module completion tracking and certificate generation
- **Note-Taking**: Per-module note functionality with localStorage persistence
- **Bookmarking**: User bookmark system for favorite modules

## Admin Panel Features
- **Content Management**: Full CRUD operations for modules and quizzes
- **Rich Editor**: CKEditor 5 integration for content creation
- **Media Management**: Image upload with automatic resizing and video URL integration
- **Module Reordering**: Drag-and-drop functionality using SortableJS
- **Import System**: Web scraping capabilities for content import from URLs

# External Dependencies

## Core Framework Dependencies
- **Flask**: Web framework for Python applications
- **Werkzeug**: WSGI utility library for secure filename handling and file uploads
- **Jinja2**: Template engine (included with Flask)

## Content Processing
- **Pillow (PIL)**: Image processing library for automatic resizing to 800x500px
- **Markdown**: Markdown to HTML conversion for rich content rendering
- **Trafilatura**: Web scraping library for extracting text content from URLs
- **ReportLab**: PDF generation library for certificates

## Frontend Libraries (CDN)
- **Bootstrap 5**: CSS framework for responsive design
- **CKEditor 5**: WYSIWYG rich text editor for content creation
- **SortableJS**: Drag-and-drop functionality for module reordering

## AI Integration
- **OpenAI**: GPT integration for automated quiz generation from imported content
- **Environment Variable**: OPENAI_API_KEY for API access

## File Storage
- **JSON Files**: Local file system storage for courses.json, feedback.json, progress.json, and config.json
- **Static Assets**: File system storage for uploaded images, videos, and resources
- **Upload Handling**: 16MB maximum file size with secure filename processing

## Configuration
- **Environment Variables**: SESSION_SECRET for session security, OPENAI_API_KEY for AI features
- **JSON Configuration**: Site title, description, admin passcode, and file size limits
- **Static File Serving**: Flask static file handling for media and resource delivery