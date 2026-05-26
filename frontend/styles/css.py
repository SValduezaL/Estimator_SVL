"""CSS global inyectado en Streamlit."""

from __future__ import annotations

import streamlit as st

GLOBAL_CSS = """
<style>
:root {
  --est-bg: #0f1419;
  --est-surface: #1e293b;
  --est-surface-2: #334155;
  --est-border: rgba(148, 163, 184, 0.28);
  --est-text: #f8fafc;
  --est-text-secondary: #e2e8f0;
  --est-muted: #cbd5e1;
  --est-accent: #60a5fa;
  --est-user: #1e40af;
  --est-assistant: #1e293b;
  --est-success: #4ade80;
  --est-warn: #facc15;
  --est-danger: #f87171;
}
.block-container { padding-top: 1.25rem; max-width: 1400px; }
.est-card {
  background: var(--est-surface);
  border: 1px solid var(--est-border);
  border-radius: 10px;
  padding: 1rem 1.1rem;
  margin-bottom: 0.75rem;
  color: var(--est-text);
}
.est-card h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.95rem;
  color: var(--est-text);
  font-weight: 600;
}
.est-card-body {
  color: var(--est-text-secondary);
  font-size: 0.95rem;
  line-height: 1.5;
}
.est-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  margin-right: 0.35rem;
  margin-bottom: 0.25rem;
  border: 1px solid var(--est-border);
  background: var(--est-surface-2);
  color: var(--est-text);
}
.est-badge--accent {
  border-color: rgba(96,165,250,0.65);
  background: rgba(30,64,175,0.45);
  color: #dbeafe;
}
.est-badge--ok {
  border-color: rgba(74,222,128,0.5);
  background: rgba(22,101,52,0.35);
  color: #dcfce7;
}
.est-badge--warn {
  border-color: rgba(250,204,21,0.5);
  background: rgba(113,63,18,0.35);
  color: #fef9c3;
}
.est-badge--cache-hit {
  border-color: rgba(74,222,128,0.55);
  background: rgba(22,101,52,0.35);
  color: #bbf7d0;
}
.est-badge--cache-miss {
  border-color: var(--est-border);
  background: var(--est-surface-2);
  color: var(--est-muted);
}
.est-stat-label { font-size: 0.78rem; color: var(--est-muted); margin-bottom: 0.1rem; }
.est-stat-value { font-size: 1.25rem; font-weight: 600; color: var(--est-text); }
.est-chat-user {
  background: var(--est-user);
  border: 1px solid rgba(96,165,250,0.45);
  border-radius: 12px 12px 4px 12px;
  padding: 0.85rem 1rem;
  margin: 0.5rem 0 0.5rem 2rem;
  color: var(--est-text);
}
.est-chat-assistant {
  background: var(--est-assistant);
  border: 1px solid var(--est-border);
  border-radius: 12px 12px 12px 4px;
  padding: 0.85rem 1rem;
  margin: 0.5rem 2rem 0.5rem 0;
  color: var(--est-text);
}
.est-chat-user .est-chat-meta,
.est-chat-assistant .est-chat-meta {
  font-size: 0.72rem;
  color: var(--est-muted);
  margin-bottom: 0.35rem;
}
.est-chat-user .est-chat-body,
.est-chat-assistant .est-chat-body {
  color: var(--est-text-secondary);
  font-size: 0.95rem;
  line-height: 1.55;
}
.est-chat-system {
  background: rgba(59,130,246,0.12);
  border: 1px dashed rgba(96,165,250,0.45);
  border-radius: 8px;
  padding: 0.6rem 0.85rem;
  margin: 0.35rem 0;
  font-size: 0.88rem;
  color: var(--est-muted);
}
.est-meta-row { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.5rem; }
.est-sidebar-session {
  padding: 0.55rem 0.65rem;
  border-radius: 8px;
  border: 1px solid transparent;
  margin-bottom: 0.35rem;
  cursor: pointer;
}
.est-sidebar-session.active {
  border-color: rgba(96,165,250,0.55);
  background: rgba(59,130,246,0.18);
}
.est-empty { text-align: center; padding: 2rem; color: var(--est-muted); }
.est-diff-add { color: #86efac; font-weight: 500; }
.est-diff-remove { color: #fca5a5; font-weight: 500; }
.est-diff-mod { color: #fde68a; font-weight: 500; }
.est-error-box {
  border: 1px solid rgba(248,113,113,0.55);
  background: rgba(127,29,29,0.25);
  border-radius: 8px;
  padding: 0.85rem 1rem;
  margin: 0.5rem 0;
  color: var(--est-text);
}
.est-ops-panel {
  background: var(--est-surface);
  border: 1px solid var(--est-border);
  border-radius: 10px;
  padding: 0.85rem 1rem;
  margin-bottom: 1rem;
  color: var(--est-text);
}
.est-ops-panel li { color: var(--est-text-secondary); margin-bottom: 0.25rem; }
</style>
"""


def inject_global_css() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
