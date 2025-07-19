// 现代磨砂玻璃风格OCR处理器

class ModernOCRApp {
    constructor() {
        this.currentTaskId = null;
        this.progressInterval = null;
        this.currentFile = null;
        this.systemStatus = null;
        this.theme = localStorage.getItem('theme') || 'light';
        
        this.init();
    }
    
    async init() {
        this.applyTheme();
        await this.loadSystemStatus();
        this.setupEventListeners();
        this.refreshResults();
        this.refreshCacheStats();
        this.setupAdvancedConfig();
    }
    
    // 主题管理
    applyTheme() {
        document.body.setAttribute('data-theme', this.theme);
        const themeIcon = document.querySelector('.theme-toggle i');
        if (themeIcon) {
            themeIcon.className = this.theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
        }
    }
    
    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', this.theme);
        this.applyTheme();
        
        // 添加主题切换动画
        document.body.style.transition = 'all 0.3s ease';
        setTimeout(() => {
            document.body.style.transition = '';
        }, 300);
        
        this.addLog(`🎨 切换到${this.theme === 'light' ? '浅色' : '深色'}主题`, 'info');
    }
    
    // 高级配置折叠
    setupAdvancedConfig() {
        const advancedContent = document.getElementById('advanced-content');
        const advancedIcon = document.getElementById('advanced-icon');
        
        // 默认收起状态
        advancedContent.classList.remove('expanded');
        advancedIcon.style.transform = 'rotate(0deg)';
    }
    
    toggleAdvanced() {
        const advancedContent = document.getElementById('advanced-content');
        const advancedIcon = document.getElementById('advanced-icon');
        
        const isExpanded = advancedContent.classList.contains('expanded');
        
        if (isExpanded) {
            advancedContent.classList.remove('expanded');
            advancedIcon.style.transform = 'rotate(0deg)';
        } else {
            advancedContent.classList.add('expanded');
            advancedIcon.style.transform = 'rotate(180deg)';
        }
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
        
        // 预处理选项
        document.getElementById('enable-preprocessing').addEventListener('change', () => {
            this.updatePreprocessingUI();
        });
        
        // 智能分块选项
        document.getElementById('enable-splitting').addEventListener('change', () => {
            this.updateSplittingUI();
        });
    }
    
    updatePreprocessingUI() {
        const enabled = document.getElementById('enable-preprocessing').checked;
        const modeSelect = document.getElementById('preprocessing-mode');
        
        modeSelect.disabled = !enabled;
        if (!enabled) {
            modeSelect.style.opacity = '0.5';
        } else {
            modeSelect.style.opacity = '1';
        }
    }
    
    updateSplittingUI() {
        const enabled = document.getElementById('enable-splitting').checked;
        const strategySelect = document.getElementById('split-strategy');
        
        strategySelect.disabled = !enabled;
        if (!enabled) {
            strategySelect.style.opacity = '0.5';
        } else {
            strategySelect.style.opacity = '1';
        }
    }
    
    async handleFileSelect(event) {
        const files = event.target.files || event.dataTransfer.files;
        if (!files || files.length === 0) return;
        
        const file = files[0];
        
        // 支持多种格式
        const supportedExtensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp', '.gif', '.docx', '.doc', '.pptx', '.ppt'];
        const isSupported = supportedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
        
        if (!isSupported) {
            this.showError('不支持的文件格式，请选择PDF、图片、Word或PowerPoint文件');
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
                pages: fileInfo.pages || 1
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
        const fileIcon = document.getElementById('file-icon');
        
        if (this.currentFile) {
            uploadArea.style.display = 'none';
            fileInfo.style.display = 'block';
            
            fileName.textContent = this.currentFile.name;
            fileMeta.textContent = `${this.formatFileSize(this.currentFile.size)} • ${this.currentFile.pages} 页`;
            
            // 根据文件类型设置图标
            const extension = this.currentFile.name.split('.').pop().toLowerCase();
            const iconMap = {
                'pdf': 'fas fa-file-pdf',
                'jpg': 'fas fa-file-image', 'jpeg': 'fas fa-file-image', 'png': 'fas fa-file-image',
                'tiff': 'fas fa-file-image', 'tif': 'fas fa-file-image', 'bmp': 'fas fa-file-image',
                'webp': 'fas fa-file-image', 'gif': 'fas fa-file-image',
                'docx': 'fas fa-file-word', 'doc': 'fas fa-file-word',
                'pptx': 'fas fa-file-powerpoint', 'ppt': 'fas fa-file-powerpoint'
            };
            
            fileIcon.className = iconMap[extension] || 'fas fa-file';
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
        const startPage = document.getElementById('start-page');
        const endPage = document.getElementById('end-page');
        
        if (!this.currentFile) {
            startPage.disabled = true;
            endPage.disabled = true;
            startPage.value = 1;
            endPage.value = 1;
            return;
        }
        
        startPage.disabled = false;
        endPage.disabled = false;
        endPage.max = this.currentFile.pages;
        startPage.max = this.currentFile.pages;
        
        // 只有在结束页为1时才设置默认值，避免覆盖用户修改的值
        if (parseInt(endPage.value) === 1) {
            endPage.value = Math.min(10, this.currentFile.pages);
        }
    }
    
    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
    
    // Token数字滚动动画 - 增强版
    animateTokenValue(elementId, newValue) {
        const element = document.getElementById(elementId);
        const counter = element.querySelector('.token-counter');
        
        if (!counter) return;
        
        const currentValue = parseInt(counter.textContent.replace(/,/g, '')) || 0;
        
        // 如果值没有变化，不执行动画
        if (currentValue === newValue) return;
        
        // 添加动画类和高亮效果
        element.classList.add('updating');
        counter.classList.add('counting');
        
        // 执行数字滚动动画
        this.countUpAnimation(counter, currentValue, newValue, 600);
        
        // 移除动画类
        setTimeout(() => {
            element.classList.remove('updating');
            counter.classList.remove('counting');
        }, 600);
    }
    
    // 优化的数字递增动画
    countUpAnimation(element, start, end, duration) {
        const startTime = Date.now();
        const difference = end - start;
        
        // 根据差值调整动画时长
        if (Math.abs(difference) < 50) {
            duration = Math.min(duration, 300);
        } else if (Math.abs(difference) > 1000) {
            duration = Math.max(duration, 800);
        }
        
        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // 使用更流畅的缓动函数
            const easeOutCubic = 1 - Math.pow(1 - progress, 3);
            const currentValue = Math.floor(start + (difference * easeOutCubic));
            
            element.textContent = currentValue.toLocaleString();
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            } else {
                element.textContent = end.toLocaleString();
            }
        };
        
        requestAnimationFrame(animate);
    }
    
    // 重置token统计
    resetTokenStats() {
        const tokenElements = ['total-tokens', 'ocr-tokens', 'gemini-tokens'];
        tokenElements.forEach(id => {
            const element = document.getElementById(id);
            const counter = element.querySelector('.token-counter');
            if (counter) {
                counter.textContent = '0';
            }
        });
    }
    
    async startProcessing() {
        if (!this.currentFile) {
            this.showError('请先上传文件');
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
        
        // 获取高级配置
        const enablePreprocessing = document.getElementById('enable-preprocessing').checked;
        const preprocessingMode = document.getElementById('preprocessing-mode').value;
        const enableSplitting = document.getElementById('enable-splitting').checked;
        const splitStrategy = document.getElementById('split-strategy').value;
        
        const request = {
            filename: this.currentFile.filename,
            start_page: startPage,
            end_page: endPage,
            ocr_service: ocrService,
            terminology: terminology,
            enable_preprocessing: enablePreprocessing,
            preprocessing_mode: preprocessingMode,
            enable_splitting: enableSplitting,
            split_strategy: splitStrategy
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
            
            // 重置进度和统计
            this.resetTokenStats();
            document.getElementById('progress-fill').style.width = '0%';
            document.getElementById('progress-percentage').textContent = '0%';
            document.getElementById('progress-label').textContent = '开始处理...';
            
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
        
        // 添加处理状态的视觉反馈
        if (processing) {
            startBtn.style.opacity = '0.6';
            stopBtn.style.opacity = '1';
        } else {
            startBtn.style.opacity = '1';
            stopBtn.style.opacity = '0.6';
        }
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
                    this.refreshCacheStats();
                    
                    // 处理完成后显示最终统计
                    this.showFinalStats(progress);
                }
                
            } catch (error) {
                console.error('Failed to fetch progress:', error);
            }
        }, 500);
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
        progressLabel.textContent = this.getProgressLabel(progress);
        
        // 更新Token统计（带动画）
        this.animateTokenValue('total-tokens', progress.total_tokens || 0);
        this.animateTokenValue('ocr-tokens', progress.ocr_tokens || 0);
        this.animateTokenValue('gemini-tokens', progress.gemini_tokens || 0);
        
        // 更新页面进度
        document.getElementById('page-progress').textContent = 
            `页面: ${progress.current_page || 0}/${progress.total_pages || 0}`;
        
        // 更新分块进度
        const chunkProgress = document.getElementById('chunk-progress');
        if (progress.total_chunks > 0) {
            chunkProgress.textContent = `分块: ${progress.current_chunk || 0}/${progress.total_chunks}`;
            chunkProgress.style.display = 'block';
        } else {
            chunkProgress.style.display = 'none';
        }
        
        // 根据状态更新进度条样式
        this.updateProgressBarStyle(progress);
    }
    
    getProgressLabel(progress) {
        if (progress.status === 'processing') {
            if (progress.current_file) {
                return `正在处理: ${progress.current_file}`;
            } else if (progress.current_page) {
                return `正在处理第 ${progress.current_page} 页`;
            } else {
                return '正在处理...';
            }
        } else if (progress.status === 'completed') {
            return '✅ 处理完成';
        } else if (progress.status === 'failed') {
            return '❌ 处理失败';
        } else if (progress.status === 'stopped') {
            return '⏹️ 处理已停止';
        } else {
            return '准备就绪';
        }
    }
    
    updateProgressBarStyle(progress) {
        const progressFill = document.getElementById('progress-fill');
        
        // 根据状态改变进度条颜色
        if (progress.status === 'completed') {
            progressFill.style.background = 'var(--accent-gradient)';
        } else if (progress.status === 'failed') {
            progressFill.style.background = 'var(--secondary-gradient)';
        } else if (progress.status === 'stopped') {
            progressFill.style.background = 'linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%)';
        } else {
            // 恢复默认样式
            progressFill.style.background = '';
        }
    }
    
    showFinalStats(progress) {
        const totalTokens = progress.total_tokens || 0;
        
        let statusMessage = '';
        if (progress.status === 'completed') {
            statusMessage = `✅ 处理完成！共消耗 ${totalTokens.toLocaleString()} tokens`;
        } else if (progress.status === 'failed') {
            statusMessage = `❌ 处理失败，已消耗 ${totalTokens.toLocaleString()} tokens`;
        } else if (progress.status === 'stopped') {
            statusMessage = `⏹️ 处理已停止，已消耗 ${totalTokens.toLocaleString()} tokens`;
        }
        
        if (statusMessage) {
            this.addLog(statusMessage, progress.status === 'completed' ? 'success' : 'warning');
        }
    }
    
    addLog(message, level = 'info') {
        const container = document.getElementById('log-container');
        const time = new Date().toLocaleTimeString();
        
        const logElement = document.createElement('div');
        logElement.className = `log-message ${level}`;
        logElement.innerHTML = `
            <span class="log-time">[${time}]</span>
            <span class="log-text">${message}</span>
        `;
        
        container.appendChild(logElement);
        container.scrollTop = container.scrollHeight;
        
        // 限制日志数量
        const logs = container.querySelectorAll('.log-message');
        if (logs.length > 100) {
            logs[0].remove();
        }
    }
    
    clearLog() {
        const container = document.getElementById('log-container');
        container.innerHTML = '<div class="log-message info"><span class="log-time">[系统]</span><span class="log-text">日志已清空</span></div>';
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
            container.innerHTML = '<p style="text-align: center; color: var(--text-muted); font-size: 0.9rem; padding: 12px;">暂无处理结果</p>';
            return;
        }
        
        container.innerHTML = files.map(file => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--bg-secondary); border: 1px solid var(--glass-border); border-radius: var(--border-radius-sm); margin-bottom: 8px; transition: all var(--transition-normal);" onmouseover="this.style.background='var(--bg-tertiary)'" onmouseout="this.style.background='var(--bg-secondary)'">
                <div style="flex: 1;">
                    <div style="font-weight: 500; color: var(--text-primary); margin-bottom: 4px;">${file.name}</div>
                    <div style="font-size: 0.85rem; color: var(--text-muted);">
                        ${this.formatFileSize(file.size)} • 
                        ${new Date(file.modified_time).toLocaleString()}
                    </div>
                </div>
                <button onclick="app.downloadResult('${file.name}')" style="padding: 8px 16px; background: var(--primary-gradient); color: white; border: none; border-radius: var(--border-radius-sm); cursor: pointer; transition: all var(--transition-normal); display: flex; align-items: center; gap: 6px;" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                    <i class="fas fa-download"></i>
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
    
    // 缓存管理
    async refreshCacheStats() {
        try {
            const response = await fetch('/api/cache/stats');
            const stats = await response.json();
            
            document.getElementById('cache-entries').textContent = stats.total_entries || 0;
            document.getElementById('cache-size').textContent = `${(stats.total_size_mb || 0).toFixed(1)} MB`;
            document.getElementById('cache-access').textContent = stats.total_access_count || 0;
            
            // 计算命中率
            const hitRate = stats.total_access_count > 0 ? 
                ((stats.cache_hits || 0) / stats.total_access_count * 100).toFixed(1) + '%' : '--';
            document.getElementById('cache-hits').textContent = hitRate;
            
        } catch (error) {
            console.error('Failed to refresh cache stats:', error);
        }
    }
    
    async cleanupCache() {
        if (!confirm('确定要清理缓存吗？这将删除过期和损坏的缓存。')) {
            return;
        }
        
        try {
            const response = await fetch('/api/cache/cleanup', { method: 'POST' });
            const result = await response.json();
            
            this.addLog(`🧹 ${result.message}`, 'success');
            if (result.stats) {
                this.addLog(`删除 ${result.stats.total_removed} 个缓存项，释放 ${(result.stats.bytes_freed/1024/1024).toFixed(2)} MB`, 'info');
            }
            
            // 刷新统计
            this.refreshCacheStats();
        } catch (error) {
            console.error('Failed to cleanup cache:', error);
            this.showError('清理缓存失败');
        }
    }
    
    async clearAllCache() {
        if (!confirm('确定要清空所有缓存吗？这个操作不可恢复！')) {
            return;
        }
        
        try {
            const response = await fetch('/api/cache/clear', { method: 'POST' });
            const result = await response.json();
            
            this.addLog(`🗑️ ${result.message}`, 'warning');
            
            // 刷新统计
            this.refreshCacheStats();
        } catch (error) {
            console.error('Failed to clear cache:', error);
            this.showError('清空缓存失败');
        }
    }
    
    showError(message) {
        document.getElementById('error-message').textContent = message;
        const modal = document.getElementById('error-modal');
        modal.classList.add('show');
    }
    
    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.remove('show');
    }
}

// 全局函数
let app;

function toggleTheme() {
    app.toggleTheme();
}

function toggleAdvanced() {
    app.toggleAdvanced();
}

function clearCurrentFile() {
    app.clearCurrentFile();
}

function refreshResults() {
    app.refreshResults();
}

function refreshCacheStats() {
    app.refreshCacheStats();
}

function cleanupCache() {
    app.cleanupCache();
}

function clearAllCache() {
    app.clearAllCache();
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

function closeModal(modalId) {
    app.closeModal(modalId);
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    app = new ModernOCRApp();
});

// 关闭模态框点击外部区域
window.addEventListener('click', (event) => {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('show');
    }
});