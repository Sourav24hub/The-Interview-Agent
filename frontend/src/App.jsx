import React, { useState, useEffect } from 'react';
import { CandidateSelector } from './CandidateSelector';
import { InterviewChat } from './InterviewChat';
import { FeedbackDashboard } from './FeedbackDashboard';
import { FALLBACK_CANDIDATES } from './candidatesData';

const BACKEND_URL = 'http://localhost:8000';

export default function App() {
  const [screen, setScreen] = useState('select'); // 'select' | 'interview' | 'feedback'
  const [candidates, setCandidates] = useState(FALLBACK_CANDIDATES);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [sessionId, setSessionId] = useState('');
  const [messages, setMessages] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [turnCount, setTurnCount] = useState(0);

  // Fetch candidates from FastAPI backend on load if available
  useEffect(() => {
    fetch(`${BACKEND_URL}/api/candidates`)
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setCandidates(data);
        }
      })
      .catch((err) => {
        console.warn('Backend candidates API not reached, using fallback dataset:', err);
      });
  }, []);

  // Initialize a new interview session
  const handleSelectCandidate = async (candidate) => {
    setSelectedCandidate(candidate);
    const newSessionId = `session-${candidate.member.id}-${Date.now().toString().slice(-6)}`;
    setSessionId(newSessionId);
    setIsThinking(true);
    setMessages([]);
    setTurnCount(0);
    setFeedback(null);
    setScreen('interview');

    try {
      const response = await fetch(`${BACKEND_URL}/api/interview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: newSessionId,
          candidate: candidate
        })
      });

      if (response.ok) {
        const data = await response.json();
        setMessages([
          {
            role: 'interviewer',
            text: data.reply,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      } else {
        // Fallback welcome message if API unreachable
        setMessages([
          {
            role: 'interviewer',
            text: `Alright, ${candidate.member.name}. Let's get into it.\n\nI've looked at your profile — ${candidate.member.jobRole}, ${candidate.member.yearsExperience} year(s) of experience. You finished ${candidate.signals.missionsCompleted} missions in the cohort.\n\nWalk me through your first-try pass on Day 7: Embeddings Explained. What was your thought process?`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
      }
    } catch (err) {
      console.error('Error starting interview:', err);
      setMessages([
        {
          role: 'interviewer',
          text: `Alright, ${candidate.member.name}. Let me know when you're ready to walk me through your AI cohort missions.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setIsThinking(false);
    }
  };

  // Send a conversation turn
  const handleSendMessage = async (userText, retryCount = 0) => {
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const updatedMessages = [
      ...messages,
      { role: 'candidate', text: userText, timestamp: timeStr }
    ];

    setMessages(updatedMessages);
    setIsThinking(true);

    try {
      const response = await fetch(`${BACKEND_URL}/api/interview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId: sessionId,
          message: userText
        })
      });

      if (response.ok) {
        const data = await response.json();
        // Detect if the reply is a counter-question (drilling current topic) vs a new topic question
        const isCounter = /counter|drilling|drilling previous|sharp counter|elaboration probe|precision drill/i.test(data.reply);
        const newHistory = [
          ...updatedMessages,
          {
            role: 'interviewer',
            text: data.reply,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isCounter: isCounter
          }
        ];
        setMessages(newHistory);

        // Only increment question counter on real new topic questions (not counter-question drills)
        if (!isCounter) {
          setTurnCount((prev) => prev + 1);
        }

        if (data.done) {
          setFeedback(data.feedback);
          setTimeout(() => setScreen('feedback'), 1400);
        }
      } else if (response.status >= 500 && retryCount < 2) {
        // Retry on server-side errors (e.g. rate-limit fallback failures) up to 2 times
        console.warn(`Server error ${response.status}, retrying (attempt ${retryCount + 1})...`);
        setMessages(messages); // revert optimistic candidate message while retrying
        setTimeout(() => handleSendMessage(userText, retryCount + 1), 1500);
        return;
      } else {
        const errText = await response.text().catch(() => 'Unknown error');
        console.error('Interview API error:', response.status, errText);
        setMessages([
          ...updatedMessages,
          {
            role: 'interviewer',
            text: '⚠️ I had trouble connecting to the interview engine. Please try again.',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isCounter: false
          }
        ]);
      }
    } catch (err) {
      console.error('Error sending message turn:', err);
      if (retryCount < 2) {
        console.warn(`Network error, retrying (attempt ${retryCount + 1})...`);
        setTimeout(() => handleSendMessage(userText, retryCount + 1), 2000);
        return;
      }
      // After all retries failed, show user-visible error
      setMessages([
        ...updatedMessages,
        {
          role: 'interviewer',
          text: '⚠️ Connection to the interview engine failed. Please check the backend server is running, then try again.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isCounter: false
        }
      ]);
    } finally {
      setIsThinking(false);
    }
  };

  // Manual wrap up shortcut
  const handleEndInterview = () => {
    setFeedback({
      summary: `${selectedCandidate.member.name} (${selectedCandidate.member.jobRole}) completed the AI cohort technical debrief across multiple curriculum topics.`,
      strengths: [
        `Sustained daily engagement with ${selectedCandidate.signals.commitDays} active commit days.`,
        `High first-attempt pass accuracy (${selectedCandidate.signals.missionsFirstTry}/${selectedCandidate.signals.missionsCompleted} missions).`
      ],
      gaps: [
        "Knowledge gaps identified in advanced multi-agent orchestration and deployment modules.",
        "Candidate tends toward high-level answers without unprompted elaboration on trade-offs."
      ],
      next: [
        "Practice articulating technical decisions out loud with specific trade-offs.",
        "Ship a production-grade AI project end-to-end (RAG + agents + deployment)."
      ]
    });
    setScreen('feedback');
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-dark)' }}>
      {screen === 'select' && (
        <CandidateSelector
          candidates={candidates}
          onSelectCandidate={handleSelectCandidate}
        />
      )}

      {screen === 'interview' && selectedCandidate && (
        <InterviewChat
          candidate={selectedCandidate}
          sessionId={sessionId}
          messages={messages}
          isThinking={isThinking}
          turnCount={turnCount}
          onSendMessage={handleSendMessage}
          onEndInterview={handleEndInterview}
          onBackToSelect={() => setScreen('select')}
        />
      )}

      {screen === 'feedback' && selectedCandidate && (
        <FeedbackDashboard
          candidate={selectedCandidate}
          feedback={feedback}
          messages={messages}
          onRestart={() => setScreen('select')}
        />
      )}
    </div>
  );
}
