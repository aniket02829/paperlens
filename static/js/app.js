// DOM Elements
const themeToggle = document.getElementById('themeToggle');
const htmlEl = document.documentElement;

// Theme Logic
themeToggle.addEventListener('click', () => {
    htmlEl.classList.toggle('dark');
    const isDark = htmlEl.classList.contains('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    
    // Update chart if exists
    if(window.confidenceChartInstance) {
        window.confidenceChartInstance.options.plugins.tooltip.titleColor = isDark ? '#fff' : '#000';
        window.confidenceChartInstance.options.plugins.tooltip.bodyColor = isDark ? '#ccc' : '#333';
        window.confidenceChartInstance.options.plugins.tooltip.backgroundColor = isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.8)';
        window.confidenceChartInstance.update();
    }
});

// Navigation Elements
const btnSingleMode = document.getElementById('btnSingleMode');
const btnBulkMode = document.getElementById('btnBulkMode');
const fileInput = document.getElementById('fileInput');
const dropzone = document.getElementById('dropzone');
const fileList = document.getElementById('fileList');
const filePreviewContainer = document.getElementById('filePreviewContainer');
const btnAnalyze = document.getElementById('btnAnalyze');
const dropzoneText = document.getElementById('dropzoneText');

// Sections
const uploadSection = document.getElementById('uploadSection');
const loadingSection = document.getElementById('loadingSection');
const singleResultSection = document.getElementById('singleResultSection');
const bulkResultSection = document.getElementById('bulkResultSection');

let currentMode = 'single'; // 'single' or 'bulk'
let selectedFiles = [];

// Tab Switching
btnSingleMode.addEventListener('click', () => {
    currentMode = 'single';
    btnSingleMode.classList.add('bg-white', 'dark:bg-gray-700', 'text-brand-600', 'dark:text-brand-400', 'shadow');
    btnSingleMode.classList.remove('text-gray-500', 'hover:text-gray-700');
    
    btnBulkMode.classList.remove('bg-white', 'dark:bg-gray-700', 'text-brand-600', 'dark:text-brand-400', 'shadow');
    btnBulkMode.classList.add('text-gray-500', 'hover:text-gray-700');
    
    fileInput.removeAttribute('multiple');
    dropzoneText.textContent = "Drag & Drop your research paper here";
    clearFiles();
});

btnBulkMode.addEventListener('click', () => {
    currentMode = 'bulk';
    btnBulkMode.classList.add('bg-white', 'dark:bg-gray-700', 'text-brand-600', 'dark:text-brand-400', 'shadow');
    btnBulkMode.classList.remove('text-gray-500', 'hover:text-gray-700');
    
    btnSingleMode.classList.remove('bg-white', 'dark:bg-gray-700', 'text-brand-600', 'dark:text-brand-400', 'shadow');
    btnSingleMode.classList.add('text-gray-500', 'hover:text-gray-700');
    
    fileInput.setAttribute('multiple', 'true');
    dropzoneText.textContent = "Drag & Drop multiple papers here";
    clearFiles();
});

// Drag & Drop Handling
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, preventDefaults, false);
});
function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
});
['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
});

dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    handleFiles(dt.files);
});
fileInput.addEventListener('change', function() {
    handleFiles(this.files);
});

function handleFiles(files) {
    if(files.length === 0) return;
    
    if(currentMode === 'single') {
        selectedFiles = [files[0]];
    } else {
        selectedFiles = Array.from(files);
    }
    renderFileList();
}

function clearFiles() {
    selectedFiles = [];
    fileInput.value = '';
    filePreviewContainer.classList.add('hidden');
    btnAnalyze.classList.add('hidden');
    hideError();
}

