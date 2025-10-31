/**
 * Perfect AI Microphone Permissions Handler
 * Handles browser microphone permissions and provides user-friendly error messages
 */

class MicrophonePermissionHandler {
    constructor() {
        this.permissionStatus = 'unknown';
        this.isSecureContext = window.isSecureContext;
        this.init();
    }

    async init() {
        await this.checkPermissions();
        this.setupPermissionChangeListener();
        this.displayPermissionStatus();
    }

    async checkPermissions() {
        try {
            // Check if we're in a secure context (HTTPS)
            if (!this.isSecureContext) {
                this.permissionStatus = 'insecure';
                return;
            }

            // Check if mediaDevices is available
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.permissionStatus = 'unsupported';
                return;
            }

            // Check current permission status
            if (navigator.permissions) {
                const permission = await navigator.permissions.query({ name: 'microphone' });
                this.permissionStatus = permission.state;
            } else {
                // Fallback: try to access microphone to check permission
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    stream.getTracks().forEach(track => track.stop());
                    this.permissionStatus = 'granted';
                } catch (error) {
                    if (error.name === 'NotAllowedError') {
                        this.permissionStatus = 'denied';
                    } else if (error.name === 'NotFoundError') {
                        this.permissionStatus = 'no-device';
                    } else {
                        this.permissionStatus = 'error';
                    }
                }
            }
        } catch (error) {
            console.error('Error checking microphone permissions:', error);
            this.permissionStatus = 'error';
        }
    }

    setupPermissionChangeListener() {
        if (navigator.permissions) {
            navigator.permissions.query({ name: 'microphone' }).then(permission => {
                permission.addEventListener('change', () => {
                    this.permissionStatus = permission.state;
                    this.displayPermissionStatus();
                });
            });
        }
    }

    displayPermissionStatus() {
        const statusElement = document.getElementById('microphone-status');
        if (!statusElement) return;

        let statusHTML = '';
        let statusClass = '';

        switch (this.permissionStatus) {
            case 'granted':
                statusHTML = `
                    <div class="permission-status granted">
                        <span class="status-icon">🎤</span>
                        <span class="status-text">Microphone access granted</span>
                    </div>
                `;
                statusClass = 'granted';
                break;

            case 'denied':
                statusHTML = `
                    <div class="permission-status denied">
                        <span class="status-icon">🚫</span>
                        <span class="status-text">Microphone access denied</span>
                        <button onclick="micHandler.requestPermission()" class="permission-button">
                            Enable Microphone
                        </button>
                        <div class="permission-help">
                            <p>To enable microphone:</p>
                            <ul>
                                <li>Click the lock icon in your address bar</li>
                                <li>Set Microphone to "Allow"</li>
                                <li>Refresh the page</li>
                            </ul>
                        </div>
                    </div>
                `;
                statusClass = 'denied';
                break;

            case 'prompt':
                statusHTML = `
                    <div class="permission-status prompt">
                        <span class="status-icon">❓</span>
                        <span class="status-text">Microphone permission needed</span>
                        <button onclick="micHandler.requestPermission()" class="permission-button">
                            Allow Microphone Access
                        </button>
                    </div>
                `;
                statusClass = 'prompt';
                break;

            case 'insecure':
                statusHTML = `
                    <div class="permission-status insecure">
                        <span class="status-icon">🔒</span>
                        <span class="status-text">HTTPS required for microphone access</span>
                        <div class="permission-help">
                            <p>Microphone access requires a secure connection.</p>
                            <p>Please access the site via <strong>https://localhost:5000</strong></p>
                            <button onclick="window.location.href='https://localhost:5000'" class="permission-button">
                                Switch to HTTPS
                            </button>
                        </div>
                    </div>
                `;
                statusClass = 'insecure';
                break;

            case 'unsupported':
                statusHTML = `
                    <div class="permission-status unsupported">
                        <span class="status-icon">❌</span>
                        <span class="status-text">Microphone not supported</span>
                        <div class="permission-help">
                            <p>Your browser doesn't support microphone access.</p>
                            <p>Please use a modern browser like Chrome, Firefox, or Safari.</p>
                        </div>
                    </div>
                `;
                statusClass = 'unsupported';
                break;

            case 'no-device':
                statusHTML = `
                    <div class="permission-status no-device">
                        <span class="status-icon">🎤</span>
                        <span class="status-text">No microphone found</span>
                        <div class="permission-help">
                            <p>Please connect a microphone and refresh the page.</p>
                        </div>
                    </div>
                `;
                statusClass = 'no-device';
                break;

            default:
                statusHTML = `
                    <div class="permission-status unknown">
                        <span class="status-icon">⏳</span>
                        <span class="status-text">Checking microphone permissions...</span>
                    </div>
                `;
                statusClass = 'unknown';
        }

        statusElement.innerHTML = statusHTML;
        statusElement.className = `microphone-status ${statusClass}`;
    }

    async requestPermission() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(track => track.stop());
            this.permissionStatus = 'granted';
            this.displayPermissionStatus();
            
            // Show success message
            this.showNotification('✅ Microphone access granted! You can now start recording.', 'success');
            
            // Enable recording button if it exists
            const recordButton = document.getElementById('start-recording-btn');
            if (recordButton) {
                recordButton.disabled = false;
            }
            
        } catch (error) {
            console.error('Error requesting microphone permission:', error);
            
            if (error.name === 'NotAllowedError') {
                this.permissionStatus = 'denied';
                this.showNotification('❌ Microphone access denied. Please check your browser settings.', 'error');
            } else if (error.name === 'NotFoundError') {
                this.permissionStatus = 'no-device';
                this.showNotification('❌ No microphone found. Please connect a microphone.', 'error');
            } else {
                this.showNotification('❌ Error accessing microphone. Please try again.', 'error');
            }
            
            this.displayPermissionStatus();
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <span class="notification-message">${message}</span>
            <button class="notification-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    // Check if recording can start
    canStartRecording() {
        return this.permissionStatus === 'granted' && this.isSecureContext;
    }

    // Get user-friendly error message
    getErrorMessage() {
        switch (this.permissionStatus) {
            case 'denied':
                return 'Microphone access is denied. Please enable it in your browser settings.';
            case 'insecure':
                return 'HTTPS is required for microphone access. Please use https://localhost:5000';
            case 'unsupported':
                return 'Your browser does not support microphone access.';
            case 'no-device':
                return 'No microphone device found. Please connect a microphone.';
            default:
                return 'Unable to access microphone. Please check your settings.';
        }
    }
}

