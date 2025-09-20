// Main JavaScript for tutorial platform
// Progress tracking using database (localStorage removed)

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
        this.setupKeyboardNavigation();
        this.setupSearchFiltering();
    }

    // Progress tracking functions removed - functionality no longer needed
    
    // Note-taking functions removed - functionality no longer needed
    
    // Bookmark functions removed - functionality no longer needed

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

    

    // User data display functions removed - functionality no longer needed

    showCertificates() {
        setActiveNavItem('nav-certificates');
        // Certificates now managed through database - simplified display
        let content = `
            <div class="alert alert-info">
                <h4>🏆 Certificates</h4>
                <p>Certificates are now managed through the database. Complete modules to earn certificates.</p>
            </div>
        `;
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
    window.showCertificates = function() {
        if (window.tutorialPlatform) {
            window.tutorialPlatform.showCertificates();
        }
    };
});

// Global functions for inline event handlers
function filterModules() {
    window.tutorialPlatform.filterModules();
}

function submitQuiz(moduleId) {
    window.tutorialPlatform.submitQuiz(moduleId);
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

// Global variables
let currentUser = 'anonymous';

// Cache clearing functionality
function clearAllCaches() {
    // Clear service worker caches
    if ('serviceWorker' in navigator && 'caches' in window) {
        caches.keys().then(function(cacheNames) {
            return Promise.all(
                cacheNames.map(function(cacheName) {
                    console.log('Clearing cache:', cacheName);
                    return caches.delete(cacheName);
                })
            );
        }).then(function() {
            console.log('All caches cleared');
            // Force reload page to get fresh content
            window.location.reload(true);
        });
    }
    
    // Clear localStorage
    if (typeof(Storage) !== "undefined") {
        localStorage.clear();
        console.log('LocalStorage cleared');
    }
    
    // Clear sessionStorage
    if (typeof(Storage) !== "undefined") {
        sessionStorage.clear();
        console.log('SessionStorage cleared');
    }
}

// Certificate download function
function downloadCertificate(moduleId) {
    const fullName = document.getElementById('fullName').value.trim();
    const messageEl = document.getElementById('certificateMessage');

    // Clear previous messages
    hideMessage(messageEl);

    if (!fullName) {
        showMessage(messageEl, 'Please enter your full name', 'danger');
        return;
    }

    if (fullName.length > 100) {
        showMessage(messageEl, 'Name is too long (maximum 100 characters)', 'danger');
        return;
    }

    // Check for invalid characters
    if (/[<>"'&]/.test(fullName)) {
        showMessage(messageEl, 'Name contains invalid characters', 'danger');
        return;
    }

    // Show success message
    showMessage(messageEl, 'Generating certificate...', 'success');

    // Generate certificate URL with name parameter
    const url = `/certificate/${moduleId}?name=${encodeURIComponent(fullName)}`;

    // Open certificate in new window/tab
    window.open(url, '_blank');

    // Clear the form after successful download
    setTimeout(() => {
        document.getElementById('fullName').value = '';
        showMessage(messageEl, 'Certificate downloaded successfully!', 'success');
        setTimeout(() => hideMessage(messageEl), 3000);
    }, 1000);
}

// Helper functions for inline messaging
function showMessage(element, message, type = 'info') {
    element.className = `alert alert-${type}`;
    element.textContent = message;
    element.classList.remove('d-none');
}

function hideMessage(element) {
    element.classList.add('d-none');
}