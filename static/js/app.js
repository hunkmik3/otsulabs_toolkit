/* ═══════════════════════════════════════════════════════════════
   OTSU TOOLKIT — Frontend Application
   ═══════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
    // ═══ Tab Navigation ═══
    const navTabs = document.querySelectorAll('.nav-tab');
    const toolPanels = document.querySelectorAll('.tool-panel');

    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tool = tab.dataset.tool;

            navTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            toolPanels.forEach(p => p.classList.remove('active'));
            const panel = document.getElementById(`panel-${tool}`);
            if (panel) {
                panel.classList.add('active');
            }
        });
    });

    // ═══ Toast Notifications ═══
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icon = type === 'error' ? '✗' : type === 'success' ? '✓' : 'ℹ';
        toast.innerHTML = `<span>${icon}</span> ${message}`;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'toastOut 0.3s ease-out forwards';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ═══ Local Storage for API Key ═══
    const geminiKeyInput = document.getElementById('gemini-key');
    const savedKey = localStorage.getItem('gemini_api_key');
    if (savedKey && geminiKeyInput) {
        geminiKeyInput.value = savedKey;
    }

    // Toggle key visibility
    const toggleKeyBtn = document.getElementById('toggle-key-visibility');
    if (toggleKeyBtn) {
        toggleKeyBtn.addEventListener('click', () => {
            const isPassword = geminiKeyInput.type === 'password';
            geminiKeyInput.type = isPassword ? 'text' : 'password';
            toggleKeyBtn.textContent = isPassword ? '🔒' : '👁';
        });
    }

    // ═══ WATERMARK MODULE ═══
    setupUploadModule({
        dropzoneId: 'watermark-dropzone',
        uploadAreaId: 'watermark-upload-area',
        fileInputId: 'watermark-file-input',
        previewAreaId: 'watermark-preview-area',
        previewContentId: 'watermark-preview-content',
        fileNameId: 'watermark-file-name',
        clearBtnId: 'watermark-clear-btn',
        submitBtnId: 'watermark-submit-btn',
        progressAreaId: 'watermark-progress',
        progressTextId: 'watermark-progress-text',
        progressBarId: 'watermark-progress-bar',
        resultAreaId: 'watermark-result',
        uploadEndpoint: '/api/watermark/upload',
        onResult: (result) => {
            const previewEl = document.getElementById('watermark-result-preview');
            const downloadBtn = document.getElementById('watermark-download-btn');

            if (result.type === 'image') {
                previewEl.innerHTML = `<img src="/preview/${result.filename}" alt="Watermarked">`;
            } else {
                previewEl.innerHTML = `<video src="/preview/${result.filename}" controls></video>`;
            }

            // Build proper download filename: originalname_watermarked.ext
            const origName = result.original_name || 'file';
            const lastDot = origName.lastIndexOf('.');
            const baseName = lastDot > 0 ? origName.substring(0, lastDot) : origName;
            const ext = lastDot > 0 ? origName.substring(lastDot) : '';
            const downloadName = `${baseName}_watermarked${ext}`;

            downloadBtn.href = `/download/${result.filename}?original_name=${encodeURIComponent(downloadName)}`;
            downloadBtn.setAttribute('download', downloadName);
        }
    });

    // ═══ CONTACT SHEET MODULE ═══
    setupUploadModule({
        dropzoneId: 'contactsheet-dropzone',
        uploadAreaId: 'contactsheet-upload-area',
        fileInputId: 'contactsheet-file-input',
        previewAreaId: 'contactsheet-preview-area',
        previewContentId: 'contactsheet-preview-content',
        fileNameId: 'contactsheet-file-name',
        clearBtnId: 'contactsheet-clear-btn',
        submitBtnId: 'contactsheet-submit-btn',
        progressAreaId: 'contactsheet-progress',
        progressTextId: 'contactsheet-progress-text',
        progressBarId: 'contactsheet-progress-bar',
        resultAreaId: 'contactsheet-result',
        uploadEndpoint: '/api/contactsheet/upload',
        getExtraFormData: () => {
            return {
                interval: document.getElementById('cs-interval').value,
                width: document.getElementById('cs-width').value,
                cols: document.getElementById('cs-cols').value
            };
        },
        onResult: (result) => {
            const previewEl = document.getElementById('contactsheet-result-preview');
            const downloadBtn = document.getElementById('contactsheet-download-btn');
            const metaEl = document.getElementById('contactsheet-meta');

            // Build proper download filename: originalname_contact_sheet.jpg
            const origName = result.original_name || 'video';
            const lastDot = origName.lastIndexOf('.');
            const baseName = lastDot > 0 ? origName.substring(0, lastDot) : origName;
            const downloadName = `${baseName}_contact_sheet.jpg`;

            previewEl.innerHTML = `<img src="/preview/${result.filename}" alt="Contact Sheet">`;
            downloadBtn.href = `/download/${result.filename}?original_name=${encodeURIComponent(downloadName)}`;
            downloadBtn.setAttribute('download', downloadName);

            metaEl.innerHTML = `${result.duration}s • ${result.frames} frames • Grid ${result.grid}`;
        }
    });

    // ═══ YOUTUBE MODULE ═══
    const ytSubmitBtn = document.getElementById('youtube-submit-btn');
    const ytProgressArea = document.getElementById('youtube-progress');
    const ytProgressText = document.getElementById('youtube-progress-text');
    const ytResultArea = document.getElementById('youtube-result');

    ytSubmitBtn.addEventListener('click', async () => {
        const url = document.getElementById('youtube-url').value.trim();
        const apiKey = document.getElementById('gemini-key').value.trim();
        const customPrompt = document.getElementById('custom-prompt').value.trim();

        if (!url) {
            showToast('Vui lòng nhập YouTube URL', 'error');
            return;
        }
        if (!apiKey) {
            showToast('Vui lòng nhập Gemini API Key', 'error');
            return;
        }

        // Save API key
        localStorage.setItem('gemini_api_key', apiKey);

        // UI updates
        ytSubmitBtn.disabled = true;
        ytSubmitBtn.querySelector('.btn-text').textContent = 'Đang xử lý...';
        ytSubmitBtn.querySelector('.btn-spinner').classList.remove('hidden');
        ytResultArea.classList.add('hidden');
        ytProgressArea.classList.remove('hidden');
        ytProgressText.textContent = 'Đang kết nối...';

        try {
            const response = await fetch('/api/youtube/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, api_key: apiKey, custom_prompt: customPrompt })
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Unknown error');
            }

            // Poll for status
            pollTaskStatus(data.task_id, {
                onProgress: (progress) => {
                    ytProgressText.textContent = progress || 'Đang xử lý...';
                },
                onComplete: (result) => {
                    ytProgressArea.classList.add('hidden');
                    ytResultArea.classList.remove('hidden');

                    document.getElementById('yt-result-title').textContent = result.title || 'Video';
                    document.getElementById('yt-result-summary').textContent = result.summary || 'Không có tóm tắt';
                    document.getElementById('yt-result-transcript').textContent = result.transcript_preview || '';

                    resetYoutubeBtn();
                    showToast('Tóm tắt video thành công!', 'success');
                },
                onError: (error) => {
                    ytProgressArea.classList.add('hidden');
                    resetYoutubeBtn();
                    showToast(`Lỗi: ${error}`, 'error');
                }
            });

        } catch (error) {
            ytProgressArea.classList.add('hidden');
            resetYoutubeBtn();
            showToast(`Lỗi: ${error.message}`, 'error');
        }
    });

    function resetYoutubeBtn() {
        ytSubmitBtn.disabled = false;
        ytSubmitBtn.querySelector('.btn-text').textContent = 'Tóm tắt Video';
        ytSubmitBtn.querySelector('.btn-spinner').classList.add('hidden');
    }

    // Copy summary button
    const copySummaryBtn = document.getElementById('yt-copy-summary');
    if (copySummaryBtn) {
        copySummaryBtn.addEventListener('click', () => {
            const summaryText = document.getElementById('yt-result-summary').textContent;
            navigator.clipboard.writeText(summaryText).then(() => {
                copySummaryBtn.classList.add('copied');
                copySummaryBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Đã copy!`;
                setTimeout(() => {
                    copySummaryBtn.classList.remove('copied');
                    copySummaryBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy tóm tắt`;
                }, 2000);
            });
        });
    }

    // ═══ Upload Module Factory ═══
    function setupUploadModule(config) {
        const dropzone = document.getElementById(config.dropzoneId);
        const uploadArea = document.getElementById(config.uploadAreaId);
        const fileInput = document.getElementById(config.fileInputId);
        const previewArea = document.getElementById(config.previewAreaId);
        const previewContent = document.getElementById(config.previewContentId);
        const fileNameEl = document.getElementById(config.fileNameId);
        const clearBtn = document.getElementById(config.clearBtnId);
        const submitBtn = document.getElementById(config.submitBtnId);
        const progressArea = document.getElementById(config.progressAreaId);
        const progressText = document.getElementById(config.progressTextId);
        const resultArea = document.getElementById(config.resultAreaId);

        let selectedFile = null;

        // Click to upload
        uploadArea.addEventListener('click', () => fileInput.click());

        // Drag & drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('drag-over');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            if (e.dataTransfer.files.length) {
                handleFile(e.dataTransfer.files[0]);
            }
        });

        // File input change
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) {
                handleFile(fileInput.files[0]);
            }
        });

        // Clear
        clearBtn.addEventListener('click', () => {
            selectedFile = null;
            fileInput.value = '';
            uploadArea.classList.remove('hidden');
            previewArea.classList.add('hidden');
            submitBtn.classList.add('hidden');
            resultArea.classList.add('hidden');
        });

        function handleFile(file) {
            selectedFile = file;
            fileNameEl.textContent = file.name;
            uploadArea.classList.add('hidden');
            previewArea.classList.remove('hidden');
            submitBtn.classList.remove('hidden');
            resultArea.classList.add('hidden');

            // Generate preview
            previewContent.innerHTML = '';
            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = URL.createObjectURL(file);
                previewContent.appendChild(img);
            } else if (file.type.startsWith('video/')) {
                const video = document.createElement('video');
                video.src = URL.createObjectURL(file);
                video.controls = true;
                video.muted = true;
                previewContent.appendChild(video);
            }
        }

        // Submit
        submitBtn.addEventListener('click', async () => {
            if (!selectedFile) {
                showToast('Vui lòng chọn file', 'error');
                return;
            }

            submitBtn.disabled = true;
            submitBtn.querySelector('.btn-text').textContent = 'Đang tải lên...';
            submitBtn.querySelector('.btn-spinner').classList.remove('hidden');
            resultArea.classList.add('hidden');
            progressArea.classList.remove('hidden');
            progressText.textContent = 'Đang tải file lên...';

            const formData = new FormData();
            formData.append('file', selectedFile);

            // Extra form data (for contact sheet)
            if (config.getExtraFormData) {
                const extra = config.getExtraFormData();
                for (const [key, value] of Object.entries(extra)) {
                    formData.append(key, value);
                }
            }

            try {
                const response = await fetch(config.uploadEndpoint, {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (!data.success) {
                    throw new Error(data.error || 'Upload failed');
                }

                progressText.textContent = 'Đang xử lý...';

                pollTaskStatus(data.task_id, {
                    onProgress: (progress) => {
                        progressText.textContent = progress || 'Đang xử lý...';
                    },
                    onComplete: (result) => {
                        progressArea.classList.add('hidden');
                        resultArea.classList.remove('hidden');
                        submitBtn.classList.add('hidden');

                        config.onResult(result);

                        resetBtn();
                        showToast('Xử lý hoàn thành!', 'success');
                    },
                    onError: (error) => {
                        progressArea.classList.add('hidden');
                        resetBtn();
                        showToast(`Lỗi: ${error}`, 'error');
                    }
                });

            } catch (error) {
                progressArea.classList.add('hidden');
                resetBtn();
                showToast(`Lỗi: ${error.message}`, 'error');
            }
        });

        function resetBtn() {
            submitBtn.disabled = false;
            const defaultText = config.uploadEndpoint.includes('watermark') ? 'Gán Watermark' : 'Tạo Contact Sheet';
            submitBtn.querySelector('.btn-text').textContent = defaultText;
            submitBtn.querySelector('.btn-spinner').classList.add('hidden');
        }
    }

    // ═══ Task Polling ═══
    function pollTaskStatus(taskId, callbacks) {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${taskId}`);
                const data = await response.json();

                if (data.status === 'processing' || data.status === 'queued') {
                    if (callbacks.onProgress) {
                        callbacks.onProgress(data.progress);
                    }
                } else if (data.status === 'completed') {
                    clearInterval(interval);
                    if (callbacks.onComplete) {
                        callbacks.onComplete(data.result);
                    }
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    if (callbacks.onError) {
                        callbacks.onError(data.error || 'Unknown error');
                    }
                }
            } catch (error) {
                clearInterval(interval);
                if (callbacks.onError) {
                    callbacks.onError(error.message);
                }
            }
        }, 1500);
    }

});