function renderFileList() {
    fileList.innerHTML = '';
    if(selectedFiles.length === 0) {
        filePreviewContainer.classList.add('hidden');
        btnAnalyze.classList.add('hidden');
        return;
    }
    
    filePreviewContainer.classList.remove('hidden');
    btnAnalyze.classList.remove('hidden');
    
    document.getElementById('previewTitle').textContent = currentMode === 'single' ? 'Selected File' : `Selected Files (${selectedFiles.length})`;
    
    selectedFiles.forEach((file, index) => {
        const li = document.createElement('li');
        li.className = "flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded border border-gray-100 dark:border-gray-700";
        
        const icon = file.name.endsWith('.pdf') ? '<i class="fa-solid fa-file-pdf text-red-500 mr-3"></i>' : '<i class="fa-solid fa-file-word text-blue-500 mr-3"></i>';
        const size = (file.size / (1024*1024)).toFixed(2) + ' MB';
        
        li.innerHTML = `
            <div class="flex items-center truncate">
                ${icon}
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">${file.name}</span>
            </div>
            <div class="flex items-center space-x-3 ml-2">
                <span class="text-xs text-gray-500">${size}</span>
                <button type="button" class="text-red-400 hover:text-red-600 transition-colors btn-remove-file" data-idx="${index}">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
        `;
        fileList.appendChild(li);
    });
    
    document.querySelectorAll('.btn-remove-file').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = parseInt(e.currentTarget.getAttribute('data-idx'));
            selectedFiles.splice(idx, 1);
            if(currentMode === 'single') fileInput.value = ''; // Reset input
            renderFileList();
        });
    });
}

// Error Handling
function showError(title, msg) {
    document.getElementById('errorTitle').textContent = title;
    document.getElementById('errorMessage').textContent = msg;
    document.getElementById('errorAlert').classList.remove('hidden');
}
function hideError() {
    document.getElementById('errorAlert').classList.add('hidden');
}

// Counter Animation
function animateCounters() {
    const counters = document.querySelectorAll('.counter');
    counters.forEach(counter => {
        const target = +counter.getAttribute('data-target');
        const duration = 2000;
        const inc = target / (duration / 16);
        let current = 0;
        
        const updateCounter = () => {
            current += inc;
            if (current < target) {
                counter.innerText = Math.ceil(current).toLocaleString();
                requestAnimationFrame(updateCounter);
            } else {
                counter.innerText = target.toLocaleString();
            }
        };
        updateCounter();
    });
}
// Run once on load
animateCounters();


// API Calls & Transitions
btnAnalyze.addEventListener('click', async () => {
    if(selectedFiles.length === 0) return;
    
    hideError();
    uploadSection.classList.add('hidden');
    loadingSection.classList.remove('hidden');
    
    // Fake progress bar animation for UI
    const progressEl = document.getElementById('loadingProgress');
    let progress = 0;
    const interval = setInterval(() => {
        if(progress < 90) { progress += Math.random() * 10; progressEl.style.width = `${progress}%`; }
    }, 300);

    const formData = new FormData();
    try {
        let endpoint = '';
        if(currentMode === 'single') {
            formData.append('file', selectedFiles[0]);
            endpoint = '/analyze';
        } else {
            selectedFiles.forEach(f => formData.append('files', f));
            endpoint = '/analyze-bulk';
        }
        
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        clearInterval(interval);
        progressEl.style.width = '100%';
        
        // Wait a tiny bit for the 100% progress animation
        setTimeout(() => {
            loadingSection.classList.add('hidden');
            progressEl.style.width = '0%';
            
            if(!data.success) {
                uploadSection.classList.remove('hidden');
                showError('Analysis Failed', data.error || 'Server returned an error.');
                return;
            }
            
            if(currentMode === 'single') {
                renderSingleResult(data.result);
            } else {
                renderBulkResult(data.summary, data.results);
            }
        }, 500);
        
    } catch (err) {
        clearInterval(interval);
        progressEl.style.width = '0%';
        loadingSection.classList.add('hidden');
        uploadSection.classList.remove('hidden');
        showError('Connection Error', 'Could not connect to the server. Please check your backend.');
        console.error(err);
    }
});

