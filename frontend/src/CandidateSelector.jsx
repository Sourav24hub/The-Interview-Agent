import React, { useState } from 'react';
import { User, Award, Calendar, CheckCircle, AlertTriangle, ArrowRight, Search, Code, Cpu } from 'lucide-react';

export function CandidateSelector({ candidates, onSelectCandidate }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterTag, setFilterTag] = useState('ALL');
  const [customId, setCustomId] = useState('');

  const filteredCandidates = candidates.filter((cand) => {
    const nameMatch = cand.member.name.toLowerCase().includes(searchTerm.toLowerCase());
    const roleMatch = cand.member.jobRole.toLowerCase().includes(searchTerm.toLowerCase());
    const idMatch = cand.member.id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSearch = nameMatch || roleMatch || idMatch;

    if (!matchesSearch) return false;

    if (filterTag === 'FIRST_TRY') {
      return cand.signals.missionsFirstTry >= 15;
    }
    if (filterTag === 'STRUGGLE') {
      return cand.missions.some((m) => (m.attempts || 0) >= 3 && m.passed);
    }
    if (filterTag === 'SKIPPED') {
      return cand.missions.some((m) => m.skipped || m.passed === false);
    }
    return true;
  });

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    if (!customId.trim()) return;
    const found = candidates.find((c) => c.member.id.toUpperCase() === customId.trim().toUpperCase());
    if (found) {
      onSelectCandidate(found);
    } else {
      onSelectCandidate({
        member: {
          id: customId.trim().toUpperCase(),
          name: `Candidate ${customId.trim().toUpperCase()}`,
          jobRole: "AI Software Engineer",
          yearsExperience: 3,
          education: "B.S. Computer Science",
          status: "COMPLETED"
        },
        missions: [
          { day: 7, title: "Embeddings Explained", passed: true, attempts: 1 },
          { day: 10, title: "Retrieval & Matching Engine", passed: true, attempts: 4 },
          { day: 28, title: "Docker & Kubernetes Deployment", skipped: true }
        ],
        signals: { commitDays: 25, missionsCompleted: 28, missionsFirstTry: 14 }
      });
    }
  };

  return (
    <div style={{ maxWidth: '1240px', margin: '0 auto', padding: '36px 24px' }}>
      {/* Header Banner */}
      <div style={{ textAlign: 'center', marginBottom: '40px' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }} className="badge badge-cyan">
          <Cpu size={14} />
          <span>AI INTERVIEW AGENT — COHORT DEBRIEF</span>
        </div>
        <h1 style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '12px', color: 'var(--text-main)' }}>
          Select Candidate to <span className="glow-text-cyan">Debrief</span>
        </h1>
        <p style={{ color: 'var(--text-muted)', maxWidth: '680px', margin: '0 auto', fontSize: '1.02rem', lineHeight: '1.6' }}>
          Select a candidate profile from the AI Cohort ({candidates.length} profiles loaded) to start an adaptive technical interview driven by Groq LLM.
        </p>
      </div>

      {/* Filter & Search Bar */}
      <div className="glass-card" style={{ padding: '18px 24px', marginBottom: '32px', display: 'flex', flexWrap: 'wrap', gap: '16px', justifyContent: 'space-between', alignItems: 'center' }}>
        {/* Search */}
        <div style={{ position: 'relative', minWidth: '300px', flex: '1' }}>
          <Search size={18} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
          <input
            type="text"
            placeholder="Search name, job role, or ID (e.g. CAND-001, CAND-007)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              background: '#ffffff',
              border: '1px solid #cbd5e1',
              borderRadius: '10px',
              padding: '10px 14px 10px 42px',
              color: 'var(--text-main)',
              fontSize: '0.92rem',
              outline: 'none'
            }}
          />
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            onClick={() => setFilterTag('ALL')}
            className={`btn-secondary ${filterTag === 'ALL' ? 'badge-cyan' : ''}`}
            style={{ fontSize: '0.85rem', padding: '6px 14px' }}
          >
            All Candidates ({candidates.length})
          </button>
          <button
            onClick={() => setFilterTag('FIRST_TRY')}
            className={`btn-secondary ${filterTag === 'FIRST_TRY' ? 'badge-green' : ''}`}
            style={{ fontSize: '0.85rem', padding: '6px 14px' }}
          >
            High First-Try Rate
          </button>
          <button
            onClick={() => setFilterTag('STRUGGLE')}
            className={`btn-secondary ${filterTag === 'STRUGGLE' ? 'badge-amber' : ''}`}
            style={{ fontSize: '0.85rem', padding: '6px 14px' }}
          >
            High Attempts (3x+)
          </button>
          <button
            onClick={() => setFilterTag('SKIPPED')}
            className={`btn-secondary ${filterTag === 'SKIPPED' ? 'badge-rose' : ''}`}
            style={{ fontSize: '0.85rem', padding: '6px 14px' }}
          >
            Skipped / Incomplete
          </button>
        </div>
      </div>

      {/* Candidates Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '24px', marginBottom: '48px' }}>
        {filteredCandidates.map((cand) => {
          const struggleCount = cand.missions.filter((m) => (m.attempts || 0) >= 3 && m.passed).length;
          const skippedCount = cand.missions.filter((m) => m.skipped || m.passed === false).length;

          return (
            <div key={cand.member.id} className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                {/* Header info */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                      width: '46px',
                      height: '46px',
                      borderRadius: '12px',
                      background: 'linear-gradient(135deg, #e0f2fe, #f3e8ff)',
                      border: '1px solid #7dd3fc',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      color: 'var(--accent-indigo)',
                      fontSize: '1rem'
                    }}>
                      {cand.member.name.split(' ').map(n => n[0]).join('')}
                    </div>
                    <div>
                      <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)' }}>{cand.member.name}</h3>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{cand.member.jobRole}</div>
                    </div>
                  </div>
                  <span className="badge badge-cyan">{cand.member.id}</span>
                </div>

                {/* Signals metrics */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr 1fr',
                  gap: '8px',
                  background: '#f1f5f9',
                  border: '1px solid #e2e8f0',
                  padding: '12px',
                  borderRadius: '10px',
                  marginBottom: '16px',
                  textAlign: 'center'
                }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Completed</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-indigo)' }}>
                      {cand.signals.missionsCompleted}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>First-Try</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-green)' }}>
                      {cand.signals.missionsFirstTry}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Active Days</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-violet)' }}>
                      {cand.signals.commitDays}d
                    </div>
                  </div>
                </div>

                {/* Details & Tags */}
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '16px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Award size={14} color="var(--accent-indigo)" />
                    <span>{cand.member.yearsExperience} yrs exp • {cand.member.education}</span>
                  </div>
                </div>

                {/* Mission Status Pills */}
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '20px' }}>
                  <span className="badge badge-green">
                    <CheckCircle size={12} /> {cand.signals.missionsFirstTry} First-Try
                  </span>
                  {struggleCount > 0 && (
                    <span className="badge badge-amber">
                      <AlertTriangle size={12} /> {struggleCount} High-Attempt
                    </span>
                  )}
                  {skippedCount > 0 && (
                    <span className="badge badge-rose">
                      <AlertTriangle size={12} /> {skippedCount} Skipped/Incomplete
                    </span>
                  )}
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => onSelectCandidate(cand)}
                className="btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
              >
                <span>Start Technical Debrief</span>
                <ArrowRight size={16} />
              </button>
            </div>
          );
        })}
      </div>

      {/* Manual ID Input Footer */}
      <div className="glass-card" style={{ padding: '24px', textAlign: 'center', maxWidth: '600px', margin: '0 auto' }}>
        <h4 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '8px' }}>Or Enter a Custom Candidate ID</h4>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
          Test any candidate ID directly against our backend session engine.
        </p>
        <form onSubmit={handleCustomSubmit} style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
          <input
            type="text"
            placeholder="e.g. CAND-003, CAND-007"
            value={customId}
            onChange={(e) => setCustomId(e.target.value)}
            style={{
              background: '#ffffff',
              border: '1px solid #cbd5e1',
              borderRadius: '10px',
              padding: '10px 16px',
              color: 'var(--text-main)',
              fontSize: '0.9rem',
              outline: 'none',
              width: '220px'
            }}
          />
          <button type="submit" className="btn-secondary">
            <span>Launch Candidate</span>
            <ArrowRight size={14} />
          </button>
        </form>
      </div>
    </div>
  );
}
