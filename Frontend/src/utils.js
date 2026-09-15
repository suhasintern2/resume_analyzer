export const ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png'];

export const MAX_SIZE_BYTES = 4 * 1024 * 1024;

export const CATEGORY_ORDER = [
  'MCQ',
  'Basic Technical',
  'Mid Technical (MERN)',
  'Resume Skills',
  'Project',
  'VlookUp Scenario',
];

export function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export function getInitials(name) {
  if (!name) return 'CD';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function validateFile(file) {
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  const type = (file.type || '').toLowerCase();

  let valid = ALLOWED_EXTENSIONS.includes(ext);
  if (!valid && (type === 'image/jpeg' || type === 'image/png' || type === 'application/pdf')) {
    valid = true;
  }

  if (!valid) {
    return 'Please upload a PDF document or a clear JPG/PNG image.';
  }

  if (file.size > MAX_SIZE_BYTES) {
    return `The file size (${formatBytes(file.size)}) exceeds the maximum allowed limit of 4 MB.`;
  }

  return '';
}

export function normalizeFileName(file) {
  const type = (file.type || '').toLowerCase();
  if (!file.name || !file.name.includes('.')) {
    if (type === 'image/png') return 'camera_capture.png';
    if (type === 'image/jpeg' || type === 'image/jpg') return 'camera_capture.jpg';
    return 'scanned_resume.pdf';
  }
  return file.name;
}

export function getCategoryClass(catName) {
  const norm = (catName || '').toLowerCase();
  if (norm.includes('mcq')) return 'tag-mcq';
  if (norm.includes('basic') || norm.includes('tech')) return 'tag-basic-technical';
  if (norm.includes('mern') || norm.includes('mid')) return 'tag-mid-technical';
  if (norm.includes('skill')) return 'tag-resume-skills';
  if (norm.includes('project')) return 'tag-project';
  if (norm.includes('scenario') || norm.includes('vlookup')) return 'tag-vlookup-scenario';
  return 'tag-basic-technical';
}

export function categoryCounts(questions) {
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
  return counts;
}

export function matchCategory(qCategory, targetFilter) {
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

export function filterQuestions(questions, activeCategory, searchQuery) {
  let filtered = questions.filter((q) => matchCategory(q.category, activeCategory));

  const query = searchQuery.trim().toLowerCase();
  if (query) {
    filtered = filtered.filter((q) => {
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
  }

  return filtered;
}

export function getDisplayHeader(catName) {
  const lower = catName.toLowerCase();
  if (lower.includes('mcq')) return 'Section 1 — Multiple Choice Questions (MCQs)';
  if (lower.includes('basic')) return 'Section 2 — Basic Technical Fundamentals';
  if (lower.includes('mern') || lower.includes('mid')) return 'Section 3 — Mid Technical (MERN Stack)';
  if (lower.includes('skill')) return 'Section 4 — Resume Skills Deep-Dive';
  if (lower.includes('project')) return 'Section 5 — Project Architecture & Execution';
  if (lower.includes('scenario') || lower.includes('vlookup')) return 'Section 6 — VlookUp Scenarios (UK Property Management)';
  return catName;
}

export function groupQuestionsByCategory(questions) {
  const grouped = {};
  for (const q of questions) {
    const cat = q.category || 'General';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(q);
  }

  const sortedCats = Object.keys(grouped).sort((a, b) => {
    const getIdx = (name) => {
      for (let i = 0; i < CATEGORY_ORDER.length; i++) {
        if (name.toLowerCase().includes(CATEGORY_ORDER[i].toLowerCase().split(' ')[0])) return i;
      }
      return 99;
    };
    return getIdx(a) - getIdx(b);
  });

  return sortedCats.map((catName) => ({ category: catName, questions: grouped[catName] }));
}