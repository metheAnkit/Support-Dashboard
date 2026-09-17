import React, { useEffect, useMemo, useRef, useState } from 'react';
import { sendMessageToBackend } from '../../utils';

const QUICK_PROMPTS = [
  { label: 'Create Incident', payload: '/create_incident' },
  { label: 'Incident Status', payload: '/incident_status' },
  { label: 'Login Help', payload: '/login_help' },
];

function buildBotMessage(text, sender = 'bot', extra = {}) {
  return {
    id: `${sender}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    sender,
    text,
    ...extra,
  };
}

function HelpDeskPortal() {
  const [messages, setMessages] = useState([
    buildBotMessage('Hello! I am the HelpDesk assistant. Choose a quick option below or ask your question.', 'bot', {
      buttons: QUICK_PROMPTS,
    }),
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [expectingIssueId, setExpectingIssueId] = useState(false);
  const messagesEndRef = useRef(null);

  const canSend = useMemo(() => input.trim().length > 0 && !sending, [input, sending]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    return () => {
      sendMessageToBackend('/restart', 'helpdesk-web').catch(() => {});
    };
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    const userMessage = buildBotMessage(text, 'user');
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setSending(true);

    try {
      // If we previously asked the user for an issue ID, send a check_status payload
      const messageToSend = expectingIssueId
        ? `/check_status_submit{"issue_id":"${text.replace(/"/g, '')}"}`
        : text;
      // reset expectation before sending
      setExpectingIssueId(false);

      const response = await sendMessageToBackend(messageToSend, 'helpdesk-web');
      const botMessages = Array.isArray(response) ? response : [];

      if (botMessages.length === 0) {
        setMessages((prev) => [
          ...prev,
          buildBotMessage('I did not receive a bot reply. Please try rephrasing your question.', 'bot', {
            buttons: QUICK_PROMPTS,
          }),
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          ...botMessages.map((item) =>
            buildBotMessage(item.text || item.image || 'Bot response', 'bot', {
              buttons: item.buttons || QUICK_PROMPTS,
            })
          ),
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        buildBotMessage(err.message || 'Unable to reach the HelpDesk bot right now.'),
      ]);
    } finally {
      setSending(false);
    }
  }

  async function sendQuickPrompt(prompt) {
    setMessages((prev) => [...prev, buildBotMessage(prompt.label, 'user')]);
    setSending(true);
    setExpectingIssueId(false);

    try {
      if (prompt.payload === '/incident_status') {
        setExpectingIssueId(true);
      }

      const response = await sendMessageToBackend(prompt.payload, 'helpdesk-web');
      const botMessages = Array.isArray(response) ? response : [];

      if (botMessages.length === 0) {
        setMessages((prev) => [
          ...prev,
          buildBotMessage('I did not receive a bot reply. Please try again.', 'bot', {
            buttons: QUICK_PROMPTS,
          }),
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          ...botMessages.map((item) =>
            buildBotMessage(item.text || item.image || 'Bot response', 'bot', {
              buttons: item.buttons || QUICK_PROMPTS,
            })
          ),
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        buildBotMessage(err.message || 'Unable to reach the HelpDesk bot right now.', 'bot', {
          buttons: QUICK_PROMPTS,
        }),
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="portal-container helpdesk-portal">
      <section className="portal-section helpdesk-hero">
        <div>
          <h2 className="section-heading">HelpDesk</h2>
          <p className="section-subtext">
            Chat with the Rasa assistant for incident guidance, support questions, and quick help.
          </p>
        </div>
        <div className="helpdesk-badge">Rasa Integrated</div>
      </section>

      <section className="portal-section chatbot-panel">
        <div className="chat-window" aria-label="HelpDesk chatbot conversation">
          {messages.map((message) => (
            <div key={message.id} className={`chat-row ${message.sender === 'user' ? 'user' : 'bot'}`}>
              <div className="chat-bubble">
                <div>{message.text}</div>
                {Array.isArray(message.buttons) && message.buttons.length > 0 && (
                  <div className="chat-bubble-actions">
                    {message.buttons.map((button) => (
                      <button
                        key={button.payload || button.label}
                        type="button"
                        className="chat-reply-btn"
                        onClick={() => sendQuickPrompt(button)}
                        disabled={sending}
                      >
                        {button.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-prompts">
          {QUICK_PROMPTS.map((prompt) => (
            <button
              key={prompt.payload || prompt.label}
              type="button"
              className="chat-prompt-btn"
              onClick={() => sendQuickPrompt(prompt)}
              disabled={sending}
            >
              {prompt.label}
            </button>
          ))}
        </div>

        <form className="chat-form" onSubmit={handleSubmit}>
          <input
            type="text"
            className="form-input chat-input"
            placeholder="Ask the HelpDesk bot..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
          />
          <button type="submit" className="btn btn-primary chat-send-btn" disabled={!canSend}>
            {sending ? 'Sending…' : 'Send'}
          </button>
        </form>
      </section>
    </div>
  );
}

export default HelpDeskPortal;