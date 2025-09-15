// Admin panel JavaScript functionality

class AdminPanel {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initializeSortable();
    }

    setupEventListeners() {
        // URL import form
        const urlImportForm = document.getElementById('urlImportForm');
        if (urlImportForm) {
            urlImportForm.addEventListener('submit', this.handleUrlImport.bind(this));
        }

        // Image upload form
        const imageUploadForm = document.getElementById('imageUploadForm');
        if (imageUploadForm) {
            imageUploadForm.addEventListener('submit', this.handleImageUpload.bind(this));
        }

        // Configuration form
        const configForm = document.getElementById('configForm');
        if (configForm) {
            configForm.addEventListener('submit', this.handleConfigUpdate.bind(this));
        }

        // Header customization form
        const headerCustomizationForm = document.getElementById('headerCustomizationForm');
        if (headerCustomizationForm) {
            headerCustomizationForm.addEventListener('submit', this.handleHeaderCustomizationUpdate.bind(this));
        }
    }

    initializeSortable() {
        const modulesList = document.getElementById('modulesList');
        if (modulesList && typeof Sortable !== 'undefined') {
            new Sortable(modulesList, {
                animation: 150,
                onEnd: this.handleModuleReorder.bind(this)
            });
        }
    }

    async handleUrlImport(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const url = formData.get('import_url');

        if (!url) {
            alert('Please enter a URL');
            return;
        }

        try {
            const response = await fetch('/api/scrape-url', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.getCSRFToken()
                },
                body: JSON.stringify({ url: url })
            });

            const data = await response.json();

            if (response.ok) {
                // Create modal to show imported content
                this.showImportPreview(data);
            } else {
                alert('Error importing content: ' + data.error);
            }
        } catch (error) {
            alert('Error importing content: ' + error.message);
        }
    }

    showImportPreview(data) {
        const modalHtml = `
            <div class="modal fade" id="importPreviewModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Import Preview</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form id="importContentForm">
                                <input type="hidden" name="csrf_token" value="${this.getCSRFToken()}">
                                <div class="mb-3">
                                    <label for="import_title" class="form-label">Module Title</label>
                                    <input type="text" class="form-control" id="import_title" name="title" required>
                                </div>
                                <div class="mb-3">
                                    <label for="import_description" class="form-label">Description</label>
                                    <textarea class="form-control" id="import_description" name="description" rows="2"></textarea>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Imported Content Preview</label>
                                    <div class="border p-3" style="max-height: 300px; overflow-y: auto;">
                                        ${data.content.substring(0, 1000)}${data.content.length > 1000 ? '...' : ''}
                                    </div>
                                </div>
                                ${data.quiz_questions.length > 0 ? `
                                <div class="mb-3">
                                    <label class="form-label">Generated Quiz Questions</label>
                                    <div class="border p-3" style="max-height: 200px; overflow-y: auto;">
                                        ${data.quiz_questions.map((q, i) => `
                                            <div class="mb-2">
                                                <strong>Q${i+1}:</strong> ${q.question}<br>
                                                <small>Options: ${q.options.join(', ')}</small>
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                                ` : ''}
                                <input type="hidden" name="content" value="${this.escapeHtml(data.content)}">
                                <input type="hidden" name="quiz_questions" value="${this.escapeHtml(JSON.stringify(data.quiz_questions))}">
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" onclick="adminPanel.createModuleFromImport()">Create Module</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('importPreviewModal'));
        modal.show();

        // Clean up modal when hidden
        modal._element.addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }

    async handleImageUpload(e) {
        e.preventDefault();
        const formData = new FormData(e.target);

        try {
            const response = await fetch('/admin/upload-image', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                // Show success message with image URL
                alert(`Image uploaded successfully! URL: ${data.url}`);
                
                // Copy URL to clipboard
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(data.url);
                    alert('Image URL copied to clipboard');
                }
                
                // Reset form
                e.target.reset();
            } else {
                alert('Error uploading image: ' + data.error);
            }
        } catch (error) {
            alert('Error uploading image: ' + error.message);
        }
    }

    async createModuleFromImport() {
        const form = document.getElementById('importContentForm');
        const formData = new FormData(form);

        try {
            const response = await fetch('/admin/module/new', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                bootstrap.Modal.getInstance(document.getElementById('importPreviewModal')).hide();
                window.location.reload();
            } else {
                alert('Error creating module');
            }
        } catch (error) {
            alert('Error creating module: ' + error.message);
        }
    }

    async handleConfigUpdate(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        // Convert form data to JSON
        const config = {};
        for (let [key, value] of formData.entries()) {
            if (key !== 'csrf_token' && value.trim() !== '') {
                config[key] = value;
            }
        }

        try {
            const response = await fetch('/admin/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.getCSRFToken()
                },
                body: JSON.stringify(config)
            });

            if (response.ok) {
                alert('Configuration updated successfully');
            } else {
                alert('Error updating configuration');
            }
        } catch (error) {
            alert('Error updating configuration: ' + error.message);
        }
    }

    async handleHeaderCustomizationUpdate(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        
        // Convert form data to JSON with proper handling for checkboxes
        const headerCustomization = {};
        for (let [key, value] of formData.entries()) {
            if (key !== 'csrf_token') {
                if (key === 'show_emoji') {
                    headerCustomization[key] = true; // Checkbox checked
                } else if (value.trim() !== '') {
                    headerCustomization[key] = value;
                }
            }
        }
        
        // If show_emoji checkbox is not in formData, it means it's unchecked
        if (!formData.has('show_emoji')) {
            headerCustomization['show_emoji'] = false;
        }

        const config = {
            header_customization: headerCustomization
        };

        try {
            const response = await fetch('/admin/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.getCSRFToken()
                },
                body: JSON.stringify(config)
            });

            if (response.ok) {
                alert('Header customization updated successfully! Please refresh the page to see changes.');
            } else {
                alert('Error updating header customization');
            }
        } catch (error) {
            alert('Error updating header customization: ' + error.message);
        }
    }

    async handleModuleReorder(evt) {
        const moduleIds = Array.from(evt.to.children).map(row => row.dataset.moduleId);
        
        try {
            const response = await fetch('/admin/modules/reorder', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.getCSRFToken()
                },
                body: JSON.stringify({ module_order: moduleIds })
            });

            if (!response.ok) {
                alert('Error reordering modules');
                // Reload page to restore original order
                window.location.reload();
            }
        } catch (error) {
            alert('Error reordering modules: ' + error.message);
            window.location.reload();
        }
    }

    getCSRFToken() {
        return document.querySelector('input[name="csrf_token"]')?.value || 
               document.querySelector('meta[name="csrf-token"]')?.content || '';
    }

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

// Global functions
async function deleteModule(moduleId) {
    if (!confirm('Are you sure you want to delete this module?')) {
        return;
    }

    try {
        const response = await fetch(`/admin/module/${moduleId}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': adminPanel.getCSRFToken()
            }
        });

        if (response.ok) {
            // Remove the row from the table
            document.querySelector(`tr[data-module-id="${moduleId}"]`).remove();
        } else {
            alert('Error deleting module');
        }
    } catch (error) {
        alert('Error deleting module: ' + error.message);
    }
}

function exportData() {
    // Create a download link for exporting data
    const link = document.createElement('a');
    link.href = '/admin/export';
    link.download = `tutorial_platform_export_${new Date().toISOString().split('T')[0]}.zip`;
    link.click();
}

// Initialize admin panel when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.adminPanel = new AdminPanel();
});

// Load SortableJS for drag-and-drop functionality
if (!window.Sortable) {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js';
    script.onload = function() {
        if (window.adminPanel) {
            window.adminPanel.initializeSortable();
        }
    };
    document.head.appendChild(script);
}