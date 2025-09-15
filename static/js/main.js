// Main JavaScript for tutorial platform
// Progress tracking using localStorage

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
        // Initialize progress data if not exists
        if (!localStorage.getItem('moduleProgress')) {
            localStorage.setItem('moduleProgress', JSON.stringify({}));
        }
        if (!localStorage.getItem('moduleNotes')) {
            localStorage.setItem('moduleNotes', JSON.stringify({}));
        }
        if (!localStorage.getItem('bookmarkedModules')) {
            localStorage.setItem('bookmarkedModules', JSON.stringify([]));
        }
    }

    markCompleted(moduleId) {
        const progress = JSON.parse(localStorage.getItem('moduleProgress') || '{}');
        progress[moduleId] = {
            completed: true,
            completedAt: new Date().toISOString(),
            progress: 100
        };
        localStorage.setItem('moduleProgress', JSON.stringify(progress));
        this.updateProgressDisplay(moduleId);
        this.showNotification('Module marked as completed!', 'success');
    }

    updateProgress(moduleId, percentage) {
        const progress = JSON.parse(localStorage.getItem('moduleProgress') || '{}');
        if (!progress[moduleId]) {
            progress[moduleId] = {};
        }
        progress[moduleId].progress = percentage;
        progress[moduleId].lastUpdate = new Date().toISOString();
        localStorage.setItem('moduleProgress', JSON.stringify(progress));
        this.updateProgressDisplay(moduleId);
    }

    updateProgressDisplay(moduleId) {
        const progress = JSON.parse(localStorage.getItem('moduleProgress') || '{}');
        const moduleProgress = progress[moduleId];
        const progressBar = document.getElementById('moduleProgress');
        
        if (progressBar && moduleProgress) {
            progressBar.style.width = `${moduleProgress.progress}%`;
            progressBar.setAttribute('aria-valuenow', moduleProgress.progress);
        }
    }

    // Note-taking functions
    saveNotes(moduleId) {
        const notesTextarea = document.getElementById('moduleNotes');
        if (!notesTextarea) return;

        const notes = JSON.parse(localStorage.getItem('moduleNotes') || '{}');
        notes[moduleId] = {
            content: notesTextarea.value,
            lastUpdate: new Date().toISOString()
        };
        localStorage.setItem('moduleNotes', JSON.stringify(notes));
        this.showNotification('Notes saved!', 'info');
    }

    loadModuleNotes(moduleId) {
        const notes = JSON.parse(localStorage.getItem('moduleNotes') || '{}');
        const notesTextarea = document.getElementById('moduleNotes');
        
        if (notesTextarea && notes[moduleId]) {
            notesTextarea.value = notes[moduleId].content;
        }
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
        const progress = JSON.parse(localStorage.getItem('moduleProgress') || '{}');
        let progressHtml = '<div class="modal fade" id="progressModal"><div class="modal-dialog"><div class="modal-content">';
        progressHtml += '<div class="modal-header"><h5>Your Progress</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>';
        progressHtml += '<div class="modal-body">';
        
        if (Object.keys(progress).length === 0) {
            progressHtml += '<p>No progress recorded yet.</p>';
        } else {
            progressHtml += '<ul class="list-group">';
            for (const [moduleId, data] of Object.entries(progress)) {
                progressHtml += `<li class="list-group-item d-flex justify-content-between align-items-center">
                    Module ${moduleId}
                    <div>
                        <div class="progress" style="width: 100px;">
                            <div class="progress-bar" style="width: ${data.progress}%"></div>
                        </div>
                        <small>${data.progress}%</small>
                    </div>
                </li>`;
            }
            progressHtml += '</ul>';
        }
        
        progressHtml += '</div></div></div></div>';
        
        document.body.insertAdjacentHTML('beforeend', progressHtml);
        new bootstrap.Modal(document.getElementById('progressModal')).show();
    }

    showBookmarks() {
        const bookmarks = JSON.parse(localStorage.getItem('bookmarkedModules') || '[]');
        let bookmarksHtml = '<div class="modal fade" id="bookmarksModal"><div class="modal-dialog"><div class="modal-content">';
        bookmarksHtml += '<div class="modal-header"><h5>Your Bookmarks</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>';
        bookmarksHtml += '<div class="modal-body">';
        
        if (bookmarks.length === 0) {
            bookmarksHtml += '<p>No bookmarks saved yet.</p>';
        } else {
            bookmarksHtml += '<ul class="list-group">';
            bookmarks.forEach(moduleId => {
                bookmarksHtml += `<li class="list-group-item">
                    <a href="/module/${moduleId}">Module ${moduleId}</a>
                </li>`;
            });
            bookmarksHtml += '</ul>';
        }
        
        bookmarksHtml += '</div></div></div></div>';
        
        document.body.insertAdjacentHTML('beforeend', bookmarksHtml);
        new bootstrap.Modal(document.getElementById('bookmarksModal')).show();
    }

    showNotes() {
        const notes = JSON.parse(localStorage.getItem('moduleNotes') || '{}');
        let notesHtml = '<div class="modal fade" id="notesModal"><div class="modal-dialog modal-lg"><div class="modal-content">';
        notesHtml += '<div class="modal-header"><h5>Your Notes</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>';
        notesHtml += '<div class="modal-body">';
        
        if (Object.keys(notes).length === 0) {
            notesHtml += '<p>No notes saved yet.</p>';
        } else {
            for (const [moduleId, data] of Object.entries(notes)) {
                notesHtml += `<div class="card mb-3">
                    <div class="card-header">Module ${moduleId}</div>
                    <div class="card-body">
                        <pre class="small">${data.content}</pre>
                    </div>
                </div>`;
            }
        }
        
        notesHtml += '</div></div></div></div>';
        
        document.body.insertAdjacentHTML('beforeend', notesHtml);
        new bootstrap.Modal(document.getElementById('notesModal')).show();
    }
}

// Initialize the platform when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.tutorialPlatform = new TutorialPlatform();
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
    window.tutorialPlatform.showProgress();
}

function showBookmarks() {
    window.tutorialPlatform.showBookmarks();
}

function showNotes() {
    window.tutorialPlatform.showNotes();
}