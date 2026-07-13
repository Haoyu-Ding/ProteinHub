from __future__ import annotations

from nicegui import ui


MEMBER_DISCIPLINE_OPTIONS = {
    "design": "计算设计",
    "synthesis": "合成",
    "assay": "测试",
    "other": "其他",
}
ROLE_LABELS = {
    "owner": "负责人",
    "member": "成员",
}
ARTIFACT_TYPE_OPTIONS = {
    "design_output": "设计输出",
    "structure_model": "结构模型",
    "synthesis_protocol": "合成方案",
    "experimental_result": "实验结果",
    "analysis_report": "分析报告",
    "other": "其他文件",
}
ARTIFACT_GROUPS = [
    ("design_output", "设计输出"),
    ("structure_model", "结构模型"),
    ("synthesis_protocol", "合成文件"),
    ("experimental_result", "实验结果"),
    ("analysis_report", "分析报告"),
    ("other", "其他文件"),
    ("file", "其他文件"),
]
DISPLAY_LABELS = (
    MEMBER_DISCIPLINE_OPTIONS
    | ROLE_LABELS
    | ARTIFACT_TYPE_OPTIONS
    | {"file": "其他文件"}
)


def design_system() -> None:
    ui.add_head_html(
        """
        <style>
        :root {
            --ph-bg: #f6f8fb;
            --ph-surface: #ffffff;
            --ph-surface-soft: #eef7f4;
            --ph-border: #d8e0e7;
            --ph-border-strong: #b9c6d2;
            --ph-text: #14202b;
            --ph-muted: #647484;
            --ph-blue: #2563eb;
            --ph-teal: #0f766e;
            --ph-amber: #d97706;
            --ph-red: #dc2626;
        }

        body {
            background:
                linear-gradient(180deg, #f9fbfd 0%, var(--ph-bg) 38%, #f4f7fa 100%);
            color: var(--ph-text);
        }

        .ph-header {
            background: rgba(255, 255, 255, 0.92) !important;
            border-bottom: 1px solid var(--ph-border);
            box-shadow: 0 1px 8px rgba(20, 32, 43, 0.05);
            backdrop-filter: blur(12px);
        }

        .ph-brand-mark {
            width: 34px;
            height: 34px;
            border-radius: 8px;
            display: grid;
            place-items: center;
            color: white;
            background: linear-gradient(135deg, var(--ph-blue), var(--ph-teal));
            box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
        }

        .ph-page {
            width: min(1180px, calc(100vw - 32px));
            margin: 0 auto;
            padding: 28px 0 44px;
            gap: 24px;
        }

        .ph-page-header {
            align-items: flex-end;
            justify-content: space-between;
            gap: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--ph-border);
        }

        .ph-eyebrow {
            color: var(--ph-teal);
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .ph-title {
            color: var(--ph-text);
            font-size: 28px;
            line-height: 1.2;
            font-weight: 750;
        }

        .ph-subtitle,
        .ph-muted {
            color: var(--ph-muted);
            font-size: 14px;
            line-height: 1.55;
        }

        .ph-grid {
            gap: 16px;
        }

        .ph-resource-card {
            border: 1px solid var(--ph-border);
            border-radius: 8px !important;
            box-shadow: 0 1px 2px rgba(20, 32, 43, 0.04);
            transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
            overflow: hidden;
        }

        .ph-resource-card:hover {
            border-color: var(--ph-border-strong);
            box-shadow: 0 12px 26px rgba(20, 32, 43, 0.08);
            transform: translateY(-1px);
        }

        .ph-protein-card {
            height: 164px;
            min-height: 164px;
            max-height: 164px;
            flex: 0 0 164px;
        }

        .ph-protein-card .ph-card-description,
        .ph-protein-card .ph-card-title {
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .ph-protein-sequence-preview {
            display: block;
            max-width: 100%;
            overflow: hidden;
            line-height: 1.6;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .ph-icon-box {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            display: grid;
            place-items: center;
            flex: 0 0 auto;
        }

        .ph-icon-project { background: #eaf1ff; color: var(--ph-blue); }
        .ph-icon-protein { background: #e7f5f1; color: var(--ph-teal); }
        .ph-icon-artifact { background: #eef2f7; color: #475569; }

        .ph-card-title {
            color: var(--ph-text);
            font-size: 17px;
            font-weight: 700;
            line-height: 1.25;
        }

        .ph-card-description {
            color: var(--ph-muted);
            font-size: 13px;
            line-height: 1.5;
        }

        .ph-meta {
            color: var(--ph-muted);
            font-size: 12px;
        }

        .ph-empty {
            width: 100%;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 42px 18px;
            border: 1px dashed var(--ph-border-strong);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.62);
            color: var(--ph-muted);
            text-align: center;
        }

        .ph-section-bar {
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding-top: 4px;
        }

        .ph-panel {
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
            box-shadow: 0 1px 2px rgba(20, 32, 43, 0.04);
        }

        .ph-workspace-layout {
            display: grid;
            grid-template-columns: 240px minmax(0, 1fr);
            align-items: flex-start;
            gap: 16px;
            --ph-workspace-height: calc(100vh - 240px);
        }

        .ph-project-sidebar {
            width: 240px;
            height: var(--ph-workspace-height);
            min-height: 420px;
            flex: 0 0 240px;
            gap: 12px;
            padding: 24px 14px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.72);
            position: sticky;
            top: 76px;
        }

        .ph-side-tabs {
            align-items: stretch;
        }

        .ph-side-tabs .q-tabs__content {
            gap: 6px;
        }

        .ph-side-tabs .q-tab {
            min-height: 38px;
            justify-content: flex-start;
            border-radius: 8px;
            color: var(--ph-muted);
        }

        .ph-side-tabs .q-tab--active {
            background: #eaf1ff;
            color: var(--ph-blue);
        }

        .ph-side-tabs .q-tab__content {
            width: 100%;
            flex-direction: row;
            justify-content: flex-start;
            gap: 10px;
        }

        .ph-side-tabs .q-tab__icon {
            width: 22px;
            margin: 0;
            font-size: 20px;
        }

        .ph-side-tabs .q-tab__label {
            line-height: 1;
        }

        .ph-workspace-panel {
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.72);
            display: flex;
            flex-direction: column;
            height: var(--ph-workspace-height);
            min-height: 420px;
            grid-column: 2;
            min-width: 0;
            width: 100%;
            overflow: hidden;
            padding: 16px 18px;
            position: sticky;
            top: 76px;
        }

        .ph-workspace-panel > .q-panel {
            height: 100%;
            min-height: 0;
            overflow: hidden;
        }

        .ph-workspace-panel .q-tab-panel {
            height: 100%;
            min-height: 0;
            padding: 0;
        }

        .ph-proteins-panel,
        .ph-members-panel {
            display: flex;
            flex-direction: column;
            gap: 12px;
            min-height: 0;
        }

        .ph-batches-panel {
            display: flex;
            flex-direction: column;
            gap: 12px;
            min-height: 0;
        }

        .ph-proteins-scroll,
        .ph-batch-scroll {
            flex: 1;
            min-height: 0;
            overflow: auto;
            padding-right: 4px;
        }

        .ph-members-scroll {
            flex: 1;
            min-height: 0;
            overflow: auto;
            padding-right: 4px;
        }

        .ph-artifact-group {
            width: 100%;
            gap: 8px;
            padding: 14px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: #fbfcfd;
        }

        .ph-member-row,
        .ph-member-candidate-row,
        .ph-batch-protein-row,
        .ph-file-row {
            width: 100%;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            padding: 14px 16px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-batch-protein-list {
            width: 100%;
            max-height: 360px;
            overflow-y: auto;
            gap: 8px;
            padding: 12px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: #fbfcfd;
        }

        .ph-batch-protein-row {
            padding: 12px 14px;
        }

        .ph-batch-mapping {
            width: 100%;
            overflow: auto;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-batch-mapping-scroll {
            flex: 1;
            min-height: 260px;
            max-height: min(48vh, 520px);
        }

        .ph-batch-upload-actions {
            display: grid;
            grid-template-columns: minmax(220px, 320px) minmax(0, 1fr) auto;
            align-items: center;
            gap: 12px;
        }

        .ph-mapping-row {
            display: grid;
            grid-template-columns: 88px minmax(160px, 1fr) minmax(120px, 0.6fr) minmax(280px, 1.5fr) minmax(100px, 0.5fr);
            min-width: 820px;
            border-bottom: 1px solid var(--ph-border);
        }

        .ph-mapping-row:last-child {
            border-bottom: 0;
        }

        .ph-mapping-head {
            position: sticky;
            top: 0;
            z-index: 1;
            background: #f8fafc;
            color: var(--ph-muted);
            font-size: 12px;
            font-weight: 750;
            text-transform: uppercase;
        }

        .ph-mapping-cell {
            min-width: 0;
            padding: 12px 14px;
            border-right: 1px solid var(--ph-border);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .ph-mapping-cell:last-child {
            border-right: 0;
        }

        .ph-mapping-position {
            color: var(--ph-teal);
            font-weight: 750;
        }

        .ph-mapping-sequence {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
            font-size: 12px;
            color: #334155;
        }

        .ph-member-results {
            width: 100%;
            min-height: 280px;
            max-height: 320px;
            overflow-y: auto;
            gap: 8px;
            padding: 12px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: #fbfcfd;
        }

        .ph-member-candidate-row {
            padding: 12px 14px;
        }

        .ph-sequence-panel {
            width: 100%;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: #fbfcfd;
            overflow: hidden;
        }

        .ph-sequence-text {
            width: 100%;
            padding: 18px;
            color: #23303b;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
            font-size: 13px;
            line-height: 1.85;
            white-space: pre-wrap;
            word-break: break-word;
            display: block;
        }

        .ph-sequence-preview {
            max-height: 58px;
            overflow: hidden;
            line-height: 1.7;
        }

        .ph-dialog-card {
            border-radius: 8px !important;
            border: 1px solid var(--ph-border);
            box-shadow: 0 24px 60px rgba(20, 32, 43, 0.18);
        }

        .ph-login-wrap {
            width: 100vw;
            min-height: 100vh;
            align-items: center;
            justify-content: center;
            padding: 32px;
        }

        .ph-login-panel {
            width: min(420px, 100%);
            gap: 18px;
            padding: 28px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.94);
            box-shadow: 0 18px 48px rgba(20, 32, 43, 0.12);
        }

        .q-field--outlined .q-field__control {
            border-radius: 8px;
        }

        .q-btn {
            border-radius: 8px;
            text-transform: none;
            font-weight: 650;
        }

        .q-badge {
            border-radius: 999px;
            font-weight: 650;
        }

        @media (max-width: 900px) {
            .ph-workspace-layout {
                grid-template-columns: 1fr;
            }

            .ph-project-sidebar {
                width: 100%;
                flex: 0 0 auto;
                height: auto;
                min-height: 0;
                position: static;
            }

            .ph-workspace-panel {
                grid-column: 1;
                height: auto;
                max-height: none;
                overflow: visible;
            }

            .ph-workspace-panel > .q-panel {
                overflow: visible;
            }

            .ph-proteins-scroll,
            .ph-batch-scroll,
            .ph-members-scroll {
                overflow: visible;
            }

            .ph-side-tabs .q-tabs__content {
                flex-direction: row !important;
            }

            .ph-batch-upload-actions {
                grid-template-columns: 1fr;
            }

        }
        </style>
        """
    )


