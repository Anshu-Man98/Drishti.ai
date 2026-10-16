import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare, Send, X, Bot, User, Crosshair,
  Sparkles, RefreshCw, AlertCircle
} from 'lucide-react';
import { ChatMessage, Finding } from '../types';
import { streamClaimChat, fetchChatHistory } from '../services/api';

interface ChatDrawerProps {
  claimId: string;
  isOpen: boolean;
  onClose: () => void;
  findings: Finding[];
  activeFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
}

const SUGGESTED_QUESTIONS = [
  "Why was this flagged?",
  "What's the strongest evidence?",
  "Which policy clause applies?",
  "What should I verify next?"
];

export const ChatDrawer: React.FC<ChatDrawerProps> = ({
  claimId,
  isOpen,
  onClose,
  findings,
  activeFindingId,
  onSelectFinding
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [streamingAnswer, setStreamingAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Map aliases like F1, F2, Clause 3.1, PAT-XXX to actual finding_id
  const aliasMap = React.useMemo(() => {
    const map: Record<string, string> = {};
    findings.forEach((f, idx) => {
      map[`F${idx + 1}`] = f.finding_id;
      map[`f${idx + 1}`] = f.finding_id;
      map[f.finding_id] = f.finding_id;
      if (f.check_id) {
        map[f.check_id] = f.finding_id;
      }
      f.evidence?.forEach((ev) => {
        if (ev.doc_id) {
          map[ev.doc_id] = f.finding_id;
          map[ev.doc_id.toLowerCase()] = f.finding_id;
        }
      });
      if (f.agent === 'rag') {
        map['rag'] = f.finding_id;
      }
      if (f.agent === 'policy') {
        map['policy'] = f.finding_id;
      }
    });
    return map;
  }, [findings]);

  // Load chat history on mount or claim change
  useEffect(() => {
    if (claimId && isOpen) {
      loadHistory();
    }
  }, [claimId, isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingAnswer]);

  const loadHistory = async () => {
    try {
      setError(null);
      const hist = await fetchChatHistory(claimId);
      setMessages(hist);
    } catch (e: any) {
      console.warn('Failed to load chat history:', e);
    }
  };

  const handleSend = async (textToSend?: string) => {
    const msg = (textToSend || inputMessage).trim();
    if (!msg || loading) return;

    setInputMessage('');
    setError(null);
    setLoading(true);
    setStreamingAnswer('');

    // Append user message to UI
    const userMsg: ChatMessage = {
      role: 'user',
      content: msg,
      created_at: new Date().toISOString()
    };
    setMessages((prev) => [...prev, userMsg]);

    let accumulatedText = '';

    try {
      await streamClaimChat(
        claimId,
        msg,
        (chunk) => {
          accumulatedText += chunk;
          setStreamingAnswer(accumulatedText);
        },
        (completeRes) => {
          const finalAnswer = (completeRes.answer || accumulatedText).trim();
          const assistantMsg: ChatMessage = {
            role: 'assistant',
            content: finalAnswer || 'No response details available from audit copilot for this inquiry.',
            cited_finding_ids: completeRes.cited_finding_ids,
            cited_evidence: completeRes.cited_evidence,
            created_at: new Date().toISOString()
          };
          setMessages((prev) => [...prev, assistantMsg]);
          setStreamingAnswer(null);
          setLoading(false);

          // Auto-focus on primary cited finding if available
          if (completeRes.cited_finding_ids && completeRes.cited_finding_ids.length > 0) {
            onSelectFinding(completeRes.cited_finding_ids[0]);
          }
        },
        (err) => {
          setError(err.message || 'Error communicating with assistant.');
          setStreamingAnswer(null);
          setLoading(false);
        }
      );
    } catch (err: any) {
      setError(err.message || 'Error communicating with assistant.');
      setStreamingAnswer(null);
      setLoading(false);
    } finally {
      setLoading(false);
      setStreamingAnswer(null);
    }
  };

  const renderContentWithCitations = (content: string) => {
    // Regex matches [F1], [F2], [F-ARITH-TOTAL], [Clause 3.1], [PAT-SHARED_BAN-06], etc.
    const parts = content.split(/(\[(?:F\d+|F-[A-Z0-9_\-]+|Clause\s+\d+\.\d+|PAT-[A-Z0-9_\-]+)\])/gi);

    return (
      <span>
        {parts.map((part, i) => {
          const match = part.match(/^\[(F\d+|F-[A-Z0-9_\-]+|Clause\s+\d+\.\d+|PAT-[A-Z0-9_\-]+)\]$/i);
          if (match) {
            const rawTag = match[1];
            const resolvedFindingId = aliasMap[rawTag] || aliasMap[rawTag.toLowerCase()] || rawTag;
            const isTargeted = resolvedFindingId === activeFindingId;

            return (
              <button
                key={i}
                type="button"
                onClick={() => onSelectFinding(resolvedFindingId)}
                className={`inline-flex items-center space-x-1 px-1.5 py-0.5 mx-0.5 rounded text-[11px] font-mono font-bold transition-all shadow-sm ${
                  isTargeted
                    ? 'bg-sky-500 text-white ring-2 ring-sky-400'
                    : 'bg-sky-500/20 text-sky-300 hover:bg-sky-500 hover:text-white border border-sky-500/40'
                }`}
                title={`Click to focus evidence for ${resolvedFindingId} on document`}
              >
                <Crosshair className="w-3 h-3 shrink-0" />
                <span>{part}</span>
              </button>
            );
          }
          return <span key={i}>{part}</span>;
        })}
      </span>
    );
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-slate-950 border-l border-slate-800 shadow-2xl flex flex-col transition-all duration-300">
      {/* Header */}
      <div className="p-4 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>Dossier Audit Copilot</span>
              <span className="text-[10px] font-mono px-2 py-0.2 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Gemini Pro
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">Grounded strictly on Claim & Dossier findings</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Close chat drawer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Suggested Questions Quick Bar */}
      <div className="p-3 bg-slate-900/50 border-b border-slate-800/80">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center space-x-1">
          <Sparkles className="w-3 h-3 text-amber-400" />
          <span>Suggested Questions</span>
        </p>
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTED_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(q)}
              disabled={loading}
              className="text-xs px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 hover:bg-slate-800 transition-all text-left"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Message Stream Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {messages.length === 0 && !streamingAnswer && (
          <div className="py-12 text-center text-slate-500 space-y-2">
            <MessageSquare className="w-10 h-10 mx-auto text-slate-700" />
            <p className="text-sm font-medium text-slate-400">No messages yet.</p>
            <p className="text-xs max-w-xs mx-auto">
              Ask anything about the claim's itemized bill, mathematical discrepancies, policy caps, or forensic findings.
            </p>
          </div>
        )}

        {messages.map((m, idx) => {
          const isUser = m.role === 'user';
          return (
            <div
              key={idx}
              className={`flex items-start space-x-2.5 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
            >
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs ${
                  isUser
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-800 text-blue-400 border border-slate-700'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div className={`space-y-1.5 max-w-[85%] ${isUser ? 'items-end' : ''}`}>
                <div
                  className={`p-3 rounded-2xl leading-relaxed whitespace-pre-wrap ${
                    isUser
                      ? 'bg-blue-600 text-white rounded-tr-sm'
                      : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-sm'
                  }`}
                >
                  {isUser ? m.content : renderContentWithCitations(m.content)}
                </div>

                {/* Evidence citations banner */}
                {!isUser && m.cited_evidence && m.cited_evidence.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {m.cited_evidence.map((ev, evIdx) => (
                      <span
                        key={evIdx}
                        className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono bg-slate-900 text-slate-400 border border-slate-800"
                        title={ev.quote ? `Quote: ${ev.quote}` : undefined}
                      >
                        <Crosshair className="w-2.5 h-2.5 text-sky-400" />
                        <span>
                          {ev.layer === 'retrieved'
                            ? `Retrieved: ${ev.doc_id}`
                            : `Page ${ev.page} ${ev.bbox ? `[Citation Box]` : ''}`}
                        </span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Real-time Streaming Bubble */}
        {streamingAnswer !== null && (
          <div className="flex items-start space-x-2.5">
            <div className="w-7 h-7 rounded-lg bg-slate-800 text-blue-400 border border-slate-700 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="space-y-1.5 max-w-[85%]">
              <div className="p-3 rounded-2xl rounded-tl-sm bg-slate-900 border border-blue-500/30 text-slate-200 leading-relaxed whitespace-pre-wrap shadow-lg shadow-blue-500/5">
                {renderContentWithCitations(streamingAnswer || '')}
                <span className="inline-block w-1.5 h-3 ml-1 bg-blue-400 animate-pulse" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form Footer */}
      <div className="p-3 bg-slate-900 border-t border-slate-800">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={loading}
            placeholder="Ask about findings, caps, or evidence citations..."
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={loading || !inputMessage.trim()}
            className={`p-2.5 rounded-xl transition-all shadow-md ${
              loading || !inputMessage.trim()
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20'
            }`}
            title="Send query to Copilot"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      </div>
    </div>
  );
};
