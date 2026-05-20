"""CSS global inyectado en Streamlit."""

from __future__ import annotations

import streamlit as st

GLOBAL_CSS = """
<style>
:root {
  --est-bg: #0f1419;
  --est-surface: #1a2332;
  --est-surface-2: #243044;
  --est-border: rgba(148, 163, 184, 0.18);
  --est-text: #e2e8f0;
  --est-muted: #94a3b8;
  --est-accent: #3b82f6;
  --est-user: #1e3a5f;
  --est-assistant: #1e293b;
  --est-success: #22c55e;
  --est-warn: #eab308;
  --est-danger: #ef4444;
}
.block-container { padding-top: 1.25rem; max-width: 1400px; }
.est-card {
  background: var(--est-surface);
  border: 1px solid var(--est-border);
  border-radius: 10px;
  padding: 1rem 1.1rem;
  margin-bottom: 0.75rem;
}
.est-card h4 { margin: 0 0 0.5rem 0; font-size: 0.95rem; color: var(--est-text); }
.est-badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  margin-right: 0.35rem;
  margin-bottom: 0.25rem;
  border: 1px solid var(--est-border);
  background: var(--est-surface-2);
  color: var(--est-muted);
}
.est-badge--accent { border-color: rgba(59,130,246,0.5); color: #93c5fd; }
.est-badge--ok { border-color: rgba(34,197,94,0.4); color: #86efac; }
.est-badge--warn { border-color: rgba(234,179,8,0.4); color: #fde047; }
.est-badge--cache-hit { border-color: rgba(34,197,94,0.5); color: #86efac; }
.est-badge--cache-miss { border-color: rgba(148,163,184,0.3); color: var(--est-muted); }
.est-stat-label { font-size: 0.78rem; color: var(--est-muted); margin-bottom: 0.1rem; }
.est-stat-value { font-size: 1.25rem; font-weight: 600; color: var(--est-text); }
.est-chat-user {
  background: var(--est-user);
  border: 1px solid var(--est-border);
  border-radius: 12px 12px 4px 12px;
  padding: 0.85rem 1rem;
  margin: 0.5rem 0 0.5rem 2rem;
}
.est-chat-assistant {
  background: var(--est-assistant);
  border: 1px solid var(--est-border);
  border-radius: 12px 12px 12px 4px;
  padding: 0.85rem 1rem;
  margin: 0.5rem 2rem 0.5rem 0;
}
.est-chat-system {
  background: rgba(59,130,246,0.08);
  border: 1px dashed rgba(59,130,246,0.35);
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
  border-color: rgba(59,130,246,0.55);
  background: rgba(59,130,246,0.12);
}
.est-empty { text-align: center; padding: 2rem; color: var(--est-muted); }
.est-diff-add { color: #86efac; }
.est-diff-remove { color: #fca5a5; }
.est-error-box {
  border: 1px solid rgba(239,68,68,0.45);
  background: rgba(239,68,68,0.08);
  border-radius: 8px;
  padding: 0.85rem 1rem;
  margin: 0.5rem 0;
}
</style>
"""


def inject_global_css() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
