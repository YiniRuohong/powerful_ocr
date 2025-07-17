// OCR处理器前端JavaScript

class OCRApp {
    constructor() {
        this.currentTaskId = null;
        this.progressInterval = null;
        this.currentFile = null;
        this.systemStatus = null;
        
        this.init();
    }
    
    async init() {
        await this.loadSystemStatus();
        this.setupEventListeners();
        this.refreshResults();
    }
    
    async loadSystemStatus() {
        try {
            const response = await fetch('/api/status');
            this.systemStatus = await response.json();
            
            this.updateSystemStatus(true);
            this.populateOCRServices();
            this.populateTerminologyFiles();
            
        } catch (error) {
            console.error('Failed to load system status:', error);
            this.updateSystemStatus(false);
            this.showError('无法连接到服务器');
        }
    }
    
    updateSystemStatus(online) {
        const indicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
        
        if (online) {
            indicator.className = 'status-indicator online';
            statusText.textContent = '服务正常';
        } else {
            indicator.className = 'status-indicator offline';
            statusText.textContent = '服务离线';
        }
    }
    
    populateOCRServices() {
        const select = document.getElementById('ocr-service');
        select.innerHTML = '';
        
        for (const [key, description] of Object.entries(this.systemStatus.available_ocr_services)) {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = description;
            select.appendChild(option);
        }
    }
    
    populateTerminologyFiles() {
        const select = document.getElementById('terminology');
        select.innerHTML = '<option value="">不使用专业词典</option>';
        
        for (const filename of this.systemStatus.terminology_files) {
            const option = document.createElement('option');
            option.value = filename;
            option.textContent = filename;
            select.appendChild(option);
        }
    }
    