// Reset flows
document.getElementById('btnResetSingle').addEventListener('click', () => {
    singleResultSection.classList.add('hidden');
    uploadSection.classList.remove('hidden');
    clearFiles();
});
document.getElementById('btnResetBulk').addEventListener('click', () => {
    bulkResultSection.classList.add('hidden');
    uploadSection.classList.remove('hidden');
    clearFiles();
});

// Render Single Result
function renderSingleResult(result) {
    singleResultSection.classList.remove('hidden');
    
    // Header Info
    document.getElementById('resTitle').textContent = result.title || 'Unknown Title';
    document.getElementById('resAuthorsText').textContent = result.authors || 'Unknown Authors';
    document.getElementById('resPageCount').textContent = result.page_count || '?';
    
    // Badge
    const badgeEl = document.getElementById('resCategoryBadge');
    badgeEl.className = "inline-flex items-center px-3 py-1 rounded-full text-sm font-bold uppercase tracking-wider mb-3 shadow-sm"; // reset
    if(result.category.toLowerCase() === 'journal') {
        badgeEl.classList.add('bg-blue-100', 'text-blue-800', 'dark:bg-blue-900', 'dark:text-blue-200', 'glow-badge-journal');
        badgeEl.innerHTML = '<i class="fa-solid fa-book-journal-whills mr-2"></i> Journal Article';
    } else if (result.category.toLowerCase() === 'conference') {
        badgeEl.classList.add('bg-purple-100', 'text-purple-800', 'dark:bg-purple-900', 'dark:text-purple-200', 'glow-badge-conf');
        badgeEl.innerHTML = '<i class="fa-solid fa-users mr-2"></i> Conference Paper';
    } else {
        badgeEl.classList.add('bg-orange-100', 'text-orange-800', 'dark:bg-orange-900', 'dark:text-orange-200', 'glow-badge-arxiv');
        badgeEl.innerHTML = '<i class="fa-solid fa-file-lines mr-2"></i> Preprint (Not Published)';
    }

    // Chart
    const confScore = Math.round(result.confidence * 100);
    document.getElementById('resConfidence').textContent = `${confScore}%`;
    let chartColor = confScore > 80 ? '#10b981' : (confScore > 60 ? '#f59e0b' : '#ef4444');
    
    if(window.confidenceChartInstance) window.confidenceChartInstance.destroy();
    const ctx = document.getElementById('confidenceChart').getContext('2d');
    window.confidenceChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [confScore, 100 - confScore],
                backgroundColor: [chartColor, 'rgba(156, 163, 175, 0.2)'],
                borderWidth: 0,
                borderRadius: 4
            }]
        },
        options: {
            cutout: '75%',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { tooltip: { enabled: false }, legend: { display: false } },
            animation: { animateScale: true }
        }
    });

    // Dynamic Body
    const contentArea = document.getElementById('resDynamicContent');
    contentArea.innerHTML = '';
    
    if(result.category.toLowerCase() === 'journal') {
        let qColor = 'bg-gray-100 text-gray-800';
        if(result.quartile === 'Q1') qColor = 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200';
        if(result.quartile === 'Q2') qColor = 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
        if(result.quartile === 'Q3') qColor = 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200';
        if(result.quartile === 'Q4') qColor = 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';

        contentArea.innerHTML = `
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-6 bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-100 dark:border-gray-700 shadow-sm">
                <div>
                    <h4 class="text-xs text-gray-500 uppercase tracking-wide font-semibold mb-1">Journal Venue</h4>
                    <p class="text-lg font-bold text-gray-900 dark:text-white">${result.venue || 'Unknown Journal'}</p>
                    <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">${result.publisher ? 'Publisher: ' + result.publisher : ''}</p>
                </div>
                <div class="flex items-center gap-4">
                    <div class="flex-shrink-0 w-16 h-16 rounded-full flex items-center justify-center font-black text-2xl shadow-inner ${qColor}">
                        ${result.quartile || 'N/A'}
                    </div>
                    <div>
                        <h4 class="text-xs text-gray-500 uppercase tracking-wide font-semibold mb-1">SJR Score</h4>
                        <div class="text-xl font-bold text-gray-900 dark:text-white">${result.sjr_score || 'N/A'}</div>
                    </div>
                </div>
            </div>
        `;
    } else if (result.category.toLowerCase() === 'conference') {
        contentArea.innerHTML = `
            <div class="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-100 dark:border-gray-700 shadow-sm">
                 <h4 class="text-xs text-gray-500 uppercase tracking-wide font-semibold mb-1">Conference Venue</h4>
                 <p class="text-lg font-bold text-gray-900 dark:text-white mb-4">${result.venue || 'Unknown Conference'}</p>
                 <div class="flex gap-4">
                     <span class="px-3 py-1 bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 rounded font-medium text-sm">
                        Type: ${result.conference_type || 'Unknown'}
                     </span>
                     <span class="px-3 py-1 bg-yellow-50 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300 rounded font-medium text-sm shadow-sm border border-yellow-200 dark:border-yellow-700/50">
                        CORE Rank: <strong>${result.core_rank || 'Unranked'}</strong>
                     </span>
                 </div>
            </div>
        `;
    } else {
        // Arxiv / Preprint
        let suggHtml = '';
        if(result.suggested_journals && result.suggested_journals.length > 0) {
            suggHtml = `<div class="mt-6"><h4 class="text-sm font-bold text-gray-800 dark:text-gray-200 mb-3">Recommended Journals for Submission:</h4>
            <div class="overflow-x-auto rounded border border-gray-200 dark:border-gray-700">
                <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
                    <thead class="bg-gray-50 dark:bg-gray-800"><tr><th class="px-4 py-2 text-left">Journal</th><th class="px-4 py-2 text-center">Quartile</th><th class="px-4 py-2 text-right">SJR</th></tr></thead>
                    <tbody class="divide-y divide-gray-200 dark:divide-gray-700">`;
            result.suggested_journals.forEach(j => {
                suggHtml += `<tr><td class="px-4 py-2 font-medium">${j.name}</td><td class="px-4 py-2 text-center"><span class="px-2 py-0.5 rounded text-xs font-bold bg-${j.quartile_color || 'gray'}-100 text-${j.quartile_color || 'gray'}-800">${j.quartile}</span></td><td class="px-4 py-2 text-right">${j.sjr_score}</td></tr>`;
            });
            suggHtml += `</tbody></table></div></div>`;
        }

        contentArea.innerHTML = `
            <div class="bg-orange-50 dark:bg-orange-900/10 border border-orange-200 dark:border-orange-800/50 rounded-xl p-6 shadow-sm">
                <p class="text-orange-800 dark:text-orange-300 font-medium"><i class="fa-solid fa-triangle-exclamation mr-2"></i> This paper appears to be a preprint and is not officially peer-reviewed or published in a major venue.</p>
                ${suggHtml}
            </div>
        `;
    }

    // Signals
    const sigList = document.getElementById('resSignalsList');
    sigList.innerHTML = '';
    (result.signals || []).forEach(sig => {
        sigList.innerHTML += `<li class="flex items-start text-sm text-gray-600 dark:text-gray-300"><i class="fa-solid fa-check text-green-500 mt-1 mr-3"></i><span>${sig}</span></li>`;
    });

    // Share logic setup
    window.currentResultSummary = `PaperLens Classification: ${result.title}\nCategory: ${result.category.toUpperCase()}\nVenue: ${result.venue || 'N/A'}\nConfidence: ${Math.round(result.confidence * 100)}%`;
}

