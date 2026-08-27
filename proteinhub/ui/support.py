from __future__ import annotations

from nicegui import ui


ROLE_LABELS = {
    "admin": "管理员",
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
PROTEIN_TYPE_OPTIONS = {
    "TCR": "TCR",
    "cyclic peptide": "cyclic peptide",
    "nanobody": "nanobody",
    "minibinder": "minibinder",
    "enzymes": "enzymes",
}
PROTEIN_MANUAL_RATING_OPTIONS = {
    "unrated": "未评级",
    "normal": "普通",
    "rare": "稀有",
    "epic": "史诗",
    "legendary": "传说",
}
PLATE_96_POSITION_OPTIONS = {
    f"{row}{column:02d}": f"{row}{column:02d}"
    for row in "ABCDEFGH"
    for column in range(1, 13)
}
TRANSLATION_ORGANISM_OPTIONS = {
    "E. coli": "E. coli",
}
TRANSLATION_RESISTANCE_OPTIONS = {
    "Amp": "Amp",
    "Kan": "Kan",
    "Tet": "Tet",
    "Cam": "Cam",
    "Sep": "Sep",
}
BATCH_ORDER_STATUS_OPTIONS = {
    "not_ordered": "未order",
    "ordered": "已order",
    "partially_received": "部分收货",
    "fully_received": "已全部收到",
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
    ROLE_LABELS
    | ARTIFACT_TYPE_OPTIONS
    | PROTEIN_TYPE_OPTIONS
    | PROTEIN_MANUAL_RATING_OPTIONS
    | BATCH_ORDER_STATUS_OPTIONS
    | {"file": "其他文件"}
)


def protein_manual_rating_label(value: str | None) -> str:
    return PROTEIN_MANUAL_RATING_OPTIONS.get(value or "", "未评级")


def protein_manual_rating_class(value: str | None) -> str:
    normalized = value if value in PROTEIN_MANUAL_RATING_OPTIONS else "unrated"
    return f"ph-protein-rating ph-protein-rating-{normalized}"


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

        .ph-brand-link {
            color: var(--ph-text);
            text-decoration: none;
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
            align-items: stretch;
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

        .ph-project-list {
            gap: 10px;
        }

        .ph-project-status-tabs {
            align-self: flex-start;
            padding: 4px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.78);
        }

        .ph-project-status-tabs .q-tab {
            min-height: 34px;
            border-radius: 6px;
            color: var(--ph-muted);
        }

        .ph-project-status-tabs .q-tab--active {
            background: #eaf1ff;
            color: var(--ph-blue);
        }

        .ph-project-card {
            min-height: 96px;
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 16px;
            align-items: center;
        }

        .ph-project-card-main {
            align-items: center;
            gap: 12px;
            flex: 1 1 auto;
            min-height: 0;
            min-width: 0;
        }

        .ph-project-card-text {
            flex: 1 1 auto;
            min-width: 0;
            gap: 4px;
        }

        .ph-project-card-footer {
            align-items: center;
            justify-content: flex-end;
            gap: 12px;
            margin-top: 0;
            flex: 0 0 auto;
        }

        .ph-project-card .ph-card-title {
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .ph-project-card .ph-card-description {
            overflow: hidden;
            display: -webkit-box;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 2;
        }

        .ph-protein-card {
            min-height: 176px;
            flex: 0 0 auto;
        }

        .ph-protein-card-layout {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 14px;
            align-items: start;
            width: 100%;
            min-width: 0;
        }

        .ph-protein-card-main {
            align-items: flex-start;
            gap: 12px;
            min-width: 0;
        }

        .ph-protein-card-content {
            flex: 1 1 auto;
            min-width: 0;
            gap: 8px;
        }

        .ph-protein-tags {
            align-items: center;
            flex-wrap: wrap;
            gap: 6px;
            min-width: 0;
        }

        .ph-protein-filter-row {
            display: grid;
            grid-template-columns: minmax(180px, 1.2fr) 128px 128px 148px auto auto;
            gap: 8px;
            align-items: end;
            overflow-x: auto;
            padding-bottom: 2px;
        }

        .ph-protein-filter-row .q-btn {
            min-width: 74px;
            white-space: nowrap;
        }

        .ph-protein-card-actions {
            align-items: center;
            justify-content: flex-end;
            gap: 4px;
            flex: 0 0 auto;
        }

        .ph-protein-card-actions .q-btn {
            width: 32px;
            height: 32px;
            border-radius: 999px;
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

        .ph-protein-rating {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 22px;
            padding: 0 8px;
            border-radius: 999px;
            border: 1px solid transparent;
            background-color: transparent !important;
            font-size: 12px;
            line-height: 1.2;
            font-weight: 700;
            white-space: nowrap;
        }

        .ph-protein-rating-unrated {
            background: transparent !important;
            color: #64748b;
            border-color: #cbd5e1;
        }

        .ph-protein-rating-normal {
            background: transparent !important;
            color: #0f172a;
            border-color: #d1d5db;
        }

        .ph-protein-rating-rare {
            background: transparent !important;
            color: #1d4ed8;
            border-color: #93c5fd;
        }

        .ph-protein-rating-epic {
            background: transparent !important;
            color: #7c3aed;
            border-color: #c4b5fd;
        }

        .ph-protein-rating-legendary {
            background: transparent !important;
            color: #a16207;
            border-color: #fcd34d;
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

        .ph-monitor-summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            width: 100%;
        }

        .ph-monitor-stat {
            min-height: 112px;
            padding: 16px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-monitor-stat-value {
            color: var(--ph-text);
            font-size: 28px;
            line-height: 1.1;
            font-weight: 760;
        }

        .ph-monitor-bar-chart {
            display: grid;
            grid-template-columns: repeat(8, minmax(72px, 1fr));
            gap: 10px;
            width: 100%;
            overflow-x: auto;
            align-items: end;
        }

        .ph-monitor-date-input {
            width: 150px;
        }

        .ph-monitor-legend {
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            width: 100%;
        }

        .ph-monitor-legend-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 999px;
        }

        .ph-monitor-chart-column {
            min-width: 72px;
            min-height: 232px;
            align-items: center;
            justify-content: flex-end;
        }

        .ph-monitor-chart-track {
            display: flex;
            align-items: flex-end;
            width: 72px;
            height: 180px;
            border-bottom: 1px solid var(--ph-border-strong);
            background: repeating-linear-gradient(
                to top,
                transparent 0,
                transparent 44px,
                rgba(20, 32, 43, 0.08) 45px
            );
        }

        .ph-monitor-chart-stack {
            width: 100%;
            min-height: 3px;
            border-radius: 5px 5px 0 0;
            display: flex;
            flex-direction: column-reverse;
            overflow: hidden;
        }

        .ph-monitor-chart-segment {
            width: 100%;
            flex-shrink: 0;
        }

        .ph-monitor-chart-empty {
            background: var(--ph-border-strong);
            opacity: 0.18;
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

        .ph-akta-preview {
            width: 100%;
            gap: 12px;
            padding: 14px 16px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-akta-preview-header {
            width: 100%;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
        }

        .ph-akta-preview-frame {
            width: 100%;
            min-height: 180px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: auto;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: #ffffff;
        }

        .ph-akta-preview-content {
            width: 100%;
        }

        .ph-akta-preview-image {
            display: none;
            width: 100%;
            max-height: 560px;
            object-fit: contain;
            background: #ffffff;
        }

        .ph-structure-viewer {
            width: 100%;
            gap: 12px;
            padding: 14px 16px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-structure-viewer-header {
            width: 100%;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
        }

        .ph-structure-viewer-actions {
            align-items: center;
            justify-content: flex-end;
            gap: 6px;
            flex-wrap: wrap;
        }

        .ph-structure-viewer-frame {
            width: 100%;
            height: min(72vh, 720px);
            min-height: 520px;
            position: relative;
            overflow: hidden;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: #ffffff;
        }

        .ph-structure-viewer-frame .msp-plugin {
            position: absolute;
            inset: 0;
        }

        .ph-structure-viewer-status {
            position: absolute;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 18px;
            color: var(--ph-muted);
            text-align: center;
        }

        .ph-akta-preview-status {
            padding: 28px;
            text-align: center;
        }

        .ph-spr-result-grid {
            width: 100%;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 8px 14px;
            padding-top: 2px;
        }

        .ph-spr-result-item {
            min-width: 0;
            display: flex;
            flex-direction: column;
            gap: 2px;
            padding-bottom: 8px;
            border-bottom: 1px solid #e2e8f0;
        }

        .ph-spr-result-key {
            color: var(--ph-muted);
            font-size: 12px;
            line-height: 1.25;
        }

        .ph-spr-result-value {
            color: var(--ph-text);
            font-size: 13px;
            font-weight: 650;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }

        .ph-score-density-grid {
            width: 100%;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 12px;
        }

        .ph-score-density-card {
            width: 100%;
            gap: 10px;
            padding: 14px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-score-density-card-header {
            width: 100%;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }

        .ph-score-density-frame {
            width: 100%;
            overflow: auto;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            background: #ffffff;
            padding: 8px;
        }

        .ph-score-density-svg {
            display: block;
            width: 100%;
            height: auto;
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
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
            overflow-x: auto;
            overflow-y: auto;
            overscroll-behavior: contain;
            scrollbar-gutter: stable;
        }

        .ph-batch-mapping-scroll {
            min-height: 0;
            max-height: min(52vh, 520px);
        }

        .ph-batch-upload-actions {
            display: grid;
            grid-template-columns: minmax(220px, 320px) minmax(0, 1fr) auto;
            align-items: center;
            gap: 12px;
        }

        .ph-spr-upload-actions {
            display: grid;
            grid-template-columns: minmax(220px, 320px) minmax(0, 1fr) auto auto;
            align-items: center;
            gap: 12px;
        }

        .ph-hplc-upload-actions {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            align-items: center;
            gap: 12px;
        }

        .ph-translation-actions {
            display: grid;
            grid-template-columns: minmax(130px, 1fr) minmax(150px, 1fr) minmax(180px, 1fr) minmax(120px, 0.8fr) minmax(120px, 0.8fr) auto;
            align-items: center;
            gap: 12px;
        }

        .ph-mapping-row {
            display: grid;
            grid-template-columns: 128px minmax(160px, 1fr) minmax(120px, 0.6fr) minmax(96px, 0.5fr) minmax(280px, 1.5fr) minmax(100px, 0.5fr) 96px;
            min-width: 1080px;
            border-bottom: 1px solid var(--ph-border);
        }

        .ph-translation-row {
            display: grid;
            grid-template-columns: 88px minmax(160px, 1fr) minmax(92px, 0.4fr) minmax(360px, 1.7fr) minmax(100px, 0.4fr);
            min-width: 900px;
            border-bottom: 1px solid var(--ph-border);
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

        .ph-receipt-well-list {
            width: 100%;
            max-height: 360px;
            overflow-y: auto;
            gap: 8px;
            padding: 12px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: #fbfcfd;
        }

        .ph-receipt-well-row {
            display: grid;
            grid-template-columns: 40px 64px minmax(160px, 1fr) minmax(92px, 0.45fr) minmax(150px, 0.85fr);
            align-items: center;
            gap: 10px;
            width: 100%;
            padding: 10px 12px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
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

        .ph-help-layout {
            display: grid;
            grid-template-columns: 260px minmax(0, 1fr);
            gap: 18px;
            align-items: start;
        }

        .ph-help-sidebar {
            position: sticky;
            top: 76px;
            gap: 12px;
        }

        .ph-help-nav {
            width: 100%;
            gap: 6px;
            padding: 12px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-help-nav-link {
            display: flex;
            align-items: center;
            gap: 8px;
            min-height: 34px;
            padding: 6px 8px;
            border-radius: 8px;
            color: var(--ph-muted);
            font-size: 14px;
            font-weight: 650;
            text-decoration: none;
        }

        .ph-help-nav-link:hover {
            background: #eef7f4;
            color: var(--ph-teal);
        }

        .ph-help-main {
            min-width: 0;
            gap: 14px;
        }

        .ph-help-section {
            width: 100%;
            gap: 14px;
            padding: 18px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-help-section.is-hidden {
            display: none;
        }

        .ph-help-section-head {
            align-items: flex-start;
            gap: 12px;
        }

        .ph-help-step {
            width: 100%;
            display: grid;
            grid-template-columns: minmax(56px, max-content) minmax(0, 1fr);
            gap: 12px;
            align-items: start;
            padding: 12px 0;
            border-top: 1px solid #edf2f7;
        }

        .ph-help-step-marker {
            min-width: 48px;
            min-height: 28px;
            padding: 0 9px;
            display: grid;
            place-items: center;
            border-radius: 8px;
            background: #eaf1ff;
            color: var(--ph-blue);
            font-size: 12px;
            font-weight: 750;
            white-space: nowrap;
        }

        .ph-help-tips {
            gap: 8px;
            padding: 12px 14px;
            border-left: 3px solid var(--ph-teal);
            border-radius: 8px;
            background: #f0fdfa;
        }

        .ph-help-tip {
            color: #115e59;
            font-size: 13px;
            line-height: 1.5;
        }

        .ph-help-empty {
            display: none;
        }

        .ph-help-empty.is-visible {
            display: flex;
        }

        @media (max-width: 900px) {
            .ph-help-layout {
                grid-template-columns: 1fr;
            }

            .ph-help-sidebar {
                position: static;
            }

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

            .ph-project-card {
                grid-template-columns: 1fr;
                align-items: stretch;
            }

            .ph-project-card-main {
                align-items: flex-start;
            }

            .ph-project-card-footer {
                justify-content: space-between;
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

            .ph-spr-upload-actions {
                grid-template-columns: 1fr;
            }

            .ph-hplc-upload-actions {
                grid-template-columns: 1fr;
            }

            .ph-monitor-bar-chart {
                grid-template-columns: repeat(8, minmax(72px, 1fr));
            }

            .ph-monitor-date-input {
                width: 100%;
            }

            .ph-protein-card-layout {
                grid-template-columns: 1fr;
            }

            .ph-protein-card-actions {
                justify-content: flex-start;
                padding-left: 52px;
            }

            .ph-protein-filter-row {
                grid-template-columns: minmax(180px, 1fr) 128px 128px 148px auto auto;
            }

            .ph-translation-actions {
                grid-template-columns: 1fr;
            }

            .ph-structure-viewer-header {
                align-items: flex-start;
                flex-direction: column;
            }

            .ph-structure-viewer-actions {
                justify-content: flex-start;
            }

            .ph-structure-viewer-frame {
                height: 62vh;
                min-height: 380px;
            }

            .ph-batch-mapping-scroll {
                max-height: min(56vh, 420px);
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
        window.phSequenceCheckText = function(check) {
            const items = check && Array.isArray(check.items) ? check.items : [];
            const lines = [];
            let displayedMatches = 0;
            for (const item of items) {
                const matches = Array.isArray(item.matches) ? item.matches : [];
                const parts = matches.slice(0, 3).map((match) => {
                    const label = match.match_type === 'duplicate'
                        ? '重复'
                        : `相似度 ${(Number(match.identity || 0) * 100).toFixed(1)}%`;
                    const scope = match.scope === 'incoming' ? '本次导入' : '已有蛋白';
                    return `${label}: ${scope} ${match.protein_name || ''}`.trim();
                });
                if (parts.length) {
                    lines.push(`${item.name}: ${parts.join('；')}`);
                    displayedMatches += parts.length;
                }
                if (lines.length >= 8) break;
            }
            if (!lines.length) return '';
            const totalMatches = items.reduce(
                (count, item) => count + (Array.isArray(item.matches) ? item.matches.length : 0),
                0,
            );
            const suffix = totalMatches > displayedMatches ? `\\n另有 ${totalMatches - displayedMatches} 条相似记录未显示` : '';
            return lines.join('\\n') + suffix;
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
        window.phStructureViewers = window.phStructureViewers || {};
        window.phLoadMolstar = function() {
            if (window.molstar && window.molstar.Viewer) return Promise.resolve();
            if (window.phMolstarScriptPromise) return window.phMolstarScriptPromise;
            window.phMolstarScriptPromise = new Promise((resolve, reject) => {
                if (!document.querySelector('link[data-ph-molstar-css]')) {
                    const link = document.createElement('link');
                    link.rel = 'stylesheet';
                    link.href = 'https://cdn.jsdelivr.net/npm/molstar@5.4.2/build/viewer/molstar.css';
                    link.dataset.phMolstarCss = 'true';
                    document.head.appendChild(link);
                }
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/molstar@5.4.2/build/viewer/molstar.js';
                script.async = true;
                script.onload = () => window.molstar && window.molstar.Viewer
                    ? resolve()
                    : reject(new Error('Mol* Viewer 加载失败'));
                script.onerror = () => reject(new Error('Mol* Viewer 加载失败'));
                document.head.appendChild(script);
            });
            return window.phMolstarScriptPromise;
        }
        window.phWaitForElement = async function(id, attempts = 30) {
            for (let attempt = 0; attempt < attempts; attempt += 1) {
                const element = document.getElementById(id);
                if (element) return element;
                await new Promise((resolve) => setTimeout(resolve, 50));
            }
            return null;
        }
        window.phStructureFileExtension = function(filename, mimeType) {
            const name = String(filename || '').toLowerCase();
            const mime = String(mimeType || '').toLowerCase();
            if (name.endsWith('.cif') || name.endsWith('.mmcif') || mime.includes('cif')) {
                return 'mmcif';
            }
            return 'pdb';
        }
        window.phSetStructureViewerStatus = function(container, text) {
            container.innerHTML = '';
            const status = document.createElement('div');
            status.className = 'ph-structure-viewer-status';
            status.textContent = text;
            container.appendChild(status);
        }
        window.phRenderProteinStructure = async function(config) {
            const container = await phWaitForElement(config.containerId);
            if (!container) return false;
            phSetStructureViewerStatus(container, '正在加载 3D 结构...');
            try {
                await phLoadMolstar();
                const token = phToken();
                const headers = token ? {Authorization: `Bearer ${token}`} : {};
                const response = await fetch(config.downloadPath, {headers});
                if (!response.ok) {
                    let detail = '结构文件加载失败';
                    try {
                        const data = await response.json();
                        detail = data && data.detail ? phErrorText(data.detail) : detail;
                    } catch (error) {}
                    throw new Error(detail);
                }
                const structureText = await response.text();
                const previous = phStructureViewers[config.containerId];
                if (previous && previous.viewer) previous.viewer.dispose();
                container.innerHTML = '';
                const viewer = await window.molstar.Viewer.create(config.containerId, {
                    layoutIsExpanded: false,
                    layoutShowControls: true,
                    layoutShowSequence: true,
                    layoutShowLog: false,
                    layoutShowRemoteState: false,
                    layoutShowLeftPanel: true,
                    viewportShowExpand: true,
                    viewportShowSelectionMode: true,
                    viewportShowAnimation: false,
                });
                await viewer.loadStructureFromData(structureText, phStructureFileExtension(config.filename, config.mimeType), {
                    dataLabel: config.filename || 'structure',
                });
                phStructureViewers[config.containerId] = {viewer};
                setTimeout(() => {
                    const updated = viewer.plugin.layout
                        && viewer.plugin.layout.events
                        && viewer.plugin.layout.events.updated;
                    if (updated && updated.next) updated.next();
                }, 100);
                return true;
            } catch (error) {
                const message = error && error.message ? error.message : '结构文件加载失败';
                phSetStructureViewerStatus(container, message);
                return false;
            }
        }
        window.phResetProteinStructureView = function(containerId) {
            const viewer = phStructureViewers[containerId];
            if (!viewer || !viewer.viewer) return false;
            const camera = viewer.viewer.plugin.managers.camera;
            if (camera && camera.reset) camera.reset(undefined, 250);
            return true;
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
        window.phSyncAdminLinks = async function() {
            const links = document.querySelectorAll('.ph-admin-only');
            try {
                const user = await phApi('/api/me');
                const isAdmin = user && user.global_role === 'admin';
                links.forEach((link) => link.classList.toggle('hidden', !isAdmin));
            } catch (error) {
                links.forEach((link) => link.classList.add('hidden'));
            }
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


def format_datetime_minute(value: str | None) -> str:
    text = (value or "").strip().replace("T", " ")
    if len(text) >= 16 and text[4] == "-" and text[7] == "-" and text[13] == ":":
        return text[:16]
    return text


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
        with ui.link(target="/projects").classes("ph-brand-link"):
            with ui.row().classes("items-center gap-3 no-wrap"):
                with ui.element("div").classes("ph-brand-mark"):
                    ui.icon("hub").classes("text-lg")
                ui.label("ProteinHub").classes("text-lg font-semibold")
        with ui.row().classes("items-center gap-2"):
            ui.link("项目", "/projects").classes("text-sm no-underline text-slate-700")
            ui.link("订单监控", "/order-monitor").classes(
                "text-sm no-underline text-slate-700 ph-admin-only hidden"
            )
            ui.link("序列搜索", "/admin/sequences").classes(
                "text-sm no-underline text-slate-700 ph-admin-only hidden"
            )
            ui.link("帮助", "/help").classes("text-sm no-underline text-slate-700")
            ui.button("退出登录", on_click=lambda: ui.run_javascript("phClearToken(); window.location.href='/login'")).props("flat dense")
    ui.add_body_html(
        "<script>setTimeout(() => window.phSyncAdminLinks && window.phSyncAdminLinks(), 0)</script>"
    )


async def ensure_logged_in() -> bool:
    token = await ui.run_javascript("phToken()", timeout=5)
    if not token:
        ui.navigate.to("/login")
        return False
    try:
        await ui.run_javascript("return await phApi('/api/me')")
        await ui.run_javascript(
            "window.phSyncAdminLinks && window.phSyncAdminLinks()",
            timeout=5,
        )
        return True
    except Exception:
        ui.notify("登录状态已失效，请重新登录", type="warning")
        ui.navigate.to("/login")
        return False
