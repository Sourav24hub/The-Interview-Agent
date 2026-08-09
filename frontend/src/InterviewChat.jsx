import React, { useState, useEffect, useRef } from 'react';
import { Send, User, Bot, ArrowLeft, Sparkles, Zap, Target } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export function InterviewChat({
  candidate,
  sessionId,
  messages,
  isThinking,
  turnCount,
  onSendMessage,
  onEndInterview,
  onBackToSelect
}) {
  const [inputText, setInputText] = useState('');
  const [mockLoading, setMockLoading] = useState(null); // tracks which button is loading
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isThinking]);

  // Auto-resize textarea whenever inputText changes
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 280)}px`;
  }, [inputText]);

  const handleSend = (e) => {
    e?.preventDefault();
    if (!inputText.trim() || isThinking) return;
    onSendMessage(inputText.trim());
    setInputText('');
    // Reset height after clearing
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Compute per-message question numbers (only for non-counter interviewer messages)
  const getInterviewerQuestionNumbers = () => {
    const nums = {};
    let qNum = 0;
    messages.forEach((msg, idx) => {
      if (msg.role === 'interviewer' && !msg.isCounter) {
        qNum++;
        nums[idx] = qNum;
      }
    });
    return nums;
  };
  const questionNumbers = getInterviewerQuestionNumbers();


  // Generate AI-powered mock answer for the current question
  const generateMockAnswer = async (style) => {
    if (mockLoading || isThinking) return;

    // Extract the latest interviewer question text
    const lastInterviewerMsg = [...messages].reverse().find((m) => m.role === 'interviewer');
    if (!lastInterviewerMsg) return;

    setMockLoading(style);
    try {
      const res = await fetch('http://localhost:8000/api/mock-answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: sessionId,
          question: lastInterviewerMsg.text,
          answerStyle: style,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setInputText(data.answer || '');
        // Focus textarea
        setTimeout(() => textareaRef.current?.focus(), 50);
      } else {
        console.error('Mock answer API error:', res.status);
      }
    } catch (err) {
      console.error('Mock answer fetch failed:', err);
    } finally {
      setMockLoading(null);
    }
  };

  const MOCK_BUTTONS = [
    {
      style: 'detailed',
      label: '✅ Detailed Answer',
      color: '#16a34a',
      bg: '#f0fdf4',
      border: '#86efac',
      hoverBg: '#dcfce7',
    },
    {
      style: 'unsure',
      label: '🤔 Unsure Answer',
      color: '#b45309',
      bg: '#fffbeb',
      border: '#fcd34d',
      hoverBg: '#fef3c7',
    },
    {
      style: 'wrong',
      label: '❌ Wrong Answer',
      color: '#dc2626',
      bg: '#fef2f2',
      border: '#fca5a5',
      hoverBg: '#fee2e2',
    },
    {
      style: 'vague',
      label: '💭 Vague Answer',
      color: '#7c3aed',
      bg: '#faf5ff',
      border: '#c4b5fd',
      hoverBg: '#ede9fe',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-light)' }}>
      {/* Top Navigation Bar */}
      <header className="glass-card" style={{
        borderRadius: 0,
        borderLeft: 'none',
        borderRight: 'none',
        borderTop: 'none',
        padding: '14px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 10,
        background: '#ffffff',
        boxShadow: '0 2px 10px rgba(0,0,0,0.03)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button onClick={onBackToSelect} className="btn-secondary" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
            <ArrowLeft size={16} />
            <span>Switch Candidate</span>
          </button>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #e0f2fe, #f3e8ff)',
              border: '1px solid #7dd3fc',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '0.88rem',
              color: 'var(--accent-indigo)'
            }}>
              {candidate.member.name.split(' ').map(n => n[0]).join('')}
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.98rem', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-main)' }}>
                <span>{candidate.member.name}</span>
                <span className="badge badge-cyan" style={{ fontSize: '0.7rem', padding: '2px 8px' }}>{candidate.member.id}</span>
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {candidate.member.jobRole} • {candidate.signals.missionsFirstTry}/{candidate.signals.missionsCompleted} First-Try
              </div>
            </div>
          </div>
        </div>

        {/* Center/Right Status Indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="badge badge-green" style={{ gap: '6px' }}>
            <Zap size={13} />
            <span>Live Engine: Groq llama-3.3-70b</span>
          </div>

          <div className="badge badge-cyan" style={{ gap: '4px' }}>
            <Target size={12} />
            <span>Single-Focus Questions</span>
          </div>

          <div className="badge badge-violet">
            <span>Question {messages.filter(m => m.role === 'candidate').length + 1} of 10</span>
          </div>

          <button onClick={onEndInterview} className="btn-secondary" style={{ color: 'var(--accent-amber)', borderColor: '#fde68a', padding: '6px 14px', fontSize: '0.85rem' }}>
            <span>Wrap Up & Get Debrief</span>
          </button>
        </div>
      </header>

      {/* Main Chat Conversation Container */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '24px 20px',
        maxWidth: '920px',
        width: '100%',
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px'
      }}>
        {messages.map((msg, index) => {
          const isInterviewer = msg.role === 'interviewer';
          const chunks = isInterviewer ? msg.text.split('\n\n').filter(Boolean) : [msg.text];

          return (
            <div
              key={index}
              style={{
                display: 'flex',
                gap: '14px',
                alignSelf: isInterviewer ? 'flex-start' : 'flex-end',
                maxWidth: '88%',
                flexDirection: isInterviewer ? 'row' : 'row-reverse'
              }}
            >
              {/* Avatar */}
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '12px',
                flexShrink: 0,
                background: isInterviewer
                  ? 'linear-gradient(135deg, #e0f2fe, #bae6fd)'
                  : 'linear-gradient(135deg, #f3e8ff, #ddd6fe)',
                border: isInterviewer ? '1px solid #7dd3fc' : '1px solid #c084fc',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: isInterviewer ? 'var(--accent-cyan)' : 'var(--accent-violet)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
              }}>
                {isInterviewer ? <Bot size={20} /> : <User size={20} />}
              </div>

              {/* Message Bubble Container */}
              <div className="glass-card" style={{
                padding: '18px 22px',
                borderRadius: isInterviewer ? '4px 18px 18px 18px' : '18px 4px 18px 18px',
                background: isInterviewer ? '#f0f9ff' : '#f5f3ff',
                borderColor: isInterviewer ? '#bae6fd' : '#ddd6fe',
                boxShadow: '0 3px 14px rgba(0,0,0,0.04)'
              }}>
                <div style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: isInterviewer ? '#0284c7' : '#7c3aed',
                  marginBottom: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <span>{isInterviewer ? 'Senior Technical Interviewer' : candidate.member.name}</span>
                  {isInterviewer && (
                    <span className="badge badge-cyan" style={{ fontSize: '0.65rem', padding: '1px 6px' }}>
                      Senior Persona
                    </span>
                  )}
                  {isInterviewer && !msg.isCounter && questionNumbers[index] && (
                    <span className="badge badge-violet" style={{ fontSize: '0.65rem', padding: '1px 6px' }}>
                      Q{questionNumbers[index]}
                    </span>
                  )}
                  {isInterviewer && msg.isCounter && (
                    <span style={{ fontSize: '0.65rem', padding: '1px 6px', background: '#fef3c7', color: '#92400e', borderRadius: '4px', fontWeight: 600 }}>
                      ↳ Follow-up
                    </span>
                  )}
                </div>

                {/* Render chunked paragraphs cleanly */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {chunks.map((chunk, chunkIdx) => (
                    <div
                      key={chunkIdx}
                      style={{
                        fontSize: '0.95rem',
                        lineHeight: '1.6',
                        color: 'var(--text-main)',
                        background: (isInterviewer && chunks.length > 1 && chunkIdx === chunks.length - 1)
                          ? '#e0f2fe'
                          : 'transparent',
                        padding: (isInterviewer && chunks.length > 1 && chunkIdx === chunks.length - 1)
                          ? '8px 12px'
                          : '0',
                        borderRadius: '6px',
                        borderLeft: (isInterviewer && chunks.length > 1 && chunkIdx === chunks.length - 1)
                          ? '3px solid #0284c7'
                          : 'none'
                      }}
                    >
                      <ReactMarkdown>{chunk}</ReactMarkdown>
                    </div>
                  ))}
                </div>

                <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', textAlign: 'right', marginTop: '10px' }}>
                  {msg.timestamp || 'Just now'}
                </div>
              </div>
            </div>
          );
        })}

        {/* Thinking Indicator */}
        {isThinking && (
          <div style={{ display: 'flex', gap: '14px', alignSelf: 'flex-start', maxWidth: '85%' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #e0f2fe, #bae6fd)',
              border: '1px solid #7dd3fc',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-cyan)'
            }}>
              <Bot size={20} />
            </div>

            <div className="glass-card" style={{ padding: '14px 20px', borderRadius: '4px 18px 18px 18px', background: '#f0f9ff', borderColor: '#bae6fd', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '0.85rem', color: '#0284c7', fontWeight: 600 }}>
                Senior Interviewer is evaluating your answer...
              </span>
              <div style={{ display: 'flex', gap: '4px' }}>
                <div className="dot-bounce-1" style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#0284c7' }} />
                <div className="dot-bounce-2" style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#0284c7' }} />
                <div className="dot-bounce-3" style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#0284c7' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Dynamic AI Mock Answer Buttons */}
      <div style={{ maxWidth: '920px', width: '100%', margin: '0 auto', padding: '0 20px 10px 20px' }}>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
          <Sparkles size={14} color="var(--accent-indigo)" />
          <span>AI Candidate Mock Answers (Generates live answer matching candidate profile):</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
          {MOCK_BUTTONS.map((btn) => {
            const isLoading = mockLoading === btn.style;
            return (
              <button
                key={btn.style}
                type="button"
                onClick={() => generateMockAnswer(btn.style)}
                disabled={isThinking || mockLoading !== null}
                style={{
                  fontSize: '0.8rem',
                  padding: '8px 16px',
                  borderRadius: '20px',
                  whiteSpace: 'nowrap',
                  background: btn.bg,
                  borderColor: btn.border,
                  borderWidth: '1px',
                  borderStyle: 'solid',
                  color: btn.color,
                  cursor: (isThinking || mockLoading !== null) ? 'not-allowed' : 'pointer',
                  fontWeight: 600,
                  opacity: (mockLoading !== null && !isLoading) ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                  transition: 'all 0.2s ease',
                }}
                onMouseOver={(e) => {
                  if (mockLoading === null && !isThinking) {
                    e.currentTarget.style.background = btn.hoverBg;
                  }
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.background = btn.bg;
                }}
              >
                {isLoading ? (
                  <>
                    <span style={{
                      width: '12px',
                      height: '12px',
                      border: `2px solid ${btn.color}`,
                      borderTopColor: 'transparent',
                      borderRadius: '50%',
                      display: 'inline-block',
                      animation: 'spin 1s linear infinite'
                    }} />
                    <span>Generating...</span>
                  </>
                ) : (
                  <span>{btn.label}</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Input Form Footer */}
      <footer className="glass-card" style={{
        borderRadius: 0,
        borderLeft: 'none',
        borderRight: 'none',
        borderBottom: 'none',
        padding: '16px 20px 20px 20px',
        background: '#ffffff',
        boxShadow: '0 -2px 10px rgba(0,0,0,0.03)'
      }}>
        <form onSubmit={handleSend} style={{ maxWidth: '920px', margin: '0 auto', display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <textarea
              ref={textareaRef}
              rows={2}
              placeholder="Type your technical response... (Press Enter to send, Shift+Enter for new line)"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isThinking}
              style={{
                width: '100%',
                background: '#ffffff',
                border: '1px solid #cbd5e1',
                borderRadius: '12px',
                padding: '12px 16px',
                color: 'var(--text-main)',
                fontSize: '0.95rem',
                fontFamily: 'var(--font-sans)',
                resize: 'none',
                outline: 'none',
                lineHeight: '1.5',
                minHeight: '60px',
                maxHeight: '280px',
                overflowY: 'auto',
                boxSizing: 'border-box',
                transition: 'height 0.1s ease'
              }}
            />
          </div>

          <button
            type="submit"
            disabled={!inputText.trim() || isThinking}
            className="btn-primary"
            style={{
              padding: '14px 22px',
              height: '52px',
              opacity: (!inputText.trim() || isThinking) ? 0.5 : 1,
              cursor: (!inputText.trim() || isThinking) ? 'not-allowed' : 'pointer'
            }}
          >
            <span>Send</span>
            <Send size={16} />
          </button>
        </form>
      </footer>
    </div>
  );
}
