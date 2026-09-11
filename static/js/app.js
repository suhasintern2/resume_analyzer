const ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png'];
const MAX_SIZE_MB = 4;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

const fileInput = document.getElementById('file-input');
const chooseBtn = document.getElementById('choose-btn');
const uploadArea = document.getElementById('upload-area');
const fileInfo = document.getElementById('file-info');
const fileName = document.getElementById('file-name');
const generateBtn = document.getElementById('generate-btn');
const changeFileBtn = document.getElementById('change-file-btn');
const errorMessage = document.getElementById('error-message');
const uploadSection = document.getElementById('upload-section');
const loadingSection = document.getElementById('loading-section');
const resultSection = document.getElementById('result-section');
const resultName = document.getElementById('result-name');
const resultSummary = document.getElementById('result-summary');
const resultQuestions = document.getElementById('result-questions');
const generateAgainBtn = document.getElementById('generate-again-btn');
const downloadDocxBtn = document.getElementById('download-docx-btn');
const printBtn = document.getElementById('print-btn');

let selectedFile = null;
let lastResult = null;

function showError(msg) {
    errorMessage.textContent = msg;
    errorMessage.classList.remove('hidden');
}

function hideError() {
    errorMessage.classList.add('hidden');
}

function validateFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
        showError('Please upload a PDF, JPG, JPEG, or PNG file.');
        return false;
    }
    if (file.size > MAX_SIZE_BYTES) {
        showError(`The file is too large. Maximum allowed size is ${MAX_SIZE_MB} MB.`);
        return false;
    }
    return true;
}

chooseBtn.addEventListener('click', () => fileInput.click());
uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#4a6cf7';
    uploadArea.style.background = '#f8f9ff';
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.style.borderColor = '#d0d7de';
    uploadArea.style.background = '';
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#d0d7de';
    uploadArea.style.background = '';
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelect(files[0]);
    }
});

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        handleFileSelect(fileInput.files[0]);
    }
});

function handleFileSelect(file) {
    hideError();
    if (!validateFile(file)) return;
    selectedFile = file;
    fileName.textContent = file.name;
    uploadArea.classList.add('hidden');
    fileInfo.classList.remove('hidden');
}

changeFileBtn.addEventListener('click', () => {
    selectedFile = null;
    fileInput.value = '';
    fileInfo.classList.add('hidden');
    uploadArea.classList.remove('hidden');
    hideError();
});

generateBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    hideError();
    generateBtn.disabled = true;
    uploadSection.classList.add('hidden');
    loadingSection.classList.remove('hidden');
    resultSection.classList.add('hidden');

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

        lastResult = data.result;
        renderResults(data.result);
    } catch (err) {
        loadingSection.classList.add('hidden');
        uploadSection.classList.remove('hidden');
        fileInfo.classList.remove('hidden');
        uploadArea.classList.add('hidden');
        generateBtn.disabled = false;
        showError(err.message || 'Something went wrong while processing the resume. Please try again.');
    }
});

function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

function renderResults(result) {
    loadingSection.classList.add('hidden');
    resultSection.classList.remove('hidden');

    resultName.textContent = escapeHtml(result.candidate_name);
    resultSummary.textContent = escapeHtml(result.summary);

    const CATEGORY_ORDER = [
        'Basic Technical', 'Resume Skills', 'Project', 'Experience', 'DSA'
    ];

    const categories = {};
    for (const q of result.questions) {
        const cat = q.category;
        if (!categories[cat]) categories[cat] = [];
        categories[cat].push(q);
    }

    const orderedCats = Object.entries(categories).sort((a, b) => {
        const ia = CATEGORY_ORDER.indexOf(a[0]);
        const ib = CATEGORY_ORDER.indexOf(b[0]);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });

    let html = '';
    for (const [catName, questions] of orderedCats) {
        html += `<div class="category-section">`;
        html += `<h3 class="category-title">${escapeHtml(catName.toUpperCase())} QUESTIONS</h3>`;
        for (const q of questions) {
            html += `
                <div class="question-block">
                    <div class="question-text">${q.number}. ${escapeHtml(q.question)}</div>
                    <div class="answer-label">Answer:</div>
                    <div class="answer-text">${escapeHtml(q.answer)}</div>
                </div>
            `;
        }
        html += `</div>`;
    }

    resultQuestions.innerHTML = html;
}

generateAgainBtn.addEventListener('click', () => {
    resultSection.classList.add('hidden');
    uploadSection.classList.remove('hidden');
    uploadArea.classList.remove('hidden');
    fileInfo.classList.add('hidden');
    selectedFile = null;
    fileInput.value = '';
    lastResult = null;
    generateBtn.disabled = false;
});

downloadDocxBtn.addEventListener('click', async () => {
    if (!lastResult) return;

    try {
        downloadDocxBtn.disabled = true;
        downloadDocxBtn.textContent = 'Generating...';

        const response = await fetch('/api/download/docx', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(lastResult),
        });

        if (!response.ok) {
            throw new Error('Failed to download document.');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `interview_prep_${lastResult.candidate_name.replace(/\s+/g, '_')}.docx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (err) {
        alert(err.message || 'Failed to download document.');
    } finally {
        downloadDocxBtn.disabled = false;
        downloadDocxBtn.textContent = 'Download DOCX';
    }
});

printBtn.addEventListener('click', () => {
    window.print();
});