def api_script() -> None:
    ui.add_head_html(
        """
        <script>
        window.phErrorText = function(detail) {
            const messages = {
                'Request failed': '请求失败',
                'Download failed': '下载失败',
                'Upload failed': '上传失败',
            };
            if (Array.isArray(detail)) {
                const items = detail.map((item) => {
                    if (!item) return '';
                    if (typeof item === 'string') return item;
                    if (item.msg) return item.msg;
                    if (item.message) return item.message;
                    return JSON.stringify(item);
                }).filter(Boolean);
                return items.join('；') || '请求参数不完整或格式不正确';
            }
            if (detail && typeof detail === 'object') {
                return detail.message || detail.msg || JSON.stringify(detail);
            }
            return messages[detail] || detail || '请求失败';
        }
        window.phNotify = function(message, type = 'negative') {
            const fallback = type === 'negative' ? '操作失败' : '操作完成';
            const text = message || fallback;
            if (window.Quasar && Quasar.Notify) {
                Quasar.Notify.create({message: text, type});
            } else {
                alert(text);
            }
        }
        window.phNotifyError = function(error, fallback = '操作失败') {
            let detail = error && error.message ? error.message : error;
            if (typeof detail === 'string' && detail.startsWith('Error: ')) {
                detail = detail.slice(7).trim();
            }
            phNotify(phErrorText(detail) || fallback, 'negative');
        }
        window.phApi = async function(path, options = {}) {
            const token = localStorage.getItem('proteinhub_token');
            const headers = options.headers || {};
            if (token) headers.Authorization = `Bearer ${token}`;
            if (options.body && !(options.body instanceof FormData)) {
                headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(options.body);
            }
            let response;
            try {
                response = await fetch(path, {...options, headers});
            } catch (error) {
                throw new Error('无法连接到服务，请检查服务是否正在运行');
            }
            if (response.status === 204) return null;
            const contentType = response.headers.get('content-type') || '';
            let data;
            try {
                data = contentType.includes('application/json') ? await response.json() : await response.text();
            } catch (error) {
                data = '';
            }
            if (!response.ok) {
                const detail = data && data.detail ? data.detail : 'Request failed';
                throw new Error(phErrorText(detail));
            }
            return data;
        }
        window.phSetToken = function(token) {
            localStorage.setItem('proteinhub_token', token);
        }
        window.phClearToken = function() {
            localStorage.removeItem('proteinhub_token');
        }
        window.phToken = function() {
            return localStorage.getItem('proteinhub_token');
        }
        </script>
        """
    )


