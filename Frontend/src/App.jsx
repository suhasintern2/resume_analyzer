import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import UploadSection from './components/UploadSection';
import LoadingSection from './components/LoadingSection';
import CandidateProfile from './components/CandidateProfile';
import Toolbar from './components/Toolbar';
import QuestionsList from './components/QuestionsList';
import ExportBar from './components/ExportBar';
import Footer from './components/Footer';
import Toast from './components/Toast';
import DashboardPage from './components/DashboardPage';
import MCQBank from './components/MCQBank';
import { generateInterviewQA, downloadDocx } from './services/api';
import { categoryCounts, filterQuestions, normalizeFileName, validateFile } from './utils';

function App() {
  // ---------- page phase ----------
  // 'upload' | 'loading' | 'result' | 'dashboard' | 'mcq'
  const [phase, setPhase] = useState('upload');

  // ---------- upload ----------
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState('');

  // ---------- result ----------
  const [lastResult, setLastResult] = useState(null);
  const [lastInterviewId, setLastInterviewId] = useState(null);

  // ---------- filters ----------
  const [activeCategory, setActiveCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // ---------- toolbar ----------
  const [allCollapsed, setAllCollapsed] = useState(false);
  const [viewMode, setViewMode] = useState('technical');

  // ---------- stepper ----------
  const [stepStage, setStepStage] = useState(0);
  const [stepDone, setStepDone] = useState(false);
  const stepIntervalRef = useRef(null);

  // ---------- download ----------
  const [downloadingRole, setDownloadingRole] = useState(null);

  // ---------- toast ----------
  const [toast, setToast] = useState({ message: '', visible: false });
  const toastTimerRef = useRef(null);

  const showToast = useCallback((message) => {
    clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(
      () => setToast((t) => ({ ...t, visible: false })),
      2400,
    );
    setToast({ message, visible: true });
  }, []);

  useEffect(() => () => clearTimeout(toastTimerRef.current), []);

  // ---------- stepper helpers ----------
  const clearStepInterval = useCallback(() => {
    if (stepIntervalRef.current) {
      clearInterval(stepIntervalRef.current);
      stepIntervalRef.current = null;
    }
  }, []);

  const startStepper = useCallback(() => {
    clearStepInterval();
    setStepStage(1);
    setStepDone(false);
    stepIntervalRef.current = setInterval(() => {
      setStepStage((s) => (s < 4 ? s + 1 : 4));
    }, 2800);
  }, [clearStepInterval]);

  // ---------- navigation ----------
  const handleGoToDashboard = useCallback(() => {
    setPhase('dashboard');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const handleGoHome = useCallback(() => {
    setPhase('upload');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const handleGoToMCQ = useCallback(() => {
    setPhase('mcq');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  // ---------- derived ----------
  const filteredQuestions = useMemo(() => {
    if (!lastResult || !lastResult.questions) return [];
    return filterQuestions(lastResult.questions, activeCategory, searchQuery);
  }, [lastResult, activeCategory, searchQuery]);

  const counts = useMemo(
    () => categoryCounts(lastResult?.questions || []),
    [lastResult],
  );

  const searchMatchCountText = useMemo(() => {
    if (!searchQuery.trim()) return '';
    return `${filteredQuestions.length} found`;
  }, [searchQuery, filteredQuestions.length]);

  const heroHidden = phase === 'result' || phase === 'dashboard';

  // ---------- handlers ----------
  const handleFileSelect = useCallback((file) => {
    setError('');
    const validationErr = validateFile(file);
    if (validationErr) {
      setError(validationErr);
      return;
    }
    const normalizedName = normalizeFileName(file);
    setSelectedFile(new File([file], normalizedName, { type: file.type }));
  }, []);

  const handleClearFile = useCallback(() => {
    setSelectedFile(null);
    setError('');
  }, []);

  const handleGenerate = useCallback(async () => {
    if (!selectedFile) return;
    setError('');
    setPhase('loading');
    startStepper();
    try {
      const { result, interview_id } = await (async () => {
        const formData = new FormData();
        formData.append('file', selectedFile);
        const response = await fetch('/api/generate', { method: 'POST', body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Failed to generate interview questions.');
        if (!data.success || !data.result) throw new Error(data.error || 'Failed to generate interview questions.');
        return { result: data.result, interview_id: data.interview_id ?? null };
      })();
      clearStepInterval();
      setStepStage(4);
      setStepDone(true);
      setLastResult(result);
      setLastInterviewId(interview_id);
      setPhase('result');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      clearStepInterval();
      setPhase('upload');
      setError(
        err.message ||
          'Something went wrong while processing the resume. Please try again.',
      );
    }
  }, [selectedFile, startStepper, clearStepInterval]);

  const handleGenerateAgain = useCallback(() => {
    setPhase('upload');
    setSelectedFile(null);
    setLastResult(null);
    setLastInterviewId(null);
    setActiveCategory('all');
    setSearchQuery('');
    setViewMode('technical');
    setAllCollapsed(false);
    setStepStage(0);
    setStepDone(false);
    setError('');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const handleCopyAll = useCallback(() => {
    if (!lastResult || !lastResult.questions) return;

    let text = 'VLOOKUP BUSINESS SOLUTIONS - TALENT EVALUATION KIT\n';
    text += `Candidate: ${lastResult.candidate_name}\n`;
    text += `Summary: ${lastResult.summary}\n\n`;
    text += '====================================================\n\n';

    lastResult.questions.forEach((q) => {
      text += `[${q.category.toUpperCase()}] Q${q.number}:\n${q.question}\n`;
      if (q.options && q.options.length > 0) {
        text += 'Options:\n' + q.options.map((o) => `  ${o}`).join('\n') + '\n';
      }
      if (q.correct_option) {
        text += `Correct Option: ${q.correct_option}\n`;
      }
      text += `Technical Answer:\n${q.answer}\n`;
      if (q.hr_answer) {
        text += `HR Guide:\n${q.hr_answer}\n`;
      }
      text += '----------------------------------------------------\n\n';
    });

    navigator.clipboard
      .writeText(text)
      .then(() => showToast('All 20 Questions, MCQs, & Answers copied to clipboard!'))
      .catch(() => showToast('Unable to copy text.'));
  }, [lastResult, showToast]);

  const handleDownload = useCallback(
    async (role) => {
      if (!lastResult) return;
      setDownloadingRole(role);
      try {
        const blob = await downloadDocx(lastResult, role);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        const rolePrefix = {
          interviewer: 'Interviewer_Technical_Guide',
          hr: 'HR_Recruiter_Guide',
          candidate: 'Candidate_Assessment_Sheet',
        }[role] || 'Interview_Prep';

        const safeName = (lastResult.candidate_name || 'Candidate').replace(
          /[^a-zA-Z0-9_-]/g,
          '_',
        );
        a.download = `VlookUp_${rolePrefix}_${safeName}.docx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        const labels = {
          interviewer: 'Download for Interviewer',
          hr: 'Download for HR',
          candidate: 'Download for Candidate',
        };
        showToast(`Downloaded ${labels[role] || 'document'}!`);
      } catch (err) {
        alert(err.message || 'Failed to download document.');
      } finally {
        setDownloadingRole(null);
      }
    },
    [lastResult, showToast],
  );

  // ---------- render ----------

  // MCQ Bank gets its own full-page layout (Header + MCQBank + Footer)
  if (phase === 'mcq') {
    return (
      <>
        <Header
          onDashboard={handleGoToDashboard}
          onHome={handleGoHome}
          activePage="mcq"
        />
        <div className="app-layout">
          <main className="main-content">
            <MCQBank onToast={showToast} onBack={handleGoHome} />
          </main>
          <Footer />
        </div>
        <Toast message={toast.message} visible={toast.visible} />
      </>
    );
  }

  // Dashboard gets its own full-page layout (Header + DashboardPage + Footer)
  if (phase === 'dashboard') {
    return (
      <>
        <Header
          onDashboard={handleGoToDashboard}
          onHome={handleGoHome}
          activePage="dashboard"
        />
        <div className="app-layout">
          <main className="main-content">
            <DashboardPage onBack={handleGoHome} />
          </main>
          <Footer />
        </div>
      </>
    );
  }

  return (
    <>
      <Header
        onDashboard={handleGoToDashboard}
        onHome={handleGoHome}
        activePage="home"
      />

      <div className="app-layout">
        <Hero hidden={heroHidden} />

        <main className="main-content">
          <UploadSection
            hidden={phase !== 'upload'}
            selectedFile={selectedFile}
            onFileSelect={handleFileSelect}
            onClearFile={handleClearFile}
            onGenerate={handleGenerate}
            generateDisabled={phase === 'loading'}
            error={error}
            onGoToMCQ={handleGoToMCQ}
          />

          <LoadingSection
            hidden={phase !== 'loading'}
            stepStage={stepStage}
            stepDone={stepDone}
          />

          <section
            id="result-section"
            className={phase === 'result' ? 'result-container' : 'result-container hidden'}
          >
            {lastResult && (
              <>
                <CandidateProfile
                  candidateName={lastResult.candidate_name}
                  summary={lastResult.summary}
                  totalQuestions={lastResult.questions?.length ?? 0}
                  categoryCount={
                    new Set((lastResult.questions || []).map((q) => q.category)).size || 6
                  }
                  interviewId={lastInterviewId}
                />

                <Toolbar
                  counts={counts}
                  activeCategory={activeCategory}
                  onCategoryChange={setActiveCategory}
                  searchQuery={searchQuery}
                  onSearchChange={setSearchQuery}
                  onClearSearch={() => setSearchQuery('')}
                  allCollapsed={allCollapsed}
                  onToggleAnswers={() => setAllCollapsed((v) => !v)}
                  viewMode={viewMode}
                  onViewModeChange={setViewMode}
                  onCopyAll={handleCopyAll}
                  searchMatchCountText={searchMatchCountText}
                />

                <QuestionsList
                  questions={filteredQuestions}
                  allCollapsed={allCollapsed}
                  viewMode={viewMode}
                  onToast={showToast}
                />

                <ExportBar
                  onGenerateAgain={handleGenerateAgain}
                  onPrint={() => window.print()}
                  onDownload={handleDownload}
                  downloadingRole={downloadingRole}
                  interviewId={lastInterviewId}
                  onGoToDashboard={lastInterviewId ? handleGoToDashboard : null}
                />
              </>
            )}
          </section>
        </main>

        <Footer />
      </div>

      <Toast message={toast.message} visible={toast.visible} />
    </>
  );
}

export default App;
