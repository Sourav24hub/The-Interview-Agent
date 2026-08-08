import React, { useState } from 'react';
import { Award, CheckCircle2, AlertTriangle, Rocket, Download, Copy, RefreshCw, FileText, ChevronDown, ChevronUp, Check } from 'lucide-react';

export function FeedbackDashboard({ candidate, feedback, messages, onRestart }) {
  const [copied, setCopied] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);

  const handleCopySummary = () => {
    if (!feedback?.summary) return;
    navigator.clipboard.writeText(feedback.summary);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({ candidate, feedback, transcript: messages }, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `debrief_${candidate.member.id}_feedback.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div style={{ maxWidth: '1140px', margin: '0 auto', padding: '40px 24px' }}>
      {/* Header Banner */}
      <div style={{ textAlign: 'center', marginBottom: '40px' }}>
        <div className="badge badge-green" style={{ marginBottom: '12px', padding: '6px 14px', fontSize: '0.85rem' }}>
          <CheckCircle2 size={16} />
          <span>TECHNICAL DEBRIEF COMPLETED</span>
        </div>
        <h1 style={{ fontSize: '2.6rem', fontWeight: 800, marginBottom: '12px', color: 'var(--text-main)' }}>
          Evaluation Dashboard: <span className="glow-text-cyan">{candidate.member.name}</span>
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '1.02rem' }}>
          {candidate.member.jobRole} • {candidate.member.yearsExperience} Years Experience • {candidate.member.id}
        </p>
      </div>

      {/* Stats Quick Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '20px', marginBottom: '32px' }}>
        <div className="glass-card" style={{ padding: '20px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '4px' }}>Missions Completed</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-indigo)' }}>
            {candidate.signals.missionsCompleted} / 31
          </div>
        </div>

        <div className="glass-card" style={{ padding: '20px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '4px' }}>First-Try Pass Rate</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-green)' }}>
            {candidate.signals.missionsFirstTry} ({Math.round((candidate.signals.missionsFirstTry / candidate.signals.missionsCompleted) * 100)}%)
          </div>
        </div>

        <div className="glass-card" style={{ padding: '20px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '4px' }}>Active Commit Days</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-violet)' }}>
            {candidate.signals.commitDays} Days
          </div>
        </div>

        <div className="glass-card" style={{ padding: '20px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '4px' }}>Interview Turns Executed</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-amber)' }}>
            {messages.filter(m => m.role === 'candidate').length} Turns
          </div>
        </div>
      </div>

      {/* Executive Summary Card */}
      <div className="glass-card" style={{ padding: '28px', marginBottom: '32px', borderLeft: '5px solid var(--accent-indigo)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-main)' }}>
            <Award color="var(--accent-indigo)" size={22} />
            <span>Executive Evaluation Summary</span>
          </h3>
          <button onClick={handleCopySummary} className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
            {copied ? <Check size={14} color="var(--accent-green)" /> : <Copy size={14} />}
            <span>{copied ? 'Copied' : 'Copy Summary'}</span>
          </button>
        </div>

        <p style={{ fontSize: '1.05rem', lineHeight: '1.7', color: 'var(--text-main)' }}>
          {feedback?.summary || "Candidate completed the technical debrief session across targeted curriculum topics."}
        </p>
      </div>

      {/* 3 Grid Columns: Strengths, Gaps, Next Steps */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', marginBottom: '40px' }}>
        
        {/* Strengths Card */}
        <div className="glass-card" style={{ padding: '24px', borderColor: '#86efac' }}>
          <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-green)', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 size={18} />
            <span>Confirmed Strengths ({feedback?.strengths?.length || 0})</span>
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {feedback?.strengths?.map((str, idx) => (
              <div key={idx} style={{ display: 'flex', gap: '10px', fontSize: '0.92rem', lineHeight: '1.5', color: 'var(--text-main)' }}>
                <span style={{ color: 'var(--accent-green)', fontWeight: 700 }}>•</span>
                <span>{str}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Knowledge Gaps Card */}
        <div className="glass-card" style={{ padding: '24px', borderColor: '#fde68a' }}>
          <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-amber)', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={18} />
            <span>Identified Gaps & Friction ({feedback?.gaps?.length || 0})</span>
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {feedback?.gaps?.map((gap, idx) => (
              <div key={idx} style={{ display: 'flex', gap: '10px', fontSize: '0.92rem', lineHeight: '1.5', color: 'var(--text-main)' }}>
                <span style={{ color: 'var(--accent-amber)', fontWeight: 700 }}>•</span>
                <span>{gap}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Actionable Next Steps Card */}
        <div className="glass-card" style={{ padding: '24px', borderColor: '#7dd3fc' }}>
          <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-cyan)', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Rocket size={18} />
            <span>Actionable Next Steps ({feedback?.next?.length || 0})</span>
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {feedback?.next?.map((step, idx) => (
              <div key={idx} style={{ display: 'flex', gap: '10px', fontSize: '0.92rem', lineHeight: '1.5', color: 'var(--text-main)' }}>
                <span style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>•</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Collapsible Transcript Accordion */}
      <div className="glass-card" style={{ padding: '20px', marginBottom: '40px' }}>
        <button
          onClick={() => setShowTranscript(!showTranscript)}
          style={{
            width: '100%',
            background: 'none',
            border: 'none',
            color: 'var(--text-main)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
            fontSize: '1rem',
            fontWeight: 600
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <FileText size={18} color="var(--accent-indigo)" />
            <span>Full Session Transcript ({messages.length} messages)</span>
          </div>
          {showTranscript ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>

        {showTranscript && (
          <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '12px', borderTop: '1px solid #e2e8f0', paddingTop: '16px' }}>
            {messages.map((m, idx) => (
              <div key={idx} style={{
                background: m.role === 'interviewer' ? '#f0f9ff' : '#f5f3ff',
                border: m.role === 'interviewer' ? '1px solid #bae6fd' : '1px solid #ddd6fe',
                padding: '12px 16px',
                borderRadius: '8px',
                fontSize: '0.9rem',
                lineHeight: '1.5'
              }}>
                <div style={{ fontWeight: 600, color: m.role === 'interviewer' ? '#0284c7' : '#7c3aed', marginBottom: '4px' }}>
                  {m.role === 'interviewer' ? 'Senior Interviewer' : candidate.member.name}
                </div>
                <div style={{ color: 'var(--text-main)' }}>{m.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', flexWrap: 'wrap' }}>
        <button onClick={handleDownloadJSON} className="btn-secondary">
          <Download size={16} />
          <span>Export Feedback (JSON)</span>
        </button>

        <button onClick={onRestart} className="btn-primary">
          <RefreshCw size={16} />
          <span>Start Another Interview</span>
        </button>
      </div>
    </div>
  );
}
