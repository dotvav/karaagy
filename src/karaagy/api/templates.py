"""Self-contained, responsive HTML status page template renderer for Karaagy."""

import base64
import functools
import html
from pathlib import Path
from typing import Any


@functools.lru_cache(maxsize=1)
def get_logo_svg() -> str:
    """Load the official Karaagy SVG logo from disk with fallbacks."""
    candidates = [
        Path(__file__).parents[3] / "assets" / "karaagy-logo.svg",
        Path.cwd() / "assets" / "karaagy-logo.svg",
    ]
    for p in candidates:
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                pass
    return ""


@functools.lru_cache(maxsize=1)
def get_logo_b64() -> str:
    """Return base64-encoded SVG logo for favicon embedding."""
    svg = get_logo_svg()
    if svg:
        return base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return ""


def render_status_html(
    base_url: str,
    version_info: dict[str, str],
    agy_version: str,
    metrics: dict[str, Any],
    quota_data: dict[str, Any],
    models: list[str],
    aliases: dict[str, str],
    settings_dict: dict[str, Any],
    env_vars: dict[str, str],
) -> str:
    """Render the full self-contained HTML status page."""
    clean_base = base_url.rstrip("/")

    # Build quota cards HTML
    quota_html_parts = []
    if quota_data.get("available") and quota_data.get("groups"):
        for grp in quota_data["groups"]:
            g_name = html.escape(grp.get("name", "Model Group"))
            g_desc = html.escape(grp.get("description", ""))
            buckets_html = []
            for b in grp.get("buckets", []):
                b_name = html.escape(b.get("name", "Limit"))
                pct = b.get("remaining_percent", 100.0)
                reset_time = html.escape(b.get("reset_time", ""))
                b_desc = html.escape(b.get("description", ""))

                # Color scale for remaining quota
                bar_color = "#10b981"  # green
                if pct < 20:
                    bar_color = "#ef4444"  # red
                elif pct < 50:
                    bar_color = "#f59e0b"  # amber

                buckets_html.append(f"""
                <div class="bucket-card">
                    <div class="bucket-header">
                        <span class="bucket-name">{b_name}</span>
                        <span class="bucket-pct" style="color: {bar_color};">{pct}% remaining</span>
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: {pct}%; background-color: {bar_color};"></div>
                    </div>
                    <div class="bucket-meta">
                        <span>{b_desc or "Active quota window"}</span>
                        {f'<span class="reset-time">Resets: {reset_time}</span>' if reset_time else ""}
                    </div>
                </div>
                """)

            quota_html_parts.append(f"""
            <div class="quota-group">
                <div class="group-title">{g_name}</div>
                <div class="group-desc">{g_desc}</div>
                <div class="buckets-grid">{"".join(buckets_html)}</div>
            </div>
            """)
        quota_content = "".join(quota_html_parts)
    else:
        err_msg = html.escape(quota_data.get("error") or "Quota information currently unavailable.")
        quota_content = f"""
        <div class="notice-box error-box">
            <span>⚠️ {err_msg}</span>
        </div>
        """

    # Model badges HTML
    model_badges = []
    for m in models:
        m_esc = html.escape(m)
        is_default = m == settings_dict.get("default_model")
        badge_cls = "model-badge default-model" if is_default else "model-badge"
        star = " ★ (Default)" if is_default else ""
        model_badges.append(f'<span class="{badge_cls}"><code>{m_esc}</code>{star}</span>')
    models_html = "".join(model_badges)

    # Aliases table HTML
    alias_rows = []
    for alias_k, target_v in sorted(aliases.items()):
        alias_rows.append(f"""
        <tr>
            <td><code>{html.escape(alias_k)}</code></td>
            <td>→</td>
            <td><code>{html.escape(target_v)}</code></td>
        </tr>
        """)
    aliases_table_html = "".join(alias_rows)

    # Settings table HTML
    setting_rows = []
    for sk, sv in sorted(settings_dict.items()):
        setting_rows.append(f"""
        <tr>
            <td class="key-col"><code>{html.escape(str(sk))}</code></td>
            <td class="val-col"><code>{html.escape(str(sv))}</code></td>
        </tr>
        """)
    settings_table_html = "".join(setting_rows)

    # Environment variables table HTML
    env_rows = []
    for ek, ev in sorted(env_vars.items()):
        is_redacted = "[REDACTED]" in str(ev)
        val_cls = "redacted-val" if is_redacted else "plain-val"
        env_rows.append(f"""
        <tr>
            <td class="key-col"><code>{html.escape(str(ek))}</code></td>
            <td class="val-col {val_cls}"><code>{html.escape(str(ev))}</code></td>
        </tr>
        """)
    env_table_html = "".join(env_rows)

    # cURL sample
    sample_curl = f"""curl -X POST "{clean_base}/v1/chat/completions" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "model": "{settings_dict.get("default_model", "gemini-3.8-flash-high")}",
    "messages": [
      {{"role": "system", "content": "You are a helpful assistant."}},
      {{"role": "user", "content": "Hello, world!"}}
    ]
  }}'"""

    quota_age = quota_data.get("cache_age_formatted", "cached")
    logo_svg = get_logo_svg()
    logo_b64 = get_logo_b64()
    favicon_tag = (
        f'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,{logo_b64}">'
        if logo_b64
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(settings_dict.get("app_name", "Karaagy"))} Gateway Status</title>
    {favicon_tag}
    <style>
        :root {{
            --bg: #0d1117;
            --surface: #161b22;
            --surface-hover: #1f242c;
            --border: #30363d;
            --text: #c9d1d9;
            --text-heading: #f0f6fc;
            --text-muted: #8b949e;
            --primary: #58a6ff;
            --primary-bg: rgba(56, 139, 253, 0.15);
            --success: #238636;
            --success-text: #3fb950;
            --warning: #d29922;
            --danger: #f85149;
            --code-bg: #090d13;
            --font-mono: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace;
            --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        @media (prefers-color-scheme: light) {{
            :root {{
                --bg: #f6f8fa;
                --surface: #ffffff;
                --surface-hover: #f3f4f6;
                --border: #d0d7de;
                --text: #24292f;
                --text-heading: #1f2328;
                --text-muted: #57606a;
                --primary: #0969da;
                --primary-bg: rgba(9, 105, 218, 0.1);
                --success: #1a7f37;
                --success-text: #1a7f37;
                --warning: #9a6700;
                --danger: #cf222e;
                --code-bg: #f6f8fa;
            }}
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: var(--font-sans);
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.5;
            padding: 24px 16px;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        header {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            gap: 16px;
        }}
        .header-title-block {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .header-logo {{
            width: 44px;
            height: 44px;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .header-logo svg {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        h1 {{
            font-size: 1.4rem;
            color: var(--text-heading);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background-color: rgba(63, 185, 80, 0.15);
            color: var(--success-text);
            border: 1px solid var(--success-text);
            font-size: 0.75rem;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 20px;
            text-transform: uppercase;
        }}
        .status-dot {{
            width: 8px;
            height: 8px;
            background-color: var(--success-text);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.5; transform: scale(0.85); }}
        }}
        .header-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            font-size: 0.85rem;
            color: var(--text-muted);
        }}
        .meta-item strong {{ color: var(--text-heading); }}
        .card {{
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
        }}
        .card-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-heading);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .btn {{
            background-color: var(--primary-bg);
            color: var(--primary);
            border: 1px solid var(--primary);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
        .btn:hover {{
            background-color: var(--primary);
            color: #ffffff;
        }}
        .btn-disabled {{
            opacity: 0.6;
            cursor: not-allowed;
        }}
        .grid-4 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
        }}
        .stat-box {{
            background-color: var(--code-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px 16px;
        }}
        .stat-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }}
        .stat-value {{
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--text-heading);
            margin-top: 4px;
        }}
        .stat-sub {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 2px;
        }}
        .quota-group {{
            margin-bottom: 20px;
        }}
        .quota-group:last-child {{ margin-bottom: 0; }}
        .group-title {{
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-heading);
        }}
        .group-desc {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 10px;
        }}
        .buckets-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 12px;
        }}
        .bucket-card {{
            background-color: var(--code-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px 14px;
        }}
        .bucket-header {{
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .bucket-name {{ color: var(--text-heading); }}
        .progress-bar-bg {{
            background-color: var(--border);
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 6px;
        }}
        .progress-bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.4s ease;
        }}
        .bucket-meta {{
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        .model-badges-wrap {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .model-badge {{
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            background-color: var(--code-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 0.82rem;
            color: var(--text);
        }}
        .default-model {{
            border-color: var(--primary);
            background-color: var(--primary-bg);
            color: var(--primary);
            font-weight: 600;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            font-family: var(--font-mono);
        }}
        th, td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background-color: var(--code-bg);
            color: var(--text-muted);
            font-weight: 600;
        }}
        .key-col {{ font-weight: 600; color: var(--primary); width: 35%; }}
        .redacted-val {{ color: var(--warning); }}
        pre {{
            background-color: var(--code-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px 16px;
            font-family: var(--font-mono);
            font-size: 0.85rem;
            overflow-x: auto;
            position: relative;
        }}
        code {{
            font-family: var(--font-mono);
            font-size: 0.85em;
        }}
        details {{
            border: 1px solid var(--border);
            border-radius: 6px;
            overflow: hidden;
            background-color: var(--surface);
        }}
        summary {{
            padding: 10px 16px;
            background-color: var(--code-bg);
            cursor: pointer;
            font-weight: 600;
            font-size: 0.9rem;
            user-select: none;
        }}
        details[open] summary {{
            border-bottom: 1px solid var(--border);
        }}
        .details-content {{
            padding: 14px;
            overflow-x: auto;
        }}
        .copy-btn {{
            position: absolute;
            top: 8px;
            right: 8px;
        }}
        footer {{
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-muted);
            padding: 10px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="header-title-block">
                {f'<div class="header-logo">{logo_svg}</div>' if logo_svg else ""}
                <div>
                    <h1>{html.escape(settings_dict.get("app_name", "Karaagy"))}</h1>
                    <span class="status-badge"><span class="status-dot"></span> Online</span>
                </div>
            </div>
            <div class="header-meta">
                <div class="meta-item">Karaagy: <strong>{html.escape(version_info.get("display", "0.1.0"))}</strong></div>
                <div class="meta-item">Antigravity: <strong>v{html.escape(agy_version)}</strong></div>
                <div class="meta-item">Uptime: <strong>{html.escape(metrics.get("uptime_formatted", "0s"))}</strong></div>
                <div class="meta-item">Platform: <strong>{html.escape(version_info.get("os_platform", ""))}</strong></div>
            </div>
        </header>

        <!-- Account Quota /usage Section -->
        <section class="card">
            <div class="card-header">
                <div class="card-title">⚡ Antigravity Quota & Rate Limits (<code>/usage</code>)</div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 0.75rem; color: var(--text-muted);">Updated: <span id="quota-age">{html.escape(quota_age)}</span></span>
                    <button class="btn" id="refresh-quota-btn" onclick="refreshQuota()">🔄 Refresh Quota</button>
                </div>
            </div>
            <div id="quota-container">
                {quota_content}
            </div>
        </section>

        <!-- Gateway Runtime Metrics -->
        <section class="card">
            <div class="card-header">
                <div class="card-title">📊 Gateway Metrics & Throughput</div>
            </div>
            <div class="grid-4">
                <div class="stat-box">
                    <div class="stat-label">Active Concurrency</div>
                    <div class="stat-value">{metrics.get("active_concurrency", 0)} / {metrics.get("max_concurrency", 4)}</div>
                    <div class="stat-sub">Parallel session limit</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Requests Processed</div>
                    <div class="stat-value">{metrics.get("total_requests", 0)}</div>
                    <div class="stat-sub">{metrics.get("successful_requests", 0)} OK · {metrics.get("failed_requests", 0)} Failed</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Tokens</div>
                    <div class="stat-value">{metrics.get("total_tokens", 0):,}</div>
                    <div class="stat-sub">{metrics.get("total_prompt_tokens", 0):,} in · {metrics.get("total_completion_tokens", 0):,} out</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Default Model</div>
                    <div class="stat-value" style="font-size: 1rem; margin-top: 8px;"><code>{html.escape(settings_dict.get("default_model", ""))}</code></div>
                    <div class="stat-sub">Effort: {html.escape(str(settings_dict.get("default_effort") or "auto"))}</div>
                </div>
            </div>
        </section>

        <!-- Discovered Models -->
        <section class="card">
            <div class="card-header">
                <div class="card-title">🤖 Discovered Models ({len(models)} available)</div>
                <a class="btn" href="{clean_base}/v1/models" target="_blank">GET /v1/models</a>
            </div>
            <div class="model-badges-wrap">
                {models_html}
            </div>
        </section>

        <!-- Quick Integration & cURL snippet -->
        <section class="card">
            <div class="card-header">
                <div class="card-title">🔗 Quick Integration</div>
                <div style="display: flex; gap: 8px;">
                    <a class="btn" href="{clean_base}/docs" target="_blank">📖 Swagger Docs</a>
                    <a class="btn" href="{clean_base}/healthz" target="_blank">Health Check</a>
                </div>
            </div>
            <div style="font-size: 0.85rem; margin-bottom: 8px;">
                Base API URL: <code>{clean_base}/v1</code>
            </div>
            <pre><button class="btn copy-btn" onclick="copyCode(this)">Copy cURL</button><code>{html.escape(sample_curl)}</code></pre>
        </section>

        <!-- Model Aliases & Configurations -->
        <details>
            <summary>🔄 Model Compatibility Aliases ({len(aliases)})</summary>
            <div class="details-content">
                <table>
                    <thead>
                        <tr><th>Requested Model ID</th><th></th><th>Routed AGY Target</th></tr>
                    </thead>
                    <tbody>
                        {aliases_table_html}
                    </tbody>
                </table>
            </div>
        </details>

        <!-- Runtime Settings -->
        <details>
            <summary>⚙️ Karaagy Gateway Settings</summary>
            <div class="details-content">
                <table>
                    <thead>
                        <tr><th>Setting Key</th><th>Configured Value</th></tr>
                    </thead>
                    <tbody>
                        {settings_table_html}
                    </tbody>
                </table>
            </div>
        </details>

        <!-- Sanitized Environment Variables -->
        <details>
            <summary>🌐 Runtime Environment Variables ({len(env_vars)})</summary>
            <div class="details-content">
                <p style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 8px;">
                    🔒 Sensitive keys containing KEY, TOKEN, SECRET, AUTH, or PASS are automatically redacted.
                </p>
                <table>
                    <thead>
                        <tr><th>Variable Name</th><th>Value</th></tr>
                    </thead>
                    <tbody>
                        {env_table_html}
                    </tbody>
                </table>
            </div>
        </details>

        <footer>
            Karaagy OpenAI Gateway for Google Antigravity CLI · <a href="{clean_base}/openapi.json" style="color: var(--primary);">openapi.json</a>
        </footer>
    </div>

    <script>
        function copyCode(btn) {{
            const pre = btn.parentElement;
            const code = pre.querySelector('code').innerText;
            navigator.clipboard.writeText(code).then(() => {{
                const orig = btn.innerText;
                btn.innerText = 'Copied!';
                setTimeout(() => btn.innerText = orig, 2000);
            }});
        }}

        async function refreshQuota() {{
            const btn = document.getElementById('refresh-quota-btn');
            const ageSpan = document.getElementById('quota-age');
            btn.classList.add('btn-disabled');
            btn.innerText = 'Refreshing...';
            try {{
                const res = await fetch('{clean_base}/v1/system/refresh-usage', {{ method: 'POST' }});
                if (res.ok) {{
                    window.location.reload();
                }} else {{
                    btn.innerText = 'Error';
                    setTimeout(() => btn.innerText = '🔄 Refresh Quota', 2000);
                }}
            }} catch (e) {{
                btn.innerText = 'Failed';
                setTimeout(() => btn.innerText = '🔄 Refresh Quota', 2000);
            }} finally {{
                btn.classList.remove('btn-disabled');
            }}
        }}
    </script>
</body>
</html>
"""
