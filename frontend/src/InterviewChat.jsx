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


  // Helper to dynamically extract current topic/tool context and question phase
  const getCurrentTopicContext = () => {
    const lastInterviewerMsg = [...messages].reverse().find((m) => m.role === 'interviewer')?.text || '';
    const candMsgCount = messages.filter((m) => m.role === 'candidate').length;
    
    let topicName = 'AI Cohort Mission';
    let toolName = 'the core framework';
    let isFollowUp = /chunk|state|concurrent|technique|specific|parameter|how did you|what data/i.test(lastInterviewerMsg);

    if (/embeddings|vector|chunk/i.test(lastInterviewerMsg)) {
      topicName = 'Embeddings & Vector Databases';
      toolName = 'ChromaDB & Sentence Transformers';
    } else if (/rag|retrieval|hybrid/i.test(lastInterviewerMsg)) {
      topicName = 'End-to-End RAG Architecture';
      toolName = 'FastAPI & ChromaDB Hybrid Retriever';
    } else if (/function|structured|pydantic|json/i.test(lastInterviewerMsg)) {
      topicName = 'Function Calling & Structured Outputs';
      toolName = 'OpenAI Tool Calls & Pydantic Schemas';
    } else if (/agent|crew|langchain|react/i.test(lastInterviewerMsg)) {
      topicName = 'Multi-Agent Orchestration';
      toolName = 'CrewAI & LangChain ReAct Agents';
    } else if (/docker|kubernetes|deploy|container/i.test(lastInterviewerMsg)) {
      topicName = 'Docker & Container Deployment';
      toolName = 'Dockerized FastAPI & Kubernetes Pods';
    } else if (/fine-tuning|lora|qlora|peft/i.test(lastInterviewerMsg)) {
      topicName = 'Fine-Tuning with QLoRA';
      toolName = 'PEFT, Unsloth & HuggingFace Trainer';
    }

    return { topicName, toolName, isFollowUp, lastInterviewerMsg, candMsgCount };
  };

  // Dynamic context-aware preset answers tailored to candidate role & topic depth
  const getDynamicPresetAnswers = () => {
    const { topicName, toolName, isFollowUp, candMsgCount } = getCurrentTopicContext();
    const roleLower = candidate?.member?.jobRole?.toLowerCase() || '';
    const isNonTech = /marketing|hr|human resources|business analyst|ux|design|product|it support/.test(roleLower);

    if (isNonTech) {
      return [
        {
          label: `🟢 Domain-Specific Application (${topicName})`,
          text: `For ${topicName}, I focused on prompt design and output consistency. I structured the prompt to produce clear markdown responses that directly solved our team's workflow automation bottleneck.`
        },
        {
          label: `🟡 Practical Workflow Detail`,
          text: `I tested several prompt variations to make sure the AI chatbot handled edge cases gracefully and returned clean structured data for business reporting.`
        },
        {
          label: `🔴 Basic Tutorial Output`,
          text: `I used the standard prompt template from the cohort module and ran it against our sample data.`
        },
        {
          label: `🔵 User Experience & Friction`,
          text: `The main friction was prompt hallucination. I solved it by giving the model strict instructions to state 'Data not available' whenever context was missing.`
        }
      ];
    }

    if (isFollowUp || candMsgCount > 0) {
      return [
        {
          label: `🟢 Deep Technical Detail (${topicName})`,
          text: `For chunking and state management in ${topicName}, I used RecursiveCharacterTextSplitter with a 512 token window and 64 token overlap. State management under concurrency was handled via a Redis-backed distributed lock with optimistic locking to prevent race conditions.`
        },
        {
          label: `🟡 Specific Implementation Choice`,
          text: `I chose HNSW indexing in ChromaDB with cosine similarity metrics. To maintain low latency, I pre-filtered metadata tags before running the vector search.`
        },
        {
          label: `🔴 Minimal Elaboration`,
          text: `I used standard helper functions from the library and ran it using default memory settings.`
        },
        {
          label: `🔵 Concurrency & Edge-Case Trade-off`,
          text: `The main trade-off was memory footprint versus retrieval accuracy. Fixed-size chunking provided predictable RAM usage under load, but required semantic boundary checks to avoid truncating mid-sentence.`
        }
      ];
    }

    return [
      {
        label: `🟢 Detailed Technical Answer (${topicName})`,
        text: `For ${topicName}, I built a production pipeline using ${toolName}. I handled chunking and state management explicitly, writing comprehensive integration tests to catch edge-case latency spikes.`
      },
      {
        label: `🟡 Vague / Tutorial Answer`,
        text: `For ${topicName}, I followed the standard cohort tutorial instructions and used default configuration parameters. It passed all tests cleanly.`
      },
      {
        label: `🔴 Brief Hand-wave Answer`,
        text: `I used ${toolName} to handle ${topicName} and it completed without any major issues.`
      },
      {
        label: `🔵 Failure Trade-offs & Concurrency`,
        text: `The biggest friction point in ${topicName} was memory overhead under concurrent load. I solved it by serializing context states and adding exponential backoff retries.`
      }
    ];
  };

  const dynamicPresets = getDynamicPresetAnswers();

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

      {/* Dynamic Context-Aware Preset Answer Chips */}
      <div style={{ maxWidth: '920px', width: '100%', margin: '0 auto', padding: '0 20px 10px 20px' }}>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
          <Sparkles size={14} color="var(--accent-indigo)" />
          <span>Dynamic Mock Answers (Adapted to counter-question depth):</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
          {dynamicPresets.map((preset, idx) => (
            <button
              key={idx}
              onClick={() => setInputText(preset.text)}
              className="btn-secondary"
              style={{
                fontSize: '0.78rem',
                padding: '6px 14px',
                borderRadius: '16px',
                whiteSpace: 'nowrap',
                background: '#ffffff',
                borderColor: '#cbd5e1',
                color: 'var(--text-main)',
                boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
              }}
            >
              {preset.label}
            </button>
          ))}
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