// Initialize microphone permission handler
let micHandler;
document.addEventListener('DOMContentLoaded', () => {
    micHandler = new MicrophonePermissionHandler();
});

// CSS styles for permission status
const micPermissionStyle = document.createElement('style');
micPermissionStyle.textContent = `
    .microphone-status {
        margin: 15px 0;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
    }

    .permission-status {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }

    .status-icon {
        font-size: 20px;
    }

    .status-text {
        font-weight: 500;
        flex: 1;
    }

    .permission-button {
        background: #dc2626;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
    }

    .permission-button:hover {
        background: #b91c1c;
    }

    .permission-help {
        width: 100%;
        margin-top: 10px;
        padding: 10px;
        background: #f9fafb;
        border-radius: 6px;
        font-size: 14px;
    }

    .permission-help ul {
        margin: 5px 0 0 20px;
    }

    .microphone-status.granted {
        background: #f0fdf4;
        border-color: #10b981;
        color: #065f46;
    }

    .microphone-status.denied {
        background: #fef2f2;
        border-color: #dc2626;
        color: #991b1b;
    }

    .microphone-status.insecure {
        background: #fffbeb;
        border-color: #f59e0b;
        color: #92400e;
    }

    .microphone-status.unsupported {
        background: #f3f4f6;
        border-color: #6b7280;
        color: #374151;
    }

    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        max-width: 400px;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .notification.success {
        background: #f0fdf4;
        border: 1px solid #10b981;
        color: #065f46;
    }

    .notification.error {
        background: #fef2f2;
        border: 1px solid #dc2626;
        color: #991b1b;
    }

    .notification-close {
        background: none;
        border: none;
        font-size: 18px;
        cursor: pointer;
        padding: 0;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
`;
document.head.appendChild(micPermissionStyle);