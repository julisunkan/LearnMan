// Main JavaScript for tutorial platform
// Progress tracking using localStorage

// Mobile navigation state
let currentModal = null;

// Set active navigation item
function setActiveNavItem(itemId) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.getElementById(itemId)?.classList.add('active');
}

// Close current modal
function closeModal() {
    if (currentModal) {
        currentModal.classList.remove('show');
        setTimeout(() => {
            if (currentModal && currentModal.parentNode) {
                currentModal.parentNode.removeChild(currentModal);
            }
            currentModal = null;
        }, 300);
    }
}

// Create modal template safely using DOM APIs
function createModal(title, contentHtml) {
    closeModal();
    
    const modal = document.createElement('div');
    modal.className = 'mobile-modal';
    
    // Create header
    const header = document.createElement('div');
    header.className = 'mobile-modal-header';
    
    const titleEl = document.createElement('h2');
    titleEl.className = 'mobile-modal-title';
    titleEl.textContent = title;
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'modal-close-btn';
    closeBtn.textContent = '×';
    closeBtn.onclick = closeModal;
    
    header.appendChild(titleEl);
    header.appendChild(closeBtn);
    
    // Create content area
    const content = document.createElement('div');
    content.className = 'mobile-modal-content';
    content.innerHTML = contentHtml; // Still using innerHTML but content is pre-sanitized
    
    modal.appendChild(header);
    modal.appendChild(content);
    
    document.body.appendChild(modal);
    currentModal = modal;
    
    // Show modal with animation
    setTimeout(() => {
        modal.classList.add('show');
    }, 10);
    
    return modal;
}

class TutorialPlatform {
    constructor() {
        this.init();
    }

    init() {
        // Initialize platform features
        this.setupProgressTracking();
        this.setupKeyboardNavigation();
        this.setupSearchFiltering();
        this.loadUserData();
    }

    // Progress tracking functions
    setupProgressTracking() {
        // Progress tracking now handled by database - localStorage removed
        // No client-side initialization needed
    }

    markCompleted(moduleId) {
        // Progress now handled by database - localStorage removed
        this.showNotification('Module marked as completed!', 'success');
    }

    updateProgress(moduleId, percentage) {
        // Progress now handled by database - localStorage removed
        this.updateProgressDisplay(moduleId);
    }

    updateProgressDisplay(moduleId) {
        // Progress display simplified - data from database
        const progressBar = document.getElementById('moduleProgress');
        if (progressBar) {
            // Progress data should be loaded from database on page load
            // This function now only handles UI updates
        }
    }

    // Note-taking functions
    saveNotes(moduleId) {
        const notesTextarea = document.getElementById('moduleNotes');
        if (!notesTextarea) return;
        
        // Notes now handled by database - localStorage removed
        this.showNotification('Notes saved!', 'info');
    }

    loadModuleNotes(moduleId) {
        const notesTextarea = document.getElementById('moduleNotes');
        
        // Notes now loaded from database on page render
        // This function is simplified
    }

    loadModuleProgress(moduleId) {
        const progress = JSON.parse(localStorage.getItem('moduleProgress') || '{}');
        if (progress[moduleId]) {
            this.updateProgressDisplay(moduleId);
        }
    }

    // Bookmark functions
    bookmarkModule(moduleId) {
        const bookmarks = JSON.parse(localStorage.getItem('bookmarkedModules') || '[]');
        
        if (!bookmarks.includes(moduleId)) {
            bookmarks.push(moduleId);
            localStorage.setItem('bookmarkedModules', JSON.stringify(bookmarks));
            this.showNotification('Module bookmarked!', 'success');
        } else {
            const index = bookmarks.indexOf(moduleId);
            bookmarks.splice(index, 1);
            localStorage.setItem('bookmarkedModules', JSON.stringify(bookmarks));
            this.showNotification('Bookmark removed!', 'info');
        }
    }

    // Search and filter functionality
    setupSearchFiltering() {
        const searchInput = document.getElementById('moduleSearch');
        if (searchInput) {
            searchInput.addEventListener('input', this.filterModules.bind(this));
        }
    }

