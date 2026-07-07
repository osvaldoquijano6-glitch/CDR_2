"""Componentes HTML personalizados para Streamlit con diseño SaaS/laboratorio."""

import streamlit as st


def inject_custom_css():
    """Inyecta CSS personalizado para mantener coherencia tipografica."""
    st.components.v1.html(
        """
        <script>
        (function() {
            const style = document.createElement('style');
            style.textContent = `
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
                
                * { font-family: 'Inter', Helvetica, Arial, sans-serif !important; }
                
                h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
                    font-family: 'Inter', sans-serif !important;
                    color: #102033 !important;
                    letter-spacing: 0;
                }
                
                .main .block-container {
                    padding-top: 1.2rem !important;
                    padding-bottom: 2rem !important;
                    max-width: 1260px !important;
                }
            `;
            document.head.appendChild(style);
        })();
        </script>
        """,
        height=0,
        scrolling=False,
    )


def modern_card(title, content, icon="", key=None):
    """Renderiza una tarjeta de laboratorio moderna."""
    html_content = f"""
    <div style="
        background: #ffffff;
        border: 1px solid #d7e2ea;
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 14px;
        transition: border-color 0.2s ease;
        box-shadow: 0 8px 24px rgba(15,32,51,0.05);
    " onmouseover="this.style.borderColor='#0f766e'" 
       onmouseout="this.style.borderColor='#d7e2ea'">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
            <span style="font-size: 1.2rem;">{icon}</span>
            <h3 style="
                font-family: 'Inter', sans-serif;
                font-size: 0.92rem;
                font-weight: 600;
                color: #102033;
                margin: 0;
                letter-spacing: 0;
            ">{title}</h3>
        </div>
        <div style="
            font-family: 'Inter', Helvetica, sans-serif;
            color: #64748b;
            font-size: 0.82rem;
            line-height: 1.55;
        ">
            {content}
        </div>
    </div>
    """
    st.components.v1.html(html_content, height=140, key=key)


def modern_metric(label, value, delta=None, key=None):
    """Renderiza un KPI minimalista."""
    delta_html = ""
    if delta:
        color = "#4ade80" if str(delta).startswith("+") else "#f87171"
        delta_html = f'<div style="color: {color}; font-size: 0.72rem; margin-top: 4px;">{delta}</div>'
    
    html_content = f"""
    <div style="
        background: #ffffff;
        border: 1px solid #d7e2ea;
        border-radius: 8px;
        padding: 16px 18px;
        box-shadow: 0 8px 24px rgba(15,32,51,0.05);
    ">
        <div style="
            font-family: 'Inter', Helvetica, sans-serif;
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0;
            font-weight: 600;
            color: #64748b;
            margin-bottom: 8px;
        ">{label}</div>
        <div style="
            font-family: 'Inter', sans-serif;
            font-size: 1.65rem;
            font-weight: 700;
            color: #102033;
            line-height: 1;
        ">{value}</div>
        {delta_html}
    </div>
    """
    st.components.v1.html(html_content, height=110, key=key)


def modern_header(title, subtitle="", badge="", key=None):
    """Renderiza un header minimalista."""
    badge_html = ""
    if badge:
        badge_html = f"""
        <div style="
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: #e6f3f1;
            border: 1px solid #b9d9d2;
            color: #115e59;
            font-family: 'Inter', sans-serif;
            font-size: 0.68rem;
            font-weight: 600;
            padding: 4px 12px;
            border-radius: 100px;
            letter-spacing: 0;
            text-transform: uppercase;
            margin-bottom: 12px;
        ">{badge}</div>
        """
    
    html_content = f"""
    <div style="
        margin-bottom: 20px;
        padding: 0;
    ">
        {badge_html}
        <h1 style="
            font-family: 'Inter', sans-serif;
            font-size: 1.55rem;
            font-weight: 700;
            color: #102033;
            margin: 0 0 4px 0;
            letter-spacing: 0;
        ">{title}</h1>
        <p style="
            font-family: 'Inter', Helvetica, sans-serif;
            color: #64748b;
            font-size: 0.85rem;
            margin: 0;
            line-height: 1.5;
        ">{subtitle}</p>
    </div>
    """
    st.components.v1.html(html_content, height=120, key=key)
