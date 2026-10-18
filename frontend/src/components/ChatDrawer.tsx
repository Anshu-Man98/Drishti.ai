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
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

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

  const categorizeError = (err: any): string => {
    const status = err?.status;
    const msg = String(err?.message || '');
    if (status === 429 || /429|rate limit/i.test(msg)) {
      return 'Rate limit reached (10 requests/min for user role). Please wait a moment before trying again.';
    }
    if (status === 503 || /503|unavailable/i.test(msg)) {
      return 'Case Assistant service is temporarily unavailable (503). Please retry in a moment.';
    }
    if (status === 403 || /403|forbidden/i.test(msg)) {
      return 'Permission denied (403). Chat access is forbidden for this session.';
    }
    return msg || 'Error communicating with Case Assistant.';
  };

  const loadHistory = React.useCallback(async () => {
    try {
      setError(null);
      const hist = await fetchChatHistory(claimId);
      const msgList = Array.isArray(hist)
        ? hist
        : (Array.isArray((hist as Record<string, unknown>)?.messages)
            ? (hist as Record<string, unknown>).messages as ChatMessage[]
            : []);
      setMessages(msgList);
    } catch (e: any) {
      console.warn('Failed to load chat history:', e);
      setError(categorizeError(e));
    }
  }, [claimId]);

  // Focus management: capture active element on open, auto-focus input, restore on close
  useEffect(() => {
    if (isOpen) {
      lastFocusedRef.current = document.activeElement as HTMLElement;
      const t = setTimeout(() => {
        inputRef.current?.focus();
      }, 60);
      return () => clearTimeout(t);
    }
  }, [isOpen]);

  const handleClose = React.useCallback(() => {
    onClose();
    if (lastFocusedRef.current && typeof lastFocusedRef.current.focus === 'function') {
      setTimeout(() => {
        lastFocusedRef.current?.focus();
      }, 50);
    }
  }, [onClose]);

  // Load chat history on mount or claim change
  useEffect(() => {
    if (claimId && isOpen) {
      loadHistory();
    }
  }, [claimId, isOpen, loadHistory]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [messages, streamingAnswer]);

  const handleSend = async (textToSend?: string) => {
    const msg = (textToSend || inputMessage).trim();
    if (!msg || loading) return;

    setInputMessage('');
    setError(null);
    setLoading(true);
    setStreamingAnswer('');
    setLastFailedMessage(msg);

    // Append user message to UI
    const userMsg: ChatMessage = {
      role: 'user',
      content: msg,
      created_at: new Date().toISOString()
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      await streamClaimChat(
        claimId,
        msg,
        (token) => {
          setStreamingAnswer((prev) => (prev || '') + token);
        },
        (completeRes) => {
          const assistantMsg: ChatMessage = {
            role: 'assistant',
            content: completeRes.answer,
            cited_finding_ids: completeRes.cited_finding_ids,
            cited_evidence: completeRes.cited_evidence,
            created_at: new Date().toISOString()
          };
          setMessages((prev) => [...prev, assistantMsg]);
          setStreamingAnswer(null);
          setLoading(false);
          setLastFailedMessage(null);

          // Auto-focus on primary cited finding if available
          if (completeRes.cited_finding_ids && completeRes.cited_finding_ids.length > 0) {
            onSelectFinding(completeRes.cited_finding_ids[0]);
          }
        },
        (err) => {
          setError(categorizeError(err));
          setStreamingAnswer(null);
          setLoading(false);
        }
      );
    } catch (err: unknown) {
      setError(categorizeError(err));
      setStreamingAnswer(null);
      setLoading(false);
    } finally {
      setLoading(false);
      setStreamingAnswer(null);
    }
  };

  const renderContentWithCitations = (content: string) => {
    // Regex matches [F1], [F2], [F-ARITH-TOTAL], [Clause 3.1], [PAT-SHARED_BAN-06], etc.
    const parts = content.split(/(\[(?:F\d+|F-[A-Z0-9_-]+|Clause\s+\d+\.\d+|PAT-[A-Z0-9_-]+)\])/gi);

    return (
      <span>
        {parts.map((part, i) => {
          const match = part.match(/^\[(F\d+|F-[A-Z0-9_-]+|Clause\s+\d+\.\d+|PAT-[A-Z0-9_-]+)\]$/i);
          if (match) {
            const rawTag = match[1];
            const resolvedFindingId = aliasMap[rawTag] || aliasMap[rawTag.toLowerCase()] || rawTag;
            const isTargeted = resolvedFindingId === activeFindingId;

            return (
              <button
                key={i}
                type="button"
                onClick={() => onSelectFinding(resolvedFindingId)}
                className={`inline-flex items-center space-x-1 px-1.5 py-0.5 mx-0.5 rounded text-[11px] font-mono font-medium transition-all shadow-2xs ${
                  isTargeted
                    ? 'bg-amber-primary text-black ring-2 ring-amber-bright font-bold'
                    : 'bg-amber-primary/10 text-amber-primary hover:bg-amber-primary hover:text-black border border-amber-primary/30'
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

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleClose]);

  return (
    <>
      {/* Backdrop with fade transition */}
      <div
        className={`fixed inset-0 bg-black/60 backdrop-blur-xs z-50 transition-opacity duration-300 ${
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Drawer Panel with hardware-accelerated translateX */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Case Assistant Chat"
        className={`fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-surface border-l border-white/10 shadow-2xl flex flex-col backdrop-blur-md transition-transform duration-300 ease-out will-change-transform ${
          isOpen ? 'translate-x-0 pointer-events-auto' : 'translate-x-full pointer-events-none'
        }`}
      >
        {/* Header */}
        <div className="p-4 bg-surface-elevated border-b border-white/8 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-amber-primary/10 border border-amber-primary/20 flex items-center justify-center text-amber-primary">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <span>Case Assistant</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
                  Gemini
                </span>
              </h3>
              <p className="text-[11px] text-muted">Grounded strictly on Claim & Dossier findings</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            aria-label="Close Case Assistant"
            className="p-1.5 rounded-lg text-muted hover:text-text-primary hover:bg-white/10 transition-colors cursor-pointer"
            title="Close Case Assistant"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

      {/* Suggested Questions Quick Bar */}
      <div className="p-3 bg-surface-elevated/40 border-b border-white/6">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted mb-2 flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-amber-primary" />
          <span>Suggested Questions</span>
        </p>
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTED_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(q)}
              disabled={loading}
              className="text-xs px-2.5 py-1 rounded-lg bg-surface border border-white/10 text-text-secondary hover:text-amber-primary hover:border-amber-primary/40 transition-all text-left"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Message Stream Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {messages.length === 0 && !streamingAnswer && (
          <div className="py-12 text-center text-muted space-y-2">
            <MessageSquare className="w-10 h-10 mx-auto text-muted/40" />
            <p className="text-sm font-medium text-text-primary">Case Assistant Ready</p>
            <p className="text-xs max-w-xs mx-auto text-text-secondary">
              Ask anything about the claim&apos;s itemized bill, mathematical discrepancies, policy caps, or forensic findings.
            </p>
          </div>
        )}

        {messages.map((m, idx) => {
          const isUser = m.role === 'user';
          return (
            <div
              key={idx}
              className={`flex items-start gap-2.5 ${isUser ? 'flex-row-reverse' : ''}`}
            >
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs ${
                  isUser
                    ? 'bg-amber-primary text-black font-bold'
                    : 'bg-surface-elevated text-amber-primary border border-white/10'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div className={`space-y-1.5 max-w-[85%] ${isUser ? 'items-end' : ''}`}>
                <div
                  className={`p-3 rounded-2xl leading-relaxed whitespace-pre-wrap ${
                    isUser
                      ? 'bg-amber-primary text-black font-medium rounded-tr-xs shadow-xs'
                      : 'bg-surface-elevated/90 border border-white/8 text-text-primary rounded-tl-xs'
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
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-surface text-muted border border-white/10"
                        title={ev.quote ? `Quote: ${ev.quote}` : undefined}
                      >
                        <Crosshair className="w-2.5 h-2.5 text-amber-primary" />
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
          <div className="flex items-start gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-surface-elevated text-amber-primary border border-white/10 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="space-y-1.5 max-w-[85%]">
              <div className="p-3 rounded-2xl rounded-tl-xs bg-surface-elevated border border-amber-primary/40 text-text-primary leading-relaxed whitespace-pre-wrap shadow-2xs">
                {renderContentWithCitations(streamingAnswer || '')}
                <span className="inline-block w-1.5 h-3 ml-1 bg-amber-primary animate-pulse" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span className="flex-1 leading-relaxed">{error}</span>
            </div>
            {lastFailedMessage && (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => handleSend(lastFailedMessage)}
                  className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Retry Query</span>
                </button>
              </div>
            )}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form Footer */}
      <div className="p-3 bg-surface-elevated border-t border-white/8">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2"
        >
          <input
            ref={inputRef}
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={loading}
            placeholder="Ask Case Assistant about findings, policy caps, or evidence..."
            className="flex-1 bg-surface border border-white/10 rounded-xl px-3.5 py-2 text-xs text-text-primary placeholder-muted focus:outline-none focus:border-amber-primary transition-colors"
          />
          <button
            type="submit"
            disabled={loading || !inputMessage.trim()}
            className={`p-2 rounded-xl transition-all shadow-xs ${
              loading || !inputMessage.trim()
                ? 'bg-surface-elevated text-muted cursor-not-allowed'
                : 'bg-amber-primary hover:bg-amber-bright text-black font-semibold shadow-sm shadow-amber-primary/20'
            }`}
            title="Send query to Case Assistant"
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin text-black" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      </div>
    </div>
  </>
);
};