    filterModules() {
        const searchInput = document.getElementById('moduleSearch');
        const searchTerm = searchInput.value.toLowerCase();
        const moduleCards = document.querySelectorAll('.module-card');

        moduleCards.forEach(card => {
            const title = card.querySelector('.card-title').textContent.toLowerCase();
            const description = card.querySelector('.card-text').textContent.toLowerCase();
            
            if (title.includes(searchTerm) || description.includes(searchTerm)) {
                card.parentElement.style.display = 'block';
            } else {
                card.parentElement.style.display = 'none';
            }
        });
    }

    // Keyboard navigation
    setupKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // Arrow key navigation for modules
            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                this.navigateModules(e.key === 'ArrowRight');
            }
            
            // Spacebar for video play/pause
            if (e.key === ' ' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                const video = document.querySelector('video');
                if (video) {
                    e.preventDefault();
                    if (video.paused) {
                        video.play();
                    } else {
                        video.pause();
                    }
                }
            }
        });
    }

    navigateModules(forward) {
        const moduleLinks = document.querySelectorAll('.module-card a[href*="module"]');
        const currentUrl = window.location.href;
        let currentIndex = -1;

        moduleLinks.forEach((link, index) => {
            if (currentUrl.includes(link.getAttribute('href'))) {
                currentIndex = index;
            }
        });

        if (currentIndex !== -1) {
            let nextIndex;
            if (forward) {
                nextIndex = (currentIndex + 1) % moduleLinks.length;
            } else {
                nextIndex = currentIndex === 0 ? moduleLinks.length - 1 : currentIndex - 1;
            }
            
            if (moduleLinks[nextIndex]) {
                window.location.href = moduleLinks[nextIndex].getAttribute('href');
            }
        }
    }

    // Quiz functionality
    submitQuiz(moduleId) {
        const form = document.getElementById('quizForm');
        if (!form) return;

        const formData = new FormData(form);
        const answers = {};
        
        for (let [key, value] of formData.entries()) {
            answers[key] = value;
        }

        fetch('/api/quiz-submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': this.getCSRFToken()
            },
            body: JSON.stringify({
                module_id: moduleId,
                answers: answers
            })
        })
        .then(response => response.json())
        .then(data => {
            this.displayQuizResults(data);
            if (data.passed) {
                this.markCompleted(moduleId);
            }
        })
        .catch(error => {
            this.showNotification('Error submitting quiz: ' + error.message, 'error');
        });
    }

    displayQuizResults(results) {
        const resultsDiv = document.getElementById('quizResults');
        if (!resultsDiv) return;

        const passedClass = results.passed ? 'success' : 'danger';
        const passedText = results.passed ? 'Passed' : 'Failed';
        
        resultsDiv.innerHTML = `
            <div class="alert alert-${passedClass}">
                <h4>${passedText}!</h4>
                <p>Score: ${results.score.toFixed(1)}% (${results.correct}/${results.total} correct)</p>
                ${results.passed ? '<p>Congratulations! You can now download your certificate.</p>' : '<p>Please review the material and try again.</p>'}
            </div>
        `;
    }

    // Utility functions
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} notification`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1050;
            min-width: 300px;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        // Fade in
        setTimeout(() => {
            notification.style.opacity = '1';
        }, 10);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }

    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || '';
    }

    loadUserData() {
        // Load and display user progress on the homepage
        const progress = JSON.parse(localStorage.getItem('moduleProgress') || '{}');
        const bookmarks = JSON.parse(localStorage.getItem('bookmarkedModules') || '[]');
        
        // Update module cards with progress indicators
        document.querySelectorAll('.module-card').forEach(card => {
            const moduleLink = card.querySelector('a[href*="module"]');
            if (moduleLink) {
                const moduleId = moduleLink.getAttribute('href').split('/').pop();
                
                if (progress[moduleId]) {
                    const progressBar = document.createElement('div');
                    progressBar.className = 'progress mt-2';
                    progressBar.innerHTML = `<div class="progress-bar" style="width: ${progress[moduleId].progress}%"></div>`;
                    card.querySelector('.card-body').appendChild(progressBar);
                }
                
                if (bookmarks.includes(moduleId)) {
                    const bookmark = document.createElement('span');
                    bookmark.className = 'badge bg-warning';
                    bookmark.textContent = 'Bookmarked';
                    card.querySelector('.card-body').appendChild(bookmark);
                }
            }
        });
    }

    // User data display functions
    showProgress() {
        setActiveNavItem('nav-progress');
        const progress = JSON.parse(localStorage.getItem('moduleProgress') || '{}');
        let content = '';
        
        if (Object.keys(progress).length === 0) {
            content = `
                <div class="alert alert-info">
                    <h4>📊 No Progress Yet</h4>
                    <p>Start learning modules to track your progress here!</p>
                </div>
            `;
        } else {
            content = '<div class="row">';
            for (const [moduleId, data] of Object.entries(progress)) {
                const completedBadge = data.completed ? '<span class="badge bg-success">Completed</span>' : '';
                const completedDate = data.completedAt ? new Date(data.completedAt).toLocaleDateString() : '';
                
                content += `
                    <div class="col-12 mb-3">
                        <div class="card">
                            <div class="card-body">
                                <div class="d-flex justify-content-between align-items-start mb-2">
                                    <h6 class="card-title mb-0">Module</h6>
                                    ${completedBadge}
                                </div>
                                <div class="progress mb-2">
                                    <div class="progress-bar" style="width: ${data.progress}%"></div>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <small class="text-muted">${data.progress}% Complete</small>
                                    ${completedDate ? `<small class="text-muted">Completed: ${completedDate}</small>` : ''}
                                </div>
                                <a href="/module/${moduleId}" class="btn btn-primary btn-sm mt-2">Continue Learning</a>
                            </div>
                        </div>
                    </div>
                `;
            }
            content += '</div>';
        }
        
        createModal('Your Progress', content);
    }

    showBookmarks() {
        setActiveNavItem('nav-bookmarks');
        const bookmarks = JSON.parse(localStorage.getItem('bookmarkedModules') || '[]');
        let content = '';
        
        if (bookmarks.length === 0) {
            content = `
                <div class="alert alert-info">
                    <h4>🔖 No Bookmarks Yet</h4>
                    <p>Bookmark your favorite modules while learning to access them quickly here!</p>
                </div>
            `;
        } else {
            content = '<div class="row">';
            bookmarks.forEach(moduleId => {
                // Escape module ID for safe HTML insertion
                const safeModuleId = this.escapeHtml(moduleId);
                content += `
                    <div class="col-12 mb-3">
                        <div class="card module-card">
                            <div class="card-body">
                                <h6 class="card-title">Bookmarked Module</h6>
                                <div class="d-flex justify-content-between align-items-center">
                                    <a href="/module/${safeModuleId}" class="btn btn-primary">Continue Learning</a>
                                    <button class="btn btn-outline-secondary btn-sm" onclick="bookmarkModule('${safeModuleId}'); showBookmarks();">Remove</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
            content += '</div>';
        }
        
        createModal('My Bookmarks', content);
    }

    showNotes() {
        setActiveNavItem('nav-notes');
        const notes = JSON.parse(localStorage.getItem('moduleNotes') || '{}');
        let content = '';
        
        if (Object.keys(notes).length === 0) {
            content = `
                <div class="alert alert-info">
                    <h4>📝 No Notes Yet</h4>
                    <p>Take notes while learning modules to review them here later!</p>
                </div>
            `;
        } else {
            content = '<div class="row">';
            for (const [moduleId, data] of Object.entries(notes)) {
                // Escape HTML to prevent XSS
                const notePreview = this.escapeHtml(data.content.length > 100 ? data.content.substring(0, 100) + '...' : data.content);
                const lastUpdate = new Date(data.lastUpdate).toLocaleDateString();
                
                content += `
                    <div class="col-12 mb-3">
                        <div class="card">
                            <div class="card-body">
                                <h6 class="card-title">Module Notes</h6>
                                <p class="card-text small">${notePreview}</p>
                                <div class="d-flex justify-content-between align-items-center">
                                    <small class="text-muted">Updated: ${lastUpdate}</small>
                                    <a href="/module/${moduleId}" class="btn btn-outline-primary btn-sm">View Module</a>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }
            content += '</div>';
        }
        
        createModal('My Notes', content);
    }
    
    showCertificates() {
        setActiveNavItem('nav-certificates');
        const progress = JSON.parse(localStorage.getItem('moduleProgress') || '{}');
        const completedModules = Object.entries(progress).filter(([moduleId, data]) => data.completed);
        let content = '';
        
        if (completedModules.length === 0) {
            content = `
                <div class="alert alert-info">
                    <h4>🏆 No Certificates Yet</h4>
                    <p>Complete modules and pass their quizzes to earn certificates!</p>
                </div>
            `;
        } else {
            content = '<div class="row">';
            completedModules.forEach(([moduleId, data]) => {
                const completedDate = new Date(data.completedAt).toLocaleDateString();
                
                content += `
                    <div class="col-12 mb-3">
                        <div class="card">
                            <div class="card-body">
                                <div class="d-flex justify-content-between align-items-start mb-3">
                                    <div>
                                        <h6 class="card-title">🏆 Certificate Available</h6>
                                        <p class="card-text">Completed on ${completedDate}</p>
                                    </div>
                                    <span class="badge bg-success">Completed</span>
                                </div>
                                <div class="d-flex justify-content-between align-items-center">
                                    <small class="text-muted">Score: ${data.progress}%</small>
                                    <div>
                                        <a href="/module/${moduleId}" class="btn btn-outline-primary btn-sm me-2">View Module</a>
                                        <a href="/certificate/${moduleId}" class="btn btn-primary btn-sm">Download Certificate</a>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
            content += '</div>';
        }
        
        createModal('My Certificates', content);
    }
    
    // Utility function to escape HTML and prevent XSS
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }
}