// Share logic
document.getElementById('btnShare').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    const originalText = btn.innerHTML;
    try {
        await navigator.clipboard.writeText(window.currentResultSummary);
        btn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Copied!';
        btn.classList.add('bg-green-100', 'text-green-800');
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.classList.remove('bg-green-100', 'text-green-800');
        }, 2000);
    } catch(err) {
        console.error('Failed to copy', err);
    }
});


// Accordion
document.getElementById('signalsToggle').addEventListener('click', () => {
    const content = document.getElementById('signalsContent');
    const icon = document.getElementById('signalsIcon');
    content.classList.toggle('hidden');
    icon.classList.toggle('rotate-180');
});

// Render Bulk Result
let currentBulkData = [];
function renderBulkResult(summary, results) {
    bulkResultSection.classList.remove('hidden');
    currentBulkData = results;
    
    document.getElementById('bulkCountJournal').textContent = summary.journals || 0;
    document.getElementById('bulkCountConf').textContent = summary.conferences || 0;
    document.getElementById('bulkCountArxiv').textContent = summary.arxiv || 0;
    
    const tbody = document.getElementById('bulkTableBody');
    tbody.innerHTML = '';
    
    results.forEach(res => {
        let badge = '';
        let details = '';
        const cat = res.category.toLowerCase();
        if(cat === 'journal') {
            badge = `<span class="px-2 py-1 rounded text-xs font-bold bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">JOURNAL</span>`;
            details = `<div class="text-xs"><strong>${res.venue}</strong> <span class="mx-1">&bull;</span> ${res.quartile||'N/A'}</div>`;
        } else if (cat === 'conference') {
            badge = `<span class="px-2 py-1 rounded text-xs font-bold bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">CONF</span>`;
            details = `<div class="text-xs"><strong>${res.venue}</strong> <span class="mx-1">&bull;</span> Rank: ${res.core_rank||'N/A'}</div>`;
        } else {
            badge = `<span class="px-2 py-1 rounded text-xs font-bold bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">PREPRINT</span>`;
            details = `<div class="text-xs text-gray-500 italic">Not peer-reviewed</div>`;
        }
        
        const confColor = res.confidence > 0.8 ? 'text-green-600' : (res.confidence > 0.6 ? 'text-yellow-600' : 'text-red-600');
        
        tbody.innerHTML += `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm font-medium text-gray-900 dark:text-white truncate max-w-[200px]" title="${res.title}">${res.title}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">${badge}</td>
                <td class="px-6 py-4 whitespace-nowrap text-gray-500 dark:text-gray-400">${details}</td>
                <td class="px-6 py-4 whitespace-nowrap text-center text-sm font-bold ${confColor}">${Math.round(res.confidence * 100)}%</td>
            </tr>
        `;
    });
}

// Export CSV
document.getElementById('btnExportCSV').addEventListener('click', () => {
    if(!currentBulkData || currentBulkData.length === 0) return;
    
    const headers = ['Title', 'Category', 'Venue', 'Quartile/Rank', 'Confidence'];
    const rows = currentBulkData.map(r => [
        `"${r.title.replace(/"/g, '""')}"`,
        r.category,
        `"${(r.venue || '').replace(/"/g, '""')}"`,
        r.quartile || r.core_rank || '',
        Math.round(r.confidence * 100) + '%'
    ]);
    
    const csvContent = [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "paperlens_results.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});

// Modal Logic
const modal = document.getElementById('aboutModal');
const btnAbout = document.getElementById('aboutBtn');
const btnClose = document.getElementById('closeModalBtn');
const btnClose2 = document.getElementById('closeModalBtn2');
const modalBackdrop = document.getElementById('aboutModalBackdrop');

function toggleModal() {
    modal.classList.toggle('hidden');
}

btnAbout.addEventListener('click', toggleModal);
btnClose.addEventListener('click', toggleModal);
btnClose2.addEventListener('click', toggleModal);
modalBackdrop.addEventListener('click', toggleModal);