def sequence_display(sequence: str) -> str:
    groups = [sequence[index : index + 10] for index in range(0, len(sequence), 10)]
    lines = [
        " ".join(groups[index : index + 6])
        for index in range(0, len(groups), 6)
    ]
    return "\n".join(lines)


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} 字节"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} 千字节"
    return f"{size / (1024 * 1024):.1f} 兆字节"


def humanize(value: str | None) -> str:
    if not value:
        return "未指定"
    return DISPLAY_LABELS.get(value, value)


def short_email(email: str | None) -> str:
    if not email:
        return "未分配"
    return email.split("@", 1)[0]


def person_label(name: str | None, email: str | None) -> str:
    if name:
        return name
    return short_email(email)


def empty_state(icon: str, title: str, detail: str) -> None:
    with ui.column().classes("ph-empty"):
        ui.icon(icon).classes("text-3xl text-slate-400")
        ui.label(title).classes("font-semibold text-slate-800")
        ui.label(detail).classes("ph-muted")


def notify_error(error: Exception, fallback: str = "操作失败") -> None:
    message = str(error).strip()
    if message.startswith("Error: "):
        message = message.removeprefix("Error: ").strip()
    ui.notify(message or fallback, type="negative")


def shell() -> None:
    design_system()
    api_script()
    ui.colors(primary="#2563eb", secondary="#0f766e", accent="#f97316")
    with ui.header().classes("ph-header items-center justify-between text-slate-900"):
        with ui.row().classes("items-center gap-3"):
            with ui.element("div").classes("ph-brand-mark"):
                ui.icon("hub").classes("text-lg")
            ui.link("ProteinHub", "/").classes("text-lg font-semibold no-underline text-slate-900")
        with ui.row().classes("items-center gap-2"):
            ui.link("项目", "/projects").classes("text-sm no-underline text-slate-700")
            ui.button("退出登录", on_click=lambda: ui.run_javascript("phClearToken(); window.location.href='/login'")).props("flat dense")


async def ensure_logged_in() -> bool:
    token = await ui.run_javascript("phToken()", timeout=5)
    if not token:
        ui.navigate.to("/login")
        return False
    try:
        await ui.run_javascript("return await phApi('/api/me')")
        return True
    except Exception:
        ui.notify("登录状态已失效，请重新登录", type="warning")
        ui.navigate.to("/login")
        return False