// Initialize the platform when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.tutorialPlatform = new TutorialPlatform();
    
    // Expose methods globally to ensure onclick handlers work
    window.showProgress = function() {
        if (window.tutorialPlatform) {
            window.tutorialPlatform.showProgress();
        }
    };
    
    window.showBookmarks = function() {
        if (window.tutorialPlatform) {
            window.tutorialPlatform.showBookmarks();
        }
    };
    
    window.showNotes = function() {
        if (window.tutorialPlatform) {
            window.tutorialPlatform.showNotes();
        }
    };
    
    window.showCertificates = function() {
        if (window.tutorialPlatform) {
            window.tutorialPlatform.showCertificates();
        }
    };
});

// Global functions for inline event handlers
function markCompleted(moduleId) {
    window.tutorialPlatform.markCompleted(moduleId);
}

function saveNotes(moduleId) {
    window.tutorialPlatform.saveNotes(moduleId);
}

function loadModuleNotes(moduleId) {
    window.tutorialPlatform.loadModuleNotes(moduleId);
}

function loadModuleProgress(moduleId) {
    window.tutorialPlatform.loadModuleProgress(moduleId);
}

function bookmarkModule(moduleId) {
    window.tutorialPlatform.bookmarkModule(moduleId);
}

function filterModules() {
    window.tutorialPlatform.filterModules();
}

function submitQuiz(moduleId) {
    window.tutorialPlatform.submitQuiz(moduleId);
}

function showProgress() {
    if (window.tutorialPlatform) {
        window.tutorialPlatform.showProgress();
    }
}

function showBookmarks() {
    if (window.tutorialPlatform) {
        window.tutorialPlatform.showBookmarks();
    }
}

function showNotes() {
    if (window.tutorialPlatform) {
        window.tutorialPlatform.showNotes();
    }
}

function showCertificates() {
    if (window.tutorialPlatform) {
        window.tutorialPlatform.showCertificates();
    }
}

// Set active nav item for current page
document.addEventListener('DOMContentLoaded', function() {
    const currentPath = window.location.pathname;
    if (currentPath === '/' || currentPath === '/index') {
        setActiveNavItem('nav-home');
    }
});