// Additional JavaScript utilities for NovaMotion Core

class NovaMotionCore {
    constructor() {
        this.socket = null;
        this.currentSimulation = null;
        this.calibrationData = null;
    }

    // Initialize WebSocket connection
    initSocket(url = null) {
        if (this.socket) {
            this.socket.disconnect();
        }

        const socketUrl = url || `http://${window.location.hostname}:${window.location.port || 5000}`;
        this.socket = io(socketUrl);

        this.socket.on('connect', () => {
            console.log('Connected to NovaMotion Core');
            this.showToast('Connected to server', 'success');
            this.updateConnectionStatus(true);
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from NovaMotion Core');
            this.showToast('Disconnected from server', 'error');
            this.updateConnectionStatus(false);
        });

        this.socket.on('simulation_update', (data) => {
            this.handleSimulationUpdate(data);
        });

        this.socket.on('simulation_complete', (data) => {
            this.handleSimulationComplete(data);
        });

        this.socket.on('calibration_update', (data) => {
            this.handleCalibrationUpdate(data);
        });

        this.socket.on('hardware_status', (data) => {
            this.updateHardwareStatus(data);
        });

        return this.socket;
    }

    // Update connection status display
    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connectionStatus');
        const dotEl = document.querySelector('.status-dot');
        