    setupEventListeners() {
        // 文件上传
        const fileInput = document.getElementById('file-input');
        const uploadArea = document.getElementById('upload-area');
        
        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        
        // 拖拽上传
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            this.handleFileSelect(e);
        });
        
        // 页面范围输入事件
        document.getElementById('start-page').addEventListener('change', this.updatePageInfo.bind(this));
        document.getElementById('end-page').addEventListener('change', this.updatePageInfo.bind(this));
        
        // 分割配置事件
        document.getElementById('enable-splitting').addEventListener('change', this.updateSplitPreview.bind(this));
        document.getElementById('split-strategy').addEventListener('change', this.updateSplitPreview.bind(this));
    }
    
    async handleFileSelect(event) {
        const files = event.target.files || event.dataTransfer.files;
        if (!files || files.length === 0) return;
        
        const file = files[0]; // 只处理第一个文件
        
        if (!file.name.endsWith('.pdf')) {
            this.showError('请选择PDF文件');
            return;
        }
        
        // 检查文件大小 (500MB)
        const maxSize = 500 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showError('文件过大，最大支持500MB');
            return;
        }
        
        const uploadProgress = document.getElementById('upload-progress');
        const progressFill = document.getElementById('upload-progress-fill');
        const progressText = document.getElementById('upload-progress-text');
        
        uploadProgress.style.display = 'block';
        
        try {
            progressText.textContent = `上传中... ${file.name}`;
            progressFill.style.width = '0%';
            
            const result = await this.uploadFile(file);
            
            progressFill.style.width = '100%';
            this.addLog(`✅ ${file.name} 上传成功`, 'success');
            
            // 更新当前文件信息
            await this.setCurrentFile(result.filename, file.size);
            
        } catch (error) {
            this.addLog(`❌ ${file.name} 上传失败: ${error.message}`, 'error');
            this.showError(`上传失败: ${error.message}`);
        } finally {
            uploadProgress.style.display = 'none';
            // 清空文件输入
            if (event.target.files) {
                event.target.value = '';
            }
        }
    }
    
    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '上传失败');
        }
        
        return await response.json();
    }
    
    async setCurrentFile(filename, fileSize) {
        try {
            // 获取文件详细信息
            const response = await fetch(`/api/file/${filename}`);
            const fileInfo = await response.json();
            
            this.currentFile = {
                filename: filename,
                name: fileInfo.name,
                size: fileInfo.size || fileSize,
                pages: fileInfo.pages
            };
            
            // 更新UI
            this.showCurrentFile();
            this.updatePageInfo();
            
        } catch (error) {
            console.error('Failed to get file info:', error);
            this.currentFile = {
                filename: filename,
                name: filename,
                size: fileSize,
                pages: 1
            };
            this.showCurrentFile();
        }
    }
    
    showCurrentFile() {
        const uploadArea = document.getElementById('upload-area');
        const fileInfo = document.getElementById('uploaded-file-info');
        const fileName = document.getElementById('current-file-name');
        const fileMeta = document.getElementById('current-file-meta');
        
        if (this.currentFile) {
            uploadArea.style.display = 'none';
            fileInfo.style.display = 'block';
            
            fileName.textContent = this.currentFile.name;
            fileMeta.textContent = `${this.formatFileSize(this.currentFile.size)} • ${this.currentFile.pages} 页`;
        } else {
            uploadArea.style.display = 'block';
            fileInfo.style.display = 'none';
        }
    }
    
    clearCurrentFile() {
        this.currentFile = null;
        this.showCurrentFile();
        this.updatePageInfo();
    }
    
    updatePageInfo() {
        const pageInfo = document.getElementById('page-info');
        const startPage = document.getElementById('start-page');
        const endPage = document.getElementById('end-page');
        
        if (!this.currentFile) {
            pageInfo.textContent = '请先上传PDF文件';
            startPage.disabled = true;
            endPage.disabled = true;
            return;
        }
        
        startPage.disabled = false;
        endPage.disabled = false;
        endPage.max = this.currentFile.pages;
        
        // 只有在结束页为1时才设置默认值，避免覆盖用户修改的值
        if (parseInt(endPage.value) === 1) {
            endPage.value = Math.min(10, this.currentFile.pages); // 默认设为10页或文件总页数，取较小值
        }
        
        startPage.max = this.currentFile.pages;
        
        pageInfo.textContent = `文件 '${this.currentFile.name}' 共有 ${this.currentFile.pages} 页`;
    }
    
    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
    
    
    async startProcessing() {
        if (!this.currentFile) {
            this.showError('请先上传PDF文件');
            return;
        }
        
        const startPage = parseInt(document.getElementById('start-page').value);
        const endPage = parseInt(document.getElementById('end-page').value);
        const ocrService = document.getElementById('ocr-service').value;
        const terminology = document.getElementById('terminology').value;
        
        if (startPage > endPage) {
            this.showError('起始页不能大于结束页');
            return;
        }
        
        const request = {
            filename: this.currentFile.filename,
            start_page: startPage,
            end_page: endPage,
            ocr_service: ocrService,
            terminology: terminology
        };
        
        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(request)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '启动处理失败');
            }
            
            const result = await response.json();
            this.currentTaskId = result.task_id;
            
            this.setProcessingState(true);
            this.startProgressPolling();
            this.addLog('🚀 开始处理文件', 'info');
            
        } catch (error) {
            this.showError(error.message);
            this.addLog(`❌ 启动失败: ${error.message}`, 'error');
        }
    }
    
    async stopProcessing() {
        if (!this.currentTaskId) return;
        
        try {
            await fetch(`/api/stop/${this.currentTaskId}`, { method: 'POST' });
            this.addLog('⏹️ 停止信号已发送', 'warning');
            
        } catch (error) {
            this.addLog(`❌ 停止失败: ${error.message}`, 'error');
        }
    }
    
    setProcessingState(processing) {
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        startBtn.disabled = processing;
        stopBtn.disabled = !processing;
    }
    
    startProgressPolling() {
        this.progressInterval = setInterval(async () => {
            if (!this.currentTaskId) return;
            
            try {
                const response = await fetch(`/api/progress/${this.currentTaskId}`);
                const progress = await response.json();
                
                this.updateProgress(progress);
                
                if (['completed', 'failed', 'stopped'].includes(progress.status)) {
                    this.stopProgressPolling();
                    this.setProcessingState(false);
                    this.currentTaskId = null;
                    this.refreshResults();
                }
                
            } catch (error) {
                console.error('Failed to fetch progress:', error);
            }
        }, 1000);
    }
    
    stopProgressPolling() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }
    
    updateProgress(progress) {
        // 更新进度条
        const progressFill = document.getElementById('progress-fill');
        const progressLabel = document.getElementById('progress-label');
        const progressPercentage = document.getElementById('progress-percentage');
        
        progressFill.style.width = `${progress.progress}%`;
        progressPercentage.textContent = `${Math.round(progress.progress)}%`;
        
        if (progress.current_file) {
            progressLabel.textContent = `正在处理: ${progress.current_file}`;
        }
        
        // 更新Token统计
        document.getElementById('total-tokens').textContent = progress.total_tokens.toLocaleString();
        document.getElementById('ocr-tokens').textContent = progress.ocr_tokens.toLocaleString();
        document.getElementById('gemini-tokens').textContent = progress.gemini_tokens.toLocaleString();
        
        // 更新页面进度
        document.getElementById('page-progress').textContent = 
            `页面: ${progress.current_page}/${progress.total_pages}`;
        
        // 更新分块进度
        if (progress.total_chunks > 0) {
            document.getElementById('chunk-progress').textContent = 
                `分块: ${progress.current_chunk}/${progress.total_chunks}`;
            document.getElementById('chunk-progress').style.display = 'block';
        } else {
            document.getElementById('chunk-progress').style.display = 'none';
        }
        
        // 更新分块列表状态
        this.updateChunkStatus(progress.chunks);
        
        // 更新日志
        if (progress.log_messages && progress.log_messages.length > 0) {
            this.updateLogFromProgress(progress.log_messages);
        }
    }
    
    updateLogFromProgress(logMessages) {
        const container = document.getElementById('log-container');
        
        // 只添加新的日志消息
        const currentLogs = container.querySelectorAll('.log-message').length;
        const newLogs = logMessages.slice(currentLogs);
        
        newLogs.forEach(log => {
            this.addLogMessage(log.message, log.level, log.timestamp);
        });
    }
    
    addLog(message, level = 'info') {
        const timestamp = new Date().toISOString();
        this.addLogMessage(message, level, timestamp);
    }
    
    addLogMessage(message, level, timestamp) {
        const container = document.getElementById('log-container');
        const time = new Date(timestamp).toLocaleTimeString();
        
        const logElement = document.createElement('div');
        logElement.className = `log-message ${level}`;
        logElement.innerHTML = `
            <span class=\"log-time\">[${time}]</span>
            <span class=\"log-text\">${message}</span>
        `;
        
        container.appendChild(logElement);
        container.scrollTop = container.scrollHeight;
        
        // 限制日志数量
        const logs = container.querySelectorAll('.log-message');
        if (logs.length > 100) {
            logs[0].remove();
        }
    }
    
    updateChunkStatus(chunks) {
        const chunkStatus = document.getElementById('chunk-status');
        
        if (!chunks || chunks.length === 0) {
            chunkStatus.style.display = 'none';
            return;
        }
        
        chunkStatus.style.display = 'block';
        
        const statusHtml = chunks.map(chunk => {
            const statusIcon = {
                'pending': '⏳',
                'processing': '🔄',
                'completed': '✅',
                'failed': '❌'
            }[chunk.status] || '⏳';
            
            return `
                <div class="chunk-status-item ${chunk.status}">
                    <span class="chunk-status-icon">${statusIcon}</span>
                    <span class="chunk-status-text">
                        ${chunk.chunk_id} (页面 ${chunk.start_page}-${chunk.end_page})
                    </span>
                </div>
            `;
        }).join('');
        
        chunkStatus.innerHTML = `
            <div class="chunk-status-header">分块处理状态:</div>
            <div class="chunk-status-list">${statusHtml}</div>
        `;
    }
    
    clearLog() {
        const container = document.getElementById('log-container');
        container.innerHTML = '<div class=\"log-message info\"><span class=\"log-time\">[系统]</span><span class=\"log-text\">日志已清空</span></div>';
    }
    
    async refreshResults() {
        try {
            const response = await fetch('/api/results');
            const data = await response.json();
            
            this.renderResultList(data.files);
            
        } catch (error) {
            console.error('Failed to refresh results:', error);
        }
    }
    
    renderResultList(files) {
        const container = document.getElementById('result-list');
        
        if (files.length === 0) {
            container.innerHTML = '<p class=\"empty-state\">暂无处理结果</p>';
            return;
        }
        
        container.innerHTML = files.map(file => `
            <div class=\"result-item\">
                <div class=\"result-info\">
                    <div class=\"result-name\">${file.name}</div>
                    <div class=\"result-meta\">
                        ${this.formatFileSize(file.size)} • 
                        ${new Date(file.modified_time).toLocaleString()}
                    </div>
                </div>
                <button class=\"btn btn-primary btn-sm\" onclick=\"downloadResult('${file.name}')\">
                    <i class=\"fas fa-download\"></i>
                    下载
                </button>
            </div>
        `).join('');
    }
    
    async downloadResult(filename) {
        try {
            const response = await fetch(`/api/download/${filename}`);
            
            if (!response.ok) {
                throw new Error('下载失败');
            }
            
            // 创建下载链接
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.addLog(`📥 ${filename} 下载完成`, 'success');
            
        } catch (error) {
            this.showError(`下载失败: ${error.message}`);
        }
    }
    
    showError(message) {
        document.getElementById('error-message').textContent = message;
        document.getElementById('error-modal').style.display = 'block';
    }
    
    closeModal(modalId) {
        document.getElementById(modalId).style.display = 'none';
    }
}

// 全局函数
let app;

function clearCurrentFile() {
    app.clearCurrentFile();
}

function refreshResults() {
    app.refreshResults();
}

function startProcessing() {
    app.startProcessing();
}

function stopProcessing() {
    app.stopProcessing();
}

function clearLog() {
    app.clearLog();
}

function downloadResult(filename) {
    app.downloadResult(filename);
}

function closeModal(modalId) {
    app.closeModal(modalId);
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    app = new OCRApp();
});

// 关闭模态框点击外部区域
window.addEventListener('click', (event) => {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
});