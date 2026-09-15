/**
 * VlookUp Resume Analyzer & Interview Intelligence Suite
 * Client Logic & Dynamic Recruiter Workspace
 */

const ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png'];
const MAX_SIZE_MB = 4;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

// DOM Elements - Upload & Hero
const heroBanner = document.getElementById('hero-banner');
const uploadSection = document.getElementById('upload-section');
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const cameraInput = document.getElementById('camera-input');
const chooseBtn = document.getElementById('choose-btn');
const cameraBtn = document.getElementById('camera-btn');
const fileInfo = document.getElementById('file-info');
const fileName = document.getElementById('file-name');
const fileSize = document.getElementById('file-size');
const generateBtn = document.getElementById('generate-btn');
const changeFileBtn = document.getElementById('change-file-btn');
const errorMessage = document.getElementById('error-message');
const errorText = document.getElementById('error-text');

// DOM Elements - Loading & Stepper
const loadingSection = document.getElementById('loading-section');
const stepperProgressFill = document.getElementById('stepper-progress-fill');
const stepUpload = document.getElementById('step-upload');
const stepExtract = document.getElementById('step-extract');
const stepGenerate = document.getElementById('step-generate');
const stepFormat = document.getElementById('step-format');

// DOM Elements - Results
const resultSection = document.getElementById('result-section');
const candidateAvatar = document.getElementById('candidate-avatar');
const resultName = document.getElementById('result-name');
const resultSummary = document.getElementById('result-summary');
const statTotalQ = document.getElementById('stat-total-q');
const statCategoriesCount = document.getElementById('stat-categories-count');
const resultQuestions = document.getElementById('result-questions');
const questionSearchInput = document.getElementById('question-search-input');
const searchClearBtn = document.getElementById('search-clear-btn');
const searchMatchCount = document.getElementById('search-match-count');
const categoryTabs = document.getElementById('category-tabs');
const toggleAnswersBtn = document.getElementById('toggle-answers-btn');
const toggleAnswersText = document.getElementById('toggle-answers-text');
const copyAllBtn = document.getElementById('copy-all-btn');
const generateAgainBtn = document.getElementById('generate-again-btn');
const printBtn = document.getElementById('print-btn');
const toastEl = document.getElementById('toast');

// View Mode Buttons (Technical Key vs HR Guide)
const viewModeTechBtn = document.getElementById('view-mode-tech');
const viewModeHrBtn = document.getElementById('view-mode-hr');

// 3 Dedicated Download Buttons
const downloadInterviewerBtn = document.getElementById('download-interviewer-btn');
const downloadHrBtn = document.getElementById('download-hr-btn');
const downloadCandidateBtn = document.getElementById('download-candidate-btn');

// State Variables
let selectedFile = null;
let lastResult = null;
let activeCategory = 'all';
let searchQuery = '';
let allCollapsed = false;
let currentViewMode = 'technical'; // 'technical' | 'hr'
let stepInterval = null;

// ==========================================================================
// Helper Utilities
// ==========================================================================

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

function getInitials(name) {
    if (!name) return 'CD';
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function showToast(message) {
    if (!toastEl) return;
    toastEl.textContent = message;
    toastEl.classList.remove('hidden');
    clearTimeout(toastEl._timer);
    toastEl._timer = setTimeout(() => {
        toastEl.classList.add('hidden');
    }, 2400);
}

function showError(msg) {
    if (errorText && errorMessage) {
        errorText.textContent = msg;
        errorMessage.classList.remove('hidden');
    }
}

function hideError() {
    if (errorMessage) {
        errorMessage.classList.add('hidden');
    }
}

function validateFile(file) {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    const type = (file.type || '').toLowerCase();

    let valid = ALLOWED_EXTENSIONS.includes(ext);
    if (!valid && (type === 'image/jpeg' || type === 'image/png' || type === 'application/pdf')) {
        valid = true;
    }

    if (!valid) {
        showError('Please upload a PDF document or a clear JPG/PNG image.');
        return false;
    }
    if (file.size > MAX_SIZE_BYTES) {
        showError(`The file size (${formatBytes(file.size)}) exceeds the maximum allowed limit of ${MAX_SIZE_MB} MB.`);
        return false;
    }
    return true;
}

function normalizeFileName(file) {
    const type = (file.type || '').toLowerCase();
    if (!file.name || !file.name.includes('.')) {
        if (type === 'image/png') return 'camera_capture.png';
        if (type === 'image/jpeg' || type === 'image/jpg') return 'camera_capture.jpg';
        return 'scanned_resume.pdf';
    }
    return file.name;
}

// ==========================================================================
// File Selection & Drag-and-Drop
// ==========================================================================

function handleFileSelect(file) {
    hideError();
    if (!validateFile(file)) return;

    const normalizedName = normalizeFileName(file);
    selectedFile = new File([file], normalizedName, { type: file.type });
    fileName.textContent = normalizedName;
    fileSize.textContent = formatBytes(file.size);

    uploadArea.classList.add('hidden');
    fileInfo.classList.remove('hidden');
}

if (chooseBtn) {
    chooseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });
}

if (cameraBtn) {
    cameraBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        cameraInput.click();
    });
}

if (uploadArea) {
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-active');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-active');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-active');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });
}

if (fileInput) {
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileSelect(fileInput.files[0]);
        }
    });
}

if (cameraInput) {
    cameraInput.addEventListener('change', () => {
        if (cameraInput.files.length > 0) {
            handleFileSelect(cameraInput.files[0]);
        }
    });
}

if (changeFileBtn) {
    changeFileBtn.addEventListener('click', () => {
        selectedFile = null;
        fileInput.value = '';
        cameraInput.value = '';
        fileInfo.classList.add('hidden');
        uploadArea.classList.remove('hidden');
        hideError();
    });
}

// ==========================================================================
// Generation & Stepper Animation
// ==========================================================================

function startStepperAnimation() {
    let stage = 1;
    if (stepperProgressFill) stepperProgressFill.style.width = '25%';

    const updateStepUI = (st) => {
        if (st >= 1 && stepUpload) stepUpload.className = 'step-item completed';
        if (st >= 2 && stepExtract) {
            stepExtract.className = 'step-item active';
            if (stepperProgressFill) stepperProgressFill.style.width = '50%';
        }
        if (st >= 3 && stepGenerate) {
            if (stepExtract) stepExtract.className = 'step-item completed';
            stepGenerate.className = 'step-item active';
            if (stepperProgressFill) stepperProgressFill.style.width = '75%';
        }
        if (st >= 4 && stepFormat) {
            if (stepGenerate) stepGenerate.className = 'step-item completed';
            stepFormat.className = 'step-item active';
            if (stepperProgressFill) stepperProgressFill.style.width = '95%';
        }
    };

    updateStepUI(stage);
    stepInterval = setInterval(() => {
        if (stage < 4) {
            stage++;
            updateStepUI(stage);
        }
    }, 2800);
}

function stopStepperAnimation() {
    if (stepInterval) {
        clearInterval(stepInterval);
        stepInterval = null;
    }
}

if (generateBtn) {
    generateBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        hideError();
        generateBtn.disabled = true;
        uploadSection.classList.add('hidden');
        loadingSection.classList.remove('hidden');
        resultSection.classList.add('hidden');

        startStepperAnimation();

        try {
            const formData = new FormData();
            formData.append('file', selectedFile);

            const response = await fetch('/api/generate', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to generate interview questions.');
            }

            if (!data.success || !data.result) {
                throw new Error(data.error || 'Failed to generate interview questions.');
            }

            stopStepperAnimation();
            if (stepperProgressFill) stepperProgressFill.style.width = '100%';
            if (stepFormat) stepFormat.className = 'step-item completed';

            lastResult = data.result;
            renderResults(data.result);
        } catch (err) {
            stopStepperAnimation();
            loadingSection.classList.add('hidden');
            uploadSection.classList.remove('hidden');
            fileInfo.classList.remove('hidden');
            uploadArea.classList.add('hidden');
            generateBtn.disabled = false;
            showError(err.message || 'Something went wrong while processing the resume. Please try again.');
        }
    });
}

// ==========================================================================
// Category & View Mapping
// ==========================================================================

function getCategoryClass(catName) {
    const norm = (catName || '').toLowerCase();
    if (norm.includes('mcq')) return 'tag-mcq';
    if (norm.includes('basic') || norm.includes('tech')) return 'tag-basic-technical';
    if (norm.includes('mern') || norm.includes('mid')) return 'tag-mid-technical';
    if (norm.includes('skill')) return 'tag-resume-skills';
    if (norm.includes('project')) return 'tag-project';
    if (norm.includes('scenario') || norm.includes('vlookup')) return 'tag-vlookup-scenario';
    return 'tag-basic-technical';
}

function renderResults(result) {
    loadingSection.classList.add('hidden');
    resultSection.classList.remove('hidden');
    if (heroBanner) heroBanner.classList.add('hidden');

    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Populate Candidate Information
    const candidate = result.candidate_name || 'Candidate';
    resultName.textContent = candidate;
    candidateAvatar.textContent = getInitials(candidate);
    resultSummary.textContent = result.summary || 'Summary not available.';

    // Statistics
    const totalQuestions = result.questions ? result.questions.length : 0;
    statTotalQ.textContent = totalQuestions;

    const uniqueCats = new Set((result.questions || []).map(q => q.category));
    statCategoriesCount.textContent = uniqueCats.size || 6;

    // Update Counts on Category Tabs
    updateCategoryCounts(result.questions || []);

    // Render Question List
    renderFilteredQuestions();
}

function updateCategoryCounts(questions) {
    const counts = { all: questions.length };
    for (const q of questions) {
        const cat = (q.category || '').toLowerCase();
        if (cat.includes('mcq')) counts.mcq = (counts.mcq || 0) + 1;
        else if (cat.includes('basic')) counts.basic = (counts.basic || 0) + 1;
        else if (cat.includes('mern') || cat.includes('mid')) counts.mern = (counts.mern || 0) + 1;
        else if (cat.includes('skill')) counts.skills = (counts.skills || 0) + 1;
        else if (cat.includes('project')) counts.projects = (counts.projects || 0) + 1;
        else if (cat.includes('scenario') || cat.includes('vlookup')) counts.scenario = (counts.scenario || 0) + 1;
    }

    const countAll = document.getElementById('count-all');
    if (countAll) countAll.textContent = counts.all || 0;

    const countMcq = document.getElementById('count-mcq');
    if (countMcq) countMcq.textContent = counts.mcq || 0;

    const countBasic = document.getElementById('count-basic');
    if (countBasic) countBasic.textContent = counts.basic || 0;

    const countMern = document.getElementById('count-mern');
    if (countMern) countMern.textContent = counts.mern || 0;

    const countSkills = document.getElementById('count-skills');
    if (countSkills) countSkills.textContent = counts.skills || 0;

    const countProjects = document.getElementById('count-projects');
    if (countProjects) countProjects.textContent = counts.projects || 0;

    const countScenario = document.getElementById('count-scenario');
    if (countScenario) countScenario.textContent = counts.scenario || 0;
}

function matchCategory(qCategory, targetFilter) {
    if (targetFilter === 'all') return true;
    const cat = (qCategory || '').toLowerCase();
    const target = targetFilter.toLowerCase();

    if (target.includes('mcq')) return cat.includes('mcq');
    if (target.includes('basic')) return cat.includes('basic');
    if (target.includes('mern') || target.includes('mid')) return cat.includes('mern') || cat.includes('mid');
    if (target.includes('skill')) return cat.includes('skill');
    if (target.includes('project')) return cat.includes('project');
    if (target.includes('scenario') || target.includes('vlookup')) return cat.includes('scenario') || cat.includes('vlookup');

    return cat === target;
}

function renderFilteredQuestions() {
    if (!lastResult || !lastResult.questions) return;

    const questions = lastResult.questions;
    const query = searchQuery.trim().toLowerCase();

    // Filter by Category
    let filtered = questions.filter(q => matchCategory(q.category, activeCategory));

    // Filter by Search Query
    if (query) {
        filtered = filtered.filter(q => {
            const questionText = (q.question || '').toLowerCase();
            const answerText = (q.answer || '').toLowerCase();
            const hrText = (q.hr_answer || '').toLowerCase();
            const catText = (q.category || '').toLowerCase();
            const optionsText = (q.options || []).join(' ').toLowerCase();
            return (
                questionText.includes(query) ||
                answerText.includes(query) ||
                hrText.includes(query) ||
                catText.includes(query) ||
                optionsText.includes(query)
            );
        });
        if (searchMatchCount) searchMatchCount.textContent = `${filtered.length} found`;
    } else {
        if (searchMatchCount) searchMatchCount.textContent = '';
    }

    // Handle Empty Results
    if (filtered.length === 0) {
        resultQuestions.innerHTML = `
            <div class="empty-filter-state">
                <h3 class="empty-filter-title">No matching interview questions</h3>
                <p>Try clearing your search keyword or switching category tabs to view questions.</p>
            </div>
        `;
        return;
    }

    // Group questions by category
    const grouped = {};
    for (const q of filtered) {
        const cat = q.category || 'General';
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(q);
    }

    const CATEGORY_ORDER = [
        'MCQ',
        'Basic Technical',
        'Mid Technical (MERN)',
        'Resume Skills',
        'Project',
        'VlookUp Scenario',
    ];

    const sortedCats = Object.keys(grouped).sort((a, b) => {
        const getIdx = (name) => {
            for (let i = 0; i < CATEGORY_ORDER.length; i++) {
                if (name.toLowerCase().includes(CATEGORY_ORDER[i].toLowerCase().split(' ')[0])) return i;
            }
            return 99;
        };
        return getIdx(a) - getIdx(b);
    });

    let html = '';

    for (const catName of sortedCats) {
        const catQuestions = grouped[catName];
        let displayHeader = catName;
        if (catName.toLowerCase().includes('mcq')) displayHeader = 'Section 1 — Multiple Choice Questions (MCQs)';
        else if (catName.toLowerCase().includes('basic')) displayHeader = 'Section 2 — Basic Technical Fundamentals';
        else if (catName.toLowerCase().includes('mern') || catName.toLowerCase().includes('mid')) displayHeader = 'Section 3 — Mid Technical (MERN Stack)';
        else if (catName.toLowerCase().includes('skill')) displayHeader = 'Section 4 — Resume Skills Deep-Dive';
        else if (catName.toLowerCase().includes('project')) displayHeader = 'Section 5 — Project Architecture & Execution';
        else if (catName.toLowerCase().includes('scenario') || catName.toLowerCase().includes('vlookup')) displayHeader = 'Section 6 — VlookUp Scenarios (UK Property Management)';

        html += `<div class="category-group-wrapper">`;
        html += `
            <div class="category-group-header">
                <span class="category-group-title">${escapeHtml(displayHeader)}</span>
                <span class="category-group-count">${catQuestions.length} Questions</span>
            </div>
        `;

        for (const q of catQuestions) {
            const numStr = q.number < 10 ? `Q0${q.number}` : `Q${q.number}`;
            const catTagClass = getCategoryClass(q.category);
            const isCollapsed = allCollapsed ? 'collapsed' : '';
            const isHrMode = currentViewMode === 'hr';

            // Options HTML for MCQs
            let optionsHtml = '';
            if (q.options && q.options.length > 0) {
                optionsHtml += `<div class="mcq-options-container">`;
                for (const opt of q.options) {
                    const optTrim = opt.trim();
                    const isOptionCorrect = q.correct_option && optTrim.toUpperCase().startsWith(q.correct_option.toUpperCase());
                    const correctClass = isOptionCorrect ? 'is-correct' : '';
                    optionsHtml += `
                        <div class="mcq-opt-pill ${correctClass}">
                            <span>${escapeHtml(opt)}</span>
                        </div>
                    `;
                }
                optionsHtml += `</div>`;
            }

            // Answer Content based on active View Mode
            let answerHeader = 'Expected Technical Answer & Architecture Key';
            let answerContent = q.answer;
            let calloutClass = '';

            if (isHrMode) {
                answerHeader = 'What to Look For (Plain-English HR Evaluation Guide)';
                answerContent = q.hr_answer || q.answer;
                calloutClass = 'hr-mode';
            }

            let correctBadgeHtml = '';
            if (q.correct_option) {
                correctBadgeHtml = `
                    <div class="mcq-key-badge">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                        <span>Correct Option: ${escapeHtml(q.correct_option)}</span>
                    </div>
                `;
            }

            html += `
                <div class="q-card ${isCollapsed}" data-num="${q.number}">
                    <div class="q-header" onclick="toggleQuestionCard(${q.number})">
                        <div class="q-meta-row">
                            <div class="q-meta-left">
                                <span class="q-num-pill">${numStr}</span>
                                <span class="q-cat-tag ${catTagClass}">${escapeHtml(q.category)}</span>
                            </div>
                            <div class="q-actions" onclick="event.stopPropagation()">
                                <button type="button" class="card-action-btn" onclick="copyQuestionCard(${q.number}, this)" title="Copy question & answer">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                                    </svg>
                                    <span>Copy</span>
                                </button>
                                <button type="button" class="card-action-btn" onclick="toggleQuestionCard(${q.number})" title="Toggle Answer">
                                    <svg class="chevron-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <polyline points="6 9 12 15 18 9"/>
                                    </svg>
                                </button>
                            </div>
                        </div>
                        <h4 class="q-title">${escapeHtml(q.question)}</h4>
                        ${optionsHtml}
                    </div>

                    <div class="q-answer-container">
                        <div class="q-answer-callout ${calloutClass}">
                            ${correctBadgeHtml}
                            <div class="answer-header">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
                                </svg>
                                <span>${escapeHtml(answerHeader)}</span>
                            </div>
                            <div class="answer-text">${escapeHtml(answerContent)}</div>
                        </div>
                    </div>
                </div>
            `;
        }

        html += `</div>`;
    }

    resultQuestions.innerHTML = html;
}

// ==========================================================================
// View Mode Switcher (Technical Key vs HR Guide)
// ==========================================================================

if (viewModeTechBtn) {
    viewModeTechBtn.addEventListener('click', () => {
        currentViewMode = 'technical';
        viewModeTechBtn.classList.add('active');
        if (viewModeHrBtn) viewModeHrBtn.classList.remove('active');
        renderFilteredQuestions();
        showToast('Switched to Technical Key Answer View');
    });
}

if (viewModeHrBtn) {
    viewModeHrBtn.addEventListener('click', () => {
        currentViewMode = 'hr';
        viewModeHrBtn.classList.add('active');
        if (viewModeTechBtn) viewModeTechBtn.classList.remove('active');
        renderFilteredQuestions();
        showToast('Switched to Plain-English HR Evaluation Guide View');
    });
}

// ==========================================================================
// Category Tabs & Search
// ==========================================================================

if (categoryTabs) {
    categoryTabs.addEventListener('click', (e) => {
        const btn = e.target.closest('.tab-btn');
        if (!btn) return;

        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        activeCategory = btn.getAttribute('data-cat') || 'all';
        renderFilteredQuestions();
    });
}

if (questionSearchInput) {
    questionSearchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value;
        if (searchClearBtn) {
            if (searchQuery.length > 0) {
                searchClearBtn.classList.remove('hidden');
            } else {
                searchClearBtn.classList.add('hidden');
            }
        }
        renderFilteredQuestions();
    });
}

if (searchClearBtn) {
    searchClearBtn.addEventListener('click', () => {
        questionSearchInput.value = '';
        searchQuery = '';
        searchClearBtn.classList.add('hidden');
        renderFilteredQuestions();
    });
}

// ==========================================================================
// Accordion & Copy Controls
// ==========================================================================

window.toggleQuestionCard = function(number) {
    const card = document.querySelector(`.q-card[data-num="${number}"]`);
    if (card) {
        card.classList.toggle('collapsed');
    }
};

if (toggleAnswersBtn) {
    toggleAnswersBtn.addEventListener('click', () => {
        allCollapsed = !allCollapsed;
        const cards = document.querySelectorAll('.q-card');
        cards.forEach(card => {
            if (allCollapsed) {
                card.classList.add('collapsed');
            } else {
                card.classList.remove('collapsed');
            }
        });
        if (toggleAnswersText) {
            toggleAnswersText.textContent = allCollapsed ? 'Expand' : 'Collapse';
        }
    });
}

window.copyQuestionCard = function(number, btnEl) {
    if (!lastResult || !lastResult.questions) return;
    const item = lastResult.questions.find(q => q.number === number);
    if (!item) return;

    let copyText = `Question ${item.number} [${item.category}]:\n${item.question}\n`;
    if (item.options && item.options.length > 0) {
        copyText += `Options:\n` + item.options.map(o => `  ${o}`).join('\n') + `\n`;
    }
    if (item.correct_option) {
        copyText += `Correct Option: ${item.correct_option}\n`;
    }
    copyText += `\nTechnical Answer:\n${item.answer}\n`;
    if (item.hr_answer) {
        copyText += `\nHR Plain-English Guide:\n${item.hr_answer}\n`;
    }

    navigator.clipboard.writeText(copyText).then(() => {
        const origHtml = btnEl.innerHTML;
        btnEl.classList.add('copied');
        btnEl.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
            <span>Copied</span>
        `;
        showToast(`Copied Q${item.number} to clipboard`);
        setTimeout(() => {
            btnEl.classList.remove('copied');
            btnEl.innerHTML = origHtml;
        }, 1800);
    }).catch(() => {
        showToast('Unable to copy to clipboard.');
    });
};

if (copyAllBtn) {
    copyAllBtn.addEventListener('click', () => {
        if (!lastResult || !lastResult.questions) return;

        let text = `VLOOKUP BUSINESS SOLUTIONS - TALENT EVALUATION KIT\n`;
        text += `Candidate: ${lastResult.candidate_name}\n`;
        text += `Summary: ${lastResult.summary}\n\n`;
        text += `====================================================\n\n`;

        lastResult.questions.forEach(q => {
            text += `[${q.category.toUpperCase()}] Q${q.number}:\n${q.question}\n`;
            if (q.options && q.options.length > 0) {
                text += `Options:\n` + q.options.map(o => `  ${o}`).join('\n') + `\n`;
            }
            if (q.correct_option) {
                text += `Correct Option: ${q.correct_option}\n`;
            }
            text += `Technical Answer:\n${q.answer}\n`;
            if (q.hr_answer) {
                text += `HR Guide:\n${q.hr_answer}\n`;
            }
            text += `----------------------------------------------------\n\n`;
        });

        navigator.clipboard.writeText(text).then(() => {
            showToast('All 20 Questions, MCQs, & Answers copied to clipboard!');
        }).catch(() => {
            showToast('Unable to copy text.');
        });
    });
}

// ==========================================================================
// 3 Role-Tailored DOCX Downloads
// ==========================================================================

async function downloadDocument(role, btnElement, defaultLabel) {
    if (!lastResult) return;

    try {
        btnElement.disabled = true;
        const originalContent = btnElement.innerHTML;
        btnElement.innerHTML = `
            <svg class="loading-spinner" width="14" height="14" viewBox="0 0 24 24" style="margin-right: 4px; display:inline-block;"></svg>
            Downloading...
        `;

        const response = await fetch(`/api/download/docx?role=${encodeURIComponent(role)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(lastResult),
        });

        if (!response.ok) {
            throw new Error('Failed to generate DOCX document.');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        const rolePrefix = {
            interviewer: 'Interviewer_Technical_Guide',
            hr: 'HR_Recruiter_Guide',
            candidate: 'Candidate_Assessment_Sheet'
        }[role] || 'Interview_Prep';

        const safeName = (lastResult.candidate_name || 'Candidate').replace(/[^a-zA-Z0-9_-]/g, '_');
        a.download = `VlookUp_${rolePrefix}_${safeName}.docx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showToast(`Downloaded ${defaultLabel}!`);
    } catch (err) {
        alert(err.message || 'Failed to download document.');
    } finally {
        btnElement.disabled = false;
        btnElement.innerHTML = defaultLabel;
    }
}

if (downloadInterviewerBtn) {
    downloadInterviewerBtn.addEventListener('click', () => {
        downloadDocument('interviewer', downloadInterviewerBtn, `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            <span>Download for Interviewer</span>
        `);
    });
}

if (downloadHrBtn) {
    downloadHrBtn.addEventListener('click', () => {
        downloadDocument('hr', downloadHrBtn, `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            <span>Download for HR</span>
        `);
    });
}

if (downloadCandidateBtn) {
    downloadCandidateBtn.addEventListener('click', () => {
        downloadDocument('candidate', downloadCandidateBtn, `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            <span>Download for Candidate</span>
        `);
    });
}

if (generateAgainBtn) {
    generateAgainBtn.addEventListener('click', () => {
        resultSection.classList.add('hidden');
        uploadSection.classList.remove('hidden');
        uploadArea.classList.remove('hidden');
        fileInfo.classList.add('hidden');
        if (heroBanner) heroBanner.classList.remove('hidden');

        selectedFile = null;
        fileInput.value = '';
        cameraInput.value = '';
        lastResult = null;
        activeCategory = 'all';
        searchQuery = '';
        currentViewMode = 'technical';
        if (questionSearchInput) questionSearchInput.value = '';
        if (searchClearBtn) searchClearBtn.classList.add('hidden');
        if (generateBtn) generateBtn.disabled = false;
        hideError();

        if (stepperProgressFill) stepperProgressFill.style.width = '0%';
        [stepUpload, stepExtract, stepGenerate, stepFormat].forEach(el => {
            if (el) el.className = 'step-item';
        });

        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        const allTab = document.querySelector('.tab-btn[data-cat="all"]');
        if (allTab) allTab.classList.add('active');

        if (viewModeTechBtn) viewModeTechBtn.classList.add('active');
        if (viewModeHrBtn) viewModeHrBtn.classList.remove('active');

        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

if (printBtn) {
    printBtn.addEventListener('click', () => {
        window.print();
    });
}