        if (statusEl && dotEl) {
            statusEl.textContent = connected ? 'Connected' : 'Disconnected';
            dotEl.style.backgroundColor = connected ? '#10b981' : '#ef4444';
            dotEl.style.animation = connected ? 'pulse 2s infinite' : 'none';
        }
    }

    // Show toast notification
    showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        toast.innerHTML = `
            <div class="toast-icon">${this.getToastIcon(type)}</div>
            <div class="toast-message">${message}</div>
            <button class="toast-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        // Add styles if not already present
        if (!document.querySelector('#toast-styles')) {
            const style = document.createElement('style');
            style.id = 'toast-styles';
            style.textContent = `
                .toast-notification {
                    position: fixed;
                    bottom: 20px;
                    left: 20px;
                    background: rgba(30, 41, 59, 0.95);
                    border-left: 4px solid #3b82f6;
                    border-radius: 8px;
                    padding: 15px 20px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    max-width: 400px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                    z-index: 10000;
                    backdrop-filter: blur(10px);
                    animation: slideInLeft 0.3s ease;
                }
                
                .toast-notification.success {
                    border-left-color: #10b981;
                }
                
                .toast-notification.error {
                    border-left-color: #ef4444;
                }
                
                .toast-notification.warning {
                    border-left-color: #f59e0b;
                }
                
                .toast-icon {
                    font-size: 20px;
                }
                
                .toast-message {
                    flex: 1;
                    color: #e2e8f0;
                    font-size: 14px;
                }
                
                .toast-close {
                    background: none;
                    border: none;
                    color: #94a3b8;
                    font-size: 20px;
                    cursor: pointer;
                    padding: 0;
                    width: 24px;
                    height: 24px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 50%;
                }
                
                .toast-close:hover {
                    background: rgba(248, 113, 113, 0.1);
                    color: #f87171;
                }
                
                @keyframes slideInLeft {
                    from {
                        transform: translateX(-100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(toast);
        
        // Auto-remove after duration
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.animation = 'slideInLeft 0.3s ease reverse';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
        
        return toast;
    }

    getToastIcon(type) {
        const icons = {
            'success': '✓',
            'error': '✗',
            'warning': '⚠',
            'info': 'ℹ'
        };
        return icons[type] || icons.info;
    }

    // Handle simulation updates
    handleSimulationUpdate(data) {
        if (this.currentSimulation) {
            this.currentSimulation.update(data);
        }
    }

    handleSimulationComplete(data) {
        this.showToast('Simulation completed', 'success');
        
        // Update quality metrics
        if (data.quality) {
            this.updateQualityDisplay(data.quality);
        }
    }

    // Handle calibration updates
    handleCalibrationUpdate(data) {
        const { stage, progress, message } = data;
        
        // Update calibration progress UI
        const progressBar = document.getElementById('calibration-progress');
        const progressText = document.getElementById('calibration-progress-text');
        
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
        
        if (progressText) {
            progressText.textContent = `${stage}: ${message} (${progress.toFixed(1)}%)`;
        }
        
        if (stage === 'complete') {
            this.calibrationData = data.results;
            this.showToast('Calibration completed successfully', 'success');
        }
    }

    // Update hardware status display
    updateHardwareStatus(data) {
        // Update TMC2209 status display
        const tmcStatus = document.getElementById('tmc-status');
        if (tmcStatus && data.drivers) {
            let html = '';
            for (const [name, status] of Object.entries(data.drivers)) {
                const connected = status.connected ? 'Connected' : 'Disconnected';
                const color = status.connected ? '#10b981' : '#ef4444';
                html += `<p style="color: ${color}">${name}: ${connected}</p>`;
            }
            tmcStatus.innerHTML = html;
        }
    }

    // Update quality metrics display
    updateQualityDisplay(metrics) {
        const elements = {
            'overallScore': 'overallScore',
            'trackingScore': 'trackingScore',
            'vibrationScore': 'vibrationScore',
            'rmsError': 'rmsError',
            'maxError': 'maxError'
        };

        for (const [key, id] of Object.entries(elements)) {
            const element = document.getElementById(id);
            if (element && metrics[key]) {
                const value = metrics[key];
                const oldValue = parseFloat(element.textContent) || 0;
                
                // Animate value change
                this.animateValue(element, oldValue, value, 500);
                
                // Add pulse animation
                element.classList.add('updated');
                setTimeout(() => element.classList.remove('updated'), 500);
            }
        }

        // Update recommendations
        this.updateRecommendations(metrics);
    }

    // Animate numeric value changes
    animateValue(element, start, end, duration) {
        if (start === end) return;

        const startTime = performance.now();
        const decimals = end.toString().split('.')[1]?.length || 0;
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function
            const ease = progress < 0.5 
                ? 2 * progress * progress 
                : 1 - Math.pow(-2 * progress + 2, 2) / 2;
            
            const current = start + (end - start) * ease;
            element.textContent = current.toFixed(decimals);
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    // Update recommendations based on metrics
    updateRecommendations(metrics) {
        const recs = [];
        
        if (metrics.tracking_score < 80) {
            recs.push('Reduce acceleration for better tracking accuracy');
        }
        
        if (metrics.vibration_score < 70) {
            recs.push('Enable input shaping or reduce speed for vibration control');
        }
        
        if (metrics.max_error_mm > 0.05) {
            recs.push('Check mechanical alignment and consider backlash compensation');
        }
        
        if (metrics.rms_error_mm < 0.01 && metrics.vibration_score > 85) {
            recs.push('System is well-tuned. Consider increasing print speed');
        }
        
        if (recs.length === 0) {
            recs.push('No optimization recommendations needed');
        }
        
        const recommendationsEl = document.getElementById('recommendations');
        if (recommendationsEl) {
            recommendationsEl.innerHTML = recs.map(r => `<p>• ${r}</p>`).join('');
        }
    }

    // Start calibration procedure
    async startCalibration() {
        try {
            this.showToast('Starting calibration...', 'info');
            
            const response = await fetch('/api/start_calibration', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                this.showToast('Calibration started', 'success');
                this.showCalibrationModal();
            } else {
                throw new Error('Failed to start calibration');
            }
        } catch (error) {
            this.showToast(`Calibration error: ${error.message}`, 'error');
        }
    }

    // Show calibration modal
    showCalibrationModal() {
        let modal = document.getElementById('calibration-modal');
        
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'calibration-modal';
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h3 style="margin: 0; color: #e2e8f0;">Calibration Progress</h3>
                        <button class="modal-close" onclick="novaMotion.closeModal()">×</button>
                    </div>
                    <div style="text-align: center; padding: 30px 0;">
                        <div class="spinner"></div>
                        <div style="margin-top: 20px; color: #94a3b8;" id="calibration-progress-text">
                            Initializing calibration...
                        </div>
                        <div class="progress-bar" style="margin-top: 20px;">
                            <div class="progress-fill" id="calibration-progress" style="width: 0%"></div>
                        </div>
                        <div id="calibration-details" style="margin-top: 20px; text-align: left; font-size: 13px; color: #cbd5e1;"></div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        
        modal.classList.add('active');
    }

    // Close modal
    closeModal() {
        const modal = document.getElementById('calibration-modal');
        if (modal) {
            modal.classList.remove('active');
            setTimeout(() => modal.remove(), 300);
        }
    }

    // Export calibration data
    exportCalibration() {
        if (!this.calibrationData) {
            this.showToast('No calibration data available', 'warning');
            return;
        }
        
        const dataStr = JSON.stringify(this.calibrationData, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `nova_calibration_${Date.now()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.showToast('Calibration data exported', 'success');
    }

    // Import calibration data
    importCalibration(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);
                this.calibrationData = data;
                
                // Send to server
                fetch('/api/import_calibration', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                }).then(response => {
                    if (response.ok) {
                        this.showToast('Calibration data imported', 'success');
                    } else {
                        throw new Error('Import failed');
                    }
                });
            } catch (error) {
                this.showToast('Invalid calibration file', 'error');
            }
        };
        reader.readAsText(file);
    }

    // Generate test G-code
    generateTestGCode() {
        const gcode = `
; NovaMotion Core Test Pattern
G28 ; Home all axes
G90 ; Absolute positioning
G21 ; Millimeter units
M104 S200 ; Set nozzle temperature
M140 S60 ; Set bed temperature
G1 Z5 F500 ; Lift nozzle
G1 X50 Y50 F3000 ; Move to start
G1 Z0.2 F300 ; Lower nozzle

; Test square
G1 X100 Y50 F6000
G1 X100 Y100
G1 X50 Y100
G1 X50 Y50

; Test diagonal
G1 X150 Y150 F8000

; Test circle approximation
G2 X50 Y150 I50 J0 F5000
G1 Z5 F500 ; Lift nozzle
M104 S0 ; Cool nozzle
M140 S0 ; Cool bed
G28 X Y ; Home XY
M84 ; Disable motors
`;
        
        const blob = new Blob([gcode], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'nova_test.gcode';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.showToast('Test G-code generated', 'success');
    }
}

// Global instance
const novaMotion = new NovaMotionCore();

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize socket
    novaMotion.initSocket();
    
    // Add event listeners
    document.getElementById('calibrate-btn')?.addEventListener('click', () => {
        novaMotion.startCalibration();
    });
    
    document.getElementById('export-btn')?.addEventListener('click', () => {
        novaMotion.exportCalibration();
    });
    
    document.getElementById('import-btn')?.addEventListener('click', () => {
        document.getElementById('import-file')?.click();
    });
    
    document.getElementById('test-gcode-btn')?.addEventListener('click', () => {
        novaMotion.generateTestGCode();
    });
    
    // Add import file input if not exists
    if (!document.getElementById('import-file')) {
        const input = document.createElement('input');
        input.id = 'import-file';
        input.type = 'file';
        input.accept = '.json';
        input.style.display = 'none';
        input.addEventListener('change', (e) => novaMotion.importCalibration(e));
        document.body.appendChild(input);
    }
    
    console.log('NovaMotion Core initialized');
});