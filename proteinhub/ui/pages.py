from __future__ import annotations
from html import escape as html_escape
import json
from datetime import date, timedelta
from urllib.parse import urlencode

from nicegui import ui

from proteinhub.ui.support import (
    ARTIFACT_GROUPS,
    BATCH_ORDER_STATUS_OPTIONS,
    PLATE_96_POSITION_OPTIONS,
    PROTEIN_MANUAL_RATING_OPTIONS,
    PROTEIN_TYPE_OPTIONS,
    ROLE_LABELS,
    TRANSLATION_ORGANISM_OPTIONS,
    TRANSLATION_RESISTANCE_OPTIONS,
    api_script,
    design_system,
    empty_state,
    ensure_logged_in,
    format_bytes,
    format_datetime_minute,
    humanize,
    notify_error,
    person_label,
    protein_manual_rating_class,
    protein_manual_rating_label,
    sequence_display,
    shell,
)


TRANSLATION_REQUEST_TIMEOUT_SECONDS = 420
PROTEIN_LIST_SORT_OPTIONS = {
    "time_desc": "时间新到旧",
    "time_asc": "时间旧到新",
    "rating_desc": "评级高到低",
    "rating_asc": "评级低到高",
}
ORDER_MONITOR_STATUS_SEGMENTS = (
    ("ordered_count", "已 order", "#2563eb"),
    ("partially_received_count", "部分收货", "#f97316"),
    ("fully_received_count", "全部收货", "#94a3b8"),
)
ORDER_MONITOR_RANK_PERIOD_LABELS = {
    "today": "Today",
    "month": "1 Month",
}
PROJECT_STATUS_LABELS = {
    "active": "活跃",
    "archived": "归档",
    "trash": "回收站",
}
PROJECT_STATUS_ICONS = {
    "active": "folder_open",
    "archived": "inventory_2",
    "trash": "delete",
}
PROJECT_STATUS_BADGE_COLORS = {
    "active": "positive",
    "archived": "secondary",
    "trash": "negative",
}
PROJECT_STATUS_EMPTY_STATES = {
    "active": ("folder_open", "还没有活跃项目", "新建一个项目后，就可以开始收集蛋白。"),
    "archived": ("inventory_2", "还没有归档项目", "归档后的项目会显示在这里。"),
    "trash": ("delete", "回收站为空", "移入回收站的项目会显示在这里。"),
}
ADMIN_SEQUENCE_SOURCE_LABELS = {
    "batch_protein": "已进批次",
    "public_protein": "工具蛋白",
}
ADMIN_SEQUENCE_SOURCE_ICONS = {
    "batch_protein": "science",
    "public_protein": "biotech",
}
ADMIN_ACCOUNT_STATUS_OPTIONS = {
    "all": "全部状态",
    "active": "启用",
    "disabled": "禁用",
}
ADMIN_USER_ROLE_FILTER_OPTIONS = {
    "all": "全部角色",
    "admin": "管理员",
    "user": "普通用户",
}
ADMIN_USER_ROLE_OPTIONS = {
    "user": "普通用户",
    "admin": "管理员",
}
HELP_SECTIONS = (
    {
        "id": "quick-start",
        "icon": "rocket_launch",
        "eyebrow": "开始使用",
        "title": "快速开始",
        "summary": "用一条最短路径建立项目、蛋白和第一批实验记录。",
        "keywords": "快速 开始 项目 蛋白 批次 实验",
        "steps": (
            ("1", "创建项目", "进入“项目”页面，新建一个项目。项目是数据和权限的边界。"),
            ("2", "添加成员", "项目负责人可以在项目工作台的成员区域添加协作者，并设置成员角色。"),
            ("3", "导入设计蛋白", "从 PDB/mmCIF 新建或批量导入设计蛋白；导入后可以在蛋白详情页查看结构和资料。"),
            ("4", "创建批次", "在项目工作台选择蛋白创建 96 孔板批次，系统会记录孔位与蛋白的映射关系。"),
            ("5", "上传实验", "进入批次详情页，根据实验类型上传 HPLC、SPR 或 AKTA 文件。"),
        ),
        "tips": (
            "先建立项目和成员，再导入设计蛋白；后续的批次、实验和资料都会继承项目权限。",
            "实验结果生成后，可以从蛋白详情页查看对应的实验图和下载文件。",
        ),
    },
    {
        "id": "protein-batch",
        "icon": "science",
        "eyebrow": "核心流程",
        "title": "蛋白与批次",
        "summary": "理解 ProteinHub 中蛋白、孔位、批次和实验结果之间的关系。",
        "keywords": "蛋白 批次 96孔 孔位 结构 序列 结果",
        "steps": (
            ("1", "蛋白是核心记录", "每个蛋白包含名称、氨基酸序列、可选 DNA 序列、结构文件和关联资料。"),
            ("2", "批次组织实验", "Batch 表示一次 96 孔板实验集合；创建时会把项目内蛋白映射到孔位。"),
            ("3", "实验挂在批次下", "SPR、HPLC、AKTA 等实验记录属于某个批次，并通过孔位回到具体蛋白。"),
            ("4", "从蛋白查看结果", "蛋白详情页的“批次结果”和“实验资料”会汇总这个蛋白关联的结果、图表和文件。"),
        ),
        "tips": (
            "结果上传后不要随意修改孔位；已经产生结果的批次会限制孔位变更。",
            "如果看不到某个蛋白或批次，先确认自己是否属于对应项目。",
        ),
    },
    {
        "id": "experiment-files",
        "icon": "upload_file",
        "eyebrow": "文件格式",
        "title": "实验文件怎么准备",
        "summary": "上传前先确认孔位识别、文件格式和配套文件，解析失败通常来自这几处。",
        "keywords": "文件 格式 上传 HPLC SPR AKTA PDB mmCIF vial_fc csv pptx zip 色块",
        "steps": (
            ("HPLC", "HPLC 文件", "需要 chromatogram CSV 和 vial_fc.csv。chromatogram 文件名中需要有唯一孔位，例如 `A1.csv`、`A01.csv` 或 `...-A1-result.dx_DAD1A.CSV`；固定馏分映射文件必须命名为 `vial_fc.csv`。"),
            ("SPR", "SPR 文件", "结果文件上传 `.pptx`；浓度表单独上传 `.csv`。样品标签中需要有唯一孔位，例如 `A1XXX`、`A01XXX` 或 `sample-A1XXX`。"),
            ("AKTA", "AKTA 文件", "上传 zip 文件，文件名中需要有唯一孔位，例如 `A1.zip`、`A01.zip` 或 `run-A1-result.zip`。服务器需要配置 AKTA 渲染脚本和 Python 环境。"),
            ("结构", "结构文件", "PDB/mmCIF 文件可以单个创建蛋白，也可以在项目中批量导入。"),
        ),
        "tips": (
            "HPLC 的起始时间和终止时间差小于 0.01 分钟的区间不会绘制成色块，但原始解析记录仍会保留。",
            "上传失败时先检查扩展名、名称中的孔位、同一名称里是否出现多个孔位，以及是否把同一孔位重复上传。",
        ),
    },
    {
        "id": "permissions",
        "icon": "admin_panel_settings",
        "eyebrow": "权限",
        "title": "角色和数据权限",
        "summary": "所有业务数据都按项目隔离，权限不足时不会显示项目内容。",
        "keywords": "权限 角色 管理员 负责人 成员 下载 删除 项目",
        "steps": (
            ("管理员", "全局管理员", "可以查看项目列表，并执行项目删除等管理员操作。"),
            ("负责人", "项目负责人", "可以管理成员，并删除项目内普通资料文件。"),
            ("成员", "项目成员", "可以查看项目内容，创建批次、上传实验和回填结果。"),
            ("下载", "资料下载", "结构文件、实验图和 artifact 下载都需要通过项目权限校验。"),
        ),
        "tips": (
            "项目删除会连带删除项目下的蛋白、批次、实验和资料记录，属于不可逆操作。",
            "不要把生产环境的管理员邮箱和开发环境混用；上线前确认 PROTEINHUB_ADMIN_EMAILS。",
        ),
    },
    {
        "id": "troubleshooting",
        "icon": "build",
        "eyebrow": "排查问题",
        "title": "常见问题",
        "summary": "遇到上传、权限或结果显示问题时，可以按下面顺序检查。",
        "keywords": "故障 排查 上传失败 看不到项目 HPLC SPR AKTA 图表 服务器 日志",
        "steps": (
            ("项目", "看不到项目", "确认当前登录邮箱已被项目负责人添加为成员，并重新登录刷新权限。"),
            ("HPLC", "HPLC 上传失败", "确认包含 `vial_fc.csv`，chromatogram 文件名能识别出批次中的唯一孔位，且样品名能在 vial 文件中找到。"),
            ("SPR", "SPR 没有结果", "确认 PPTX 使用了系统支持的结果页结构，样品标签能唯一映射到 A1、A01、A02 等孔位。"),
            ("AKTA", "AKTA 上传失败", "确认 zip 文件名中能识别出唯一孔位，并检查服务器上的 AKTA Python 和脚本路径配置。"),
            ("图表", "图表没有显示", "先刷新蛋白详情页；如果仍然失败，检查原始文件是否成功上传以及服务器日志。"),
        ),
        "tips": (
            "服务器部署后，优先查看应用服务日志和 PostgreSQL 连接状态。",
            "提交问题时最好附上实验类型、文件名和错误提示，不要直接上传包含敏感数据的完整文件到聊天工具。",
        ),
    },
)


def _is_akta_png_artifact(artifact: dict) -> bool:
    filename = artifact.get("filename", "")
    return (
        artifact.get("artifact_type") == "experimental_result"
        and artifact.get("mime_type") == "image/png"
        and filename.startswith("AKTA_")
        and filename.lower().endswith(".png")
    )


def _is_spr_svg_artifact(artifact: dict) -> bool:
    filename = artifact.get("filename", "")
    return (
        artifact.get("artifact_type") == "experimental_result"
        and artifact.get("mime_type") == "image/svg+xml"
        and filename.startswith("SPR_")
        and filename.lower().endswith(".svg")
    )


def _is_hplc_svg_artifact(artifact: dict) -> bool:
    filename = artifact.get("filename", "")
    return (
        artifact.get("artifact_type") == "experimental_result"
        and artifact.get("mime_type") == "image/svg+xml"
        and filename.startswith("HPLC_")
        and filename.lower().endswith(".svg")
    )


def _run_date_from_prefixed_filename(filename: str, prefix: str) -> str:
    if not filename.startswith(prefix):
        return ""
    parts = filename.split("_")
    if len(parts) < 3:
        return ""
    try:
        return date.fromisoformat(parts[1]).isoformat()
    except ValueError:
        return ""


def _preview_meta(*values: str) -> str:
    return " · ".join(value for value in values if value)


def _spr_result_notes_by_artifact_id(batch_results: list[dict]) -> dict[int, dict]:
    notes = {}
    for result in batch_results:
        if result.get("experiment_type") != "SPR" or not result.get("result_note"):
            continue
        try:
            note = json.loads(result["result_note"])
        except (TypeError, ValueError):
            continue
        if not isinstance(note, dict) or note.get("source") != "SPR":
            continue
        artifact_id = note.get("chart_artifact_id")
        if isinstance(artifact_id, int):
            notes[artifact_id] = note
    return notes


def _hplc_result_notes_by_artifact_id(batch_results: list[dict]) -> dict[int, dict]:
    notes = {}
    for result in batch_results:
        if result.get("experiment_type") != "HPLC" or not result.get("result_note"):
            continue
        try:
            note = json.loads(result["result_note"])
        except (TypeError, ValueError):
            continue
        if not isinstance(note, dict) or note.get("source") != "HPLC":
            continue
        artifact_id = note.get("chart_artifact_id")
        if isinstance(artifact_id, int):
            notes[artifact_id] = note
    return notes


def _hplc_display_items(note: dict | None) -> list[tuple[str, str]]:
    if not note:
        return []
    items = []
    if note.get("sample_key"):
        items.append(("样品", str(note["sample_key"])))
    if note.get("plate_position"):
        items.append(("孔位", str(note["plate_position"])))
    block_count = note.get("block_count")
    if isinstance(block_count, int):
        items.append(("色块", f"{block_count} 个"))
    return items


def _spr_table_display_items(table_row: dict | None) -> list[tuple[str, str]]:
    if not table_row:
        return []
    preferred_keys = [
        "Single cycle kinetics 1 Solution",
        "Quality Kinetics Chi² (RU²)",
        "1:1 binding ka (1/Ms)",
        "kd (1/s)",
        "KD (M)",
        "Rmax (RU)",
        "tc",
    ]
    return [
        (key, str(table_row[key]))
        for key in preferred_keys
        if table_row.get(key) not in (None, "")
    ]


def _batch_result_note_text(result: dict) -> str:
    note = result.get("result_note") or ""
    if result.get("experiment_type") == "AKTA":
        try:
            parsed = json.loads(note)
        except (TypeError, ValueError):
            return note
        if not isinstance(parsed, dict) or parsed.get("source") != "AKTA":
            return note
        bits = [str(parsed.get("run_date") or "AKTA")]
        if parsed.get("png_artifact_id"):
            bits.append(f"PNG #{parsed['png_artifact_id']}")
        return " · ".join(bits)
    if result.get("experiment_type") == "SPR":
        try:
            parsed = json.loads(note)
        except (TypeError, ValueError):
            return note
        if not isinstance(parsed, dict) or parsed.get("source") != "SPR":
            return note
        table_row = parsed.get("table_row") or {}
        bits = [str(parsed.get("sample_id") or "SPR")]
        if parsed.get("run_date"):
            bits.append(str(parsed["run_date"]))
        for key in ("KD (M)", "Rmax (RU)"):
            if table_row.get(key):
                bits.append(f"{key} {table_row[key]}")
        return " · ".join(bits)
    if result.get("experiment_type") == "HPLC":
        try:
            parsed = json.loads(note)
        except (TypeError, ValueError):
            return note
        if not isinstance(parsed, dict) or parsed.get("source") != "HPLC":
            return note
        bits = [str(parsed.get("sample_key") or "HPLC")]
        if parsed.get("plate_position"):
            bits.append(str(parsed["plate_position"]))
        block_count = parsed.get("block_count")
        if isinstance(block_count, int):
            bits.append(f"{block_count} 个色块")
        return " · ".join(bits)
    return note


def _format_order_date(value: str | None) -> str:
    if not value:
        return "未记录"
    return value[:10]


def _format_days_since(value: int | None) -> str:
    if value is None:
        return "未记录"
    if value == 0:
        return "今天"
    return f"{value} 天前"


def _sequence_similarity_scope_label(scope: str | None) -> str:
    if scope == "existing":
        return "已有蛋白"
    if scope == "incoming":
        return "本次导入"
    return "未知来源"


def _sequence_similarity_type_label(match_type: str | None) -> str:
    if match_type == "duplicate":
        return "重复"
    return "高相似度"


def _sequence_similarity_identity_label(match: dict) -> str:
    try:
        identity = float(match.get("identity") or 0)
    except (TypeError, ValueError):
        identity = 0
    return f"{identity * 100:.1f}%"


def _project_member_badge_text(project: dict) -> str:
    members = project.get("members") or []
    member_count = int(project.get("member_count") or len(members))
    if member_count <= 0:
        return ""
    names = [person_label(member.get("name"), member.get("email")) for member in members]
    if not names:
        return f"成员 {member_count} 人"
    display_names = names[:3]
    suffix = f"等 {member_count} 人" if member_count > len(display_names) else ""
    return f"成员 {'、'.join(display_names)}{suffix}"


def _project_member_tooltip(project: dict) -> str:
    members = project.get("members") or []
    return "\n".join(
        f"{person_label(member.get('name'), member.get('email'))} <{member.get('email')}>"
        for member in members
    )


def _project_status_label(status: str | None) -> str:
    return PROJECT_STATUS_LABELS.get(status or "active", "活跃")


def _project_status_badge_color(status: str | None) -> str:
    return PROJECT_STATUS_BADGE_COLORS.get(status or "active", "positive")


def _admin_sequence_source_label(source_type: str | None) -> str:
    return ADMIN_SEQUENCE_SOURCE_LABELS.get(source_type or "", "序列")


def _admin_sequence_source_icon(source_type: str | None) -> str:
    return ADMIN_SEQUENCE_SOURCE_ICONS.get(source_type or "", "search")


def _admin_user_role_badge_color(role: str | None) -> str:
    return "primary" if role == "admin" else "secondary"


def _admin_user_time_text(value: str | None) -> str:
    return format_datetime_minute(value) if value else "未记录"


def _render_sequence_similarity_badge(protein: dict, open_dialog) -> None:
    if protein.get("sequence_similarity_status") != "high_similarity":
        return
    badge = ui.badge("高相似度").props("outline color=warning").classes("cursor-pointer")
    badge.on("click", lambda p=protein: open_dialog(p))
    with badge:
        ui.tooltip("查看相似蛋白")


def _render_sequence_similarity_matches(protein: dict, container) -> None:
    matches = protein.get("sequence_similarity_matches") or []
    container.clear()
    with container:
        if not matches:
            ui.label("没有保存的相似蛋白详情。").classes("ph-muted")
            return
        for match in matches:
            with ui.row().classes("ph-file-row items-start no-wrap"):
                with ui.column().classes("min-w-0 flex-1 gap-1"):
                    ui.label(match.get("protein_name") or "未命名蛋白").classes("font-medium break-all")
                    ui.label(
                        f"{_sequence_similarity_scope_label(match.get('scope'))} · "
                        f"{_sequence_similarity_type_label(match.get('match_type'))} · "
                        f"相似度 {_sequence_similarity_identity_label(match)}"
                    ).classes("ph-meta")
                protein_id = match.get("protein_id")
                if protein_id:
                    ui.button(
                        "打开",
                        icon="open_in_new",
                        on_click=lambda target_id=protein_id: ui.navigate.to(
                            f"/proteins/{target_id}"
                        ),
                    ).props("flat dense no-wrap").classes("shrink-0")


def _cadence_badge_color(status: str) -> str:
    if status == "on_track":
        return "positive"
    if status == "overdue":
        return "warning"
    return "secondary"



def install_ui() -> None:
    @ui.page("/")
    async def index() -> None:
        if await ensure_logged_in():
            ui.navigate.to("/projects")

    @ui.page("/login")
    def login_page() -> None:
        design_system()
        api_script()
        ui.colors(primary="#2563eb", secondary="#0f766e", accent="#f97316")
        with ui.column().classes("ph-login-wrap"):
            with ui.column().classes("ph-login-panel"):
                with ui.row().classes("items-center gap-3"):
                    with ui.element("div").classes("ph-brand-mark"):
                        ui.icon("hub").classes("text-lg")
                    with ui.column().classes("gap-0"):
                        ui.label("ProteinHub").classes("text-2xl font-semibold text-slate-900")
                        ui.label("以蛋白为中心的信息与实验资料库").classes("ph-muted")
                email = ui.input("邮箱").props("outlined").classes("w-full")
                password = ui.input("密码", password=True, password_toggle_button=True).props("outlined").classes("w-full")

                async def submit() -> None:
                    body = {"email": email.value, "password": password.value}
                    try:
                        result = await ui.run_javascript(
                            f"return await phApi('/api/auth/login', {{method: 'POST', body: {json.dumps(body)}}})",
                            timeout=10,
                        )
                        await ui.run_javascript(f"phSetToken({result['access_token']!r})")
                        ui.navigate.to("/projects")
                    except Exception as error:
                        notify_error(error)

                ui.button("继续", on_click=submit).classes("w-full").props("unelevated")

    @ui.page("/help")
    async def help_page() -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("使用指南").classes("ph-eyebrow")
                    ui.label("帮助").classes("ph-title")
                    ui.label("按常见工作流整理 ProteinHub 的操作、文件格式和权限。").classes("ph-subtitle")
                ui.button(
                    "返回项目",
                    icon="folder_open",
                    on_click=lambda: ui.navigate.to("/projects"),
                ).props("flat")

            with ui.element("div").classes("ph-help-layout w-full"):
                with ui.column().classes("ph-help-sidebar"):
                    help_search = ui.input(
                        "搜索帮助",
                        placeholder="例如 HPLC、权限、AKTA",
                    ).props("outlined clearable dense").classes("w-full")
                    with ui.column().classes("ph-help-nav"):
                        ui.label("目录").classes("text-sm font-semibold text-slate-800")
                        for section in HELP_SECTIONS:
                            with ui.link(target=f"#{section['id']}").classes("ph-help-nav-link"):
                                ui.icon(section["icon"]).classes("text-base")
                                ui.label(section["title"])

                help_topics = ui.column().classes("ph-help-main")

            def matches_query(section: dict, query: str) -> bool:
                if not query:
                    return True
                haystack = " ".join(
                    [
                        str(section["title"]),
                        str(section["summary"]),
                        str(section["keywords"]),
                        " ".join(
                            " ".join(step)
                            for step in section["steps"]
                        ),
                        " ".join(section["tips"]),
                    ]
                ).lower()
                return query in haystack

            def render_help(query: str | None = None) -> None:
                normalized_query = (query or "").strip().lower()
                visible_sections = [
                    section
                    for section in HELP_SECTIONS
                    if matches_query(section, normalized_query)
                ]
                help_topics.clear()
                with help_topics:
                    if not visible_sections:
                        empty_state("search_off", "没有匹配的帮助条目", "换一个关键词试试看。")
                        return
                    for section in visible_sections:
                        with ui.element("section").props(f"id={section['id']}").classes("ph-help-section"):
                            with ui.row().classes("ph-help-section-head w-full"):
                                with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                    ui.icon(section["icon"])
                                with ui.column().classes("min-w-0 gap-1"):
                                    ui.label(section["eyebrow"]).classes("ph-eyebrow")
                                    ui.label(section["title"]).classes("text-xl font-semibold text-slate-900")
                                    ui.label(section["summary"]).classes("ph-muted")
                            with ui.column().classes("w-full gap-0"):
                                for marker, title, detail in section["steps"]:
                                    with ui.element("div").classes("ph-help-step"):
                                        ui.label(marker).classes("ph-help-step-marker")
                                        with ui.column().classes("min-w-0 gap-1"):
                                            ui.label(title).classes("font-semibold text-slate-800")
                                            ui.label(detail).classes("ph-muted")
                            with ui.column().classes("ph-help-tips w-full"):
                                for tip in section["tips"]:
                                    ui.label(tip).classes("ph-help-tip")

            help_search.on_value_change(lambda event: render_help(event.value))
            render_help()

    @ui.page("/projects")
    async def projects_page() -> None:
        shell()
        if not await ensure_logged_in():
            return
        try:
            current_user = await ui.run_javascript("return await phApi('/api/me')", timeout=10)
        except Exception as error:
            notify_error(error)
            return
        is_admin_user = current_user.get("global_role") == "admin"
        visible_project_statuses = ["active", "archived"]
        if is_admin_user:
            visible_project_statuses.append("trash")
        project_view_state = {"status": "active"}
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("工作台").classes("ph-eyebrow")
                    ui.label("项目").classes("ph-title")
                    ui.label("项目权限会保护每个蛋白记录和实验资料。").classes("ph-subtitle")
                ui.button("新建项目", icon="add", on_click=lambda: project_dialog.open()).props("unelevated")

            def select_project_status(event) -> None:
                project_view_state["status"] = str(event.value or "active")
                return load_projects()

            with ui.tabs(
                value="active",
                on_change=select_project_status,
            ).classes("ph-project-status-tabs") as status_tabs:
                for status in visible_project_statuses:
                    ui.tab(
                        status,
                        label=PROJECT_STATUS_LABELS[status],
                        icon=PROJECT_STATUS_ICONS[status],
                    )

            project_list = ui.column().classes("ph-project-list w-full")
            project_delete_target = {"project": None}

            def selected_project_status() -> str:
                return str(project_view_state["status"] or "active")

            async def load_projects(status: str | None = None) -> None:
                try:
                    status = status or selected_project_status()
                    endpoint = f"/api/projects?{urlencode({'status': status})}"
                    projects = await ui.run_javascript(
                        f"return await phApi({json.dumps(endpoint)})",
                        timeout=10,
                    )
                    project_list.clear()
                    with project_list:
                        if not projects:
                            empty_state(*PROJECT_STATUS_EMPTY_STATES[status])
                        for project in projects:
                            with ui.card().classes("ph-resource-card ph-project-card w-full p-4"):
                                with ui.row().classes("ph-project-card-main w-full"):
                                    with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                        ui.icon(PROJECT_STATUS_ICONS.get(project.get("status"), "folder_open"))
                                    with ui.column().classes("ph-project-card-text"):
                                        ui.label(project["name"]).classes("ph-card-title")
                                        ui.label(project["description"] or "暂无描述").classes("ph-card-description")
                                        with ui.row().classes("items-center gap-2 flex-wrap"):
                                            ui.badge(
                                                _project_status_label(project.get("status"))
                                            ).props(
                                                f"outline color={_project_status_badge_color(project.get('status'))}"
                                            )
                                            owner_badge = ui.badge(
                                                f"负责人 {person_label(project.get('owner_name'), project.get('owner_email'))}"
                                            ).props("outline color=primary").classes("max-w-full")
                                            if project.get("owner_email"):
                                                with owner_badge:
                                                    ui.tooltip(project["owner_email"])
                                            member_badge_text = _project_member_badge_text(project)
                                            if member_badge_text:
                                                member_badge = ui.badge(member_badge_text).props(
                                                    "outline color=secondary"
                                                ).classes("max-w-full whitespace-normal")
                                                member_tooltip = _project_member_tooltip(project)
                                                if member_tooltip:
                                                    with member_badge:
                                                        ui.tooltip(member_tooltip)
                                with ui.row().classes("ph-project-card-footer"):
                                    if is_admin_user:
                                        status_button = ui.button(
                                            icon="published_with_changes",
                                        ).props("flat round dense color=primary")
                                        with status_button:
                                            ui.tooltip("调整状态")
                                            with ui.menu():
                                                for next_status in PROJECT_STATUS_LABELS:
                                                    item = ui.menu_item(
                                                        PROJECT_STATUS_LABELS[next_status],
                                                        on_click=lambda s=next_status, p=project: update_selected_project_status(p, s),
                                                    )
                                                    if next_status == project.get("status", "active"):
                                                        item.disable()
                                        delete_button = ui.button(
                                            icon="delete",
                                            on_click=lambda p=project: open_delete_project(p),
                                        ).props("flat round dense color=negative")
                                        with delete_button:
                                            ui.tooltip("删除项目")
                                    ui.button("打开", icon="arrow_forward", on_click=lambda p=project: ui.navigate.to(f"/projects/{p['id']}")).props("flat")
                except Exception as error:
                    notify_error(error)

            with ui.dialog() as project_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("新建项目").classes("text-lg font-semibold")
                name = ui.input("名称").props("outlined").classes("w-full")
                description = ui.textarea("描述").props("outlined").classes("w-full")

                async def create() -> None:
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/projects', {{method: 'POST', body: {{name: {name.value!r}, description: {description.value!r}}}}})",
                            timeout=10,
                        )
                        project_dialog.close()
                        name.value = ""
                        description.value = ""
                        project_view_state["status"] = "active"
                        status_tabs.value = "active"
                        await load_projects("active")
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=project_dialog.close).props("flat")
                    ui.button("创建", icon="add", on_click=create)

            with ui.dialog() as delete_project_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                delete_project_title = ui.label().classes("text-lg font-semibold")
                ui.label("删除后项目内的蛋白、批次、实验和资料记录会一并移除。").classes("ph-muted")

                async def delete_selected_project() -> None:
                    project = project_delete_target["project"]
                    if not project:
                        return
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project['id']}', {{method: 'DELETE'}})",
                            timeout=10,
                        )
                        delete_project_dialog.close()
                        project_delete_target["project"] = None
                        ui.notify("项目已删除", type="positive")
                        await load_projects()
                    except Exception as error:
                        notify_error(error)

                async def update_selected_project_status(project: dict, status: str) -> None:
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project['id']}/status', {{method: 'PATCH', body: {{status: {status!r}}}}})",
                            timeout=10,
                        )
                        ui.notify("项目状态已更新", type="positive")
                        await load_projects()
                    except Exception as error:
                        notify_error(error)

                def open_delete_project(project: dict) -> None:
                    project_delete_target["project"] = project
                    delete_project_title.text = f"删除项目：{project['name']}"
                    delete_project_dialog.open()

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=delete_project_dialog.close).props("flat")
                    ui.button("删除", icon="delete", on_click=delete_selected_project).props("unelevated color=negative")

            await load_projects()

    @ui.page("/order-monitor")
    async def order_monitor_page() -> None:
        shell()
        if not await ensure_logged_in():
            return
        default_end_date = date.today()
        default_start_date = default_end_date - timedelta(
            days=default_end_date.weekday(),
            weeks=7,
        )
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("管理员").classes("ph-eyebrow")
                    ui.label("订单监控").classes("ph-title")
                    ui.label("跟踪批次 order 时间和最近每周订单节奏。").classes("ph-subtitle")
                refresh_button = ui.button(
                    "刷新",
                    icon="refresh",
                    on_click=lambda: load_monitor(),
                ).props("unelevated no-wrap")

            summary_grid = ui.element("div").classes("ph-monitor-summary-grid")
            with ui.element("div").classes("ph-order-dashboard w-full"):
                with ui.column().classes("ph-panel ph-order-dashboard-pane gap-3 p-4"):
                    with ui.row().classes("ph-section-bar w-full"):
                        with ui.column().classes("gap-0"):
                            ui.label("负责人 Rank").classes("text-xl font-semibold")
                            owner_rank_range_label = ui.label("Today").classes("ph-muted")
                        owner_rank_period = ui.toggle(
                            ORDER_MONITOR_RANK_PERIOD_LABELS,
                            value="today",
                            on_change=lambda event: render_owner_rankings(),
                        ).props("toggle-color=primary unelevated")
                    owner_rank_column = ui.column().classes("w-full gap-2")
                with ui.column().classes("ph-panel ph-order-dashboard-pane gap-3 p-4"):
                    with ui.row().classes("ph-section-bar w-full"):
                        with ui.column().classes("gap-0"):
                            ui.label("批次收货进度").classes("text-xl font-semibold")
                            ui.label("等待最久优先").classes("ph-muted")
                    receipt_progress_column = ui.column().classes("w-full gap-3")
            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label("按周 order 批次数").classes("text-xl font-semibold")
                        chart_range_label = ui.label("最近 8 个自然周").classes("ph-muted")
                    with ui.row().classes("items-end gap-2"):
                        monitor_start_date = ui.input(
                            "起始日期",
                            value=default_start_date.isoformat(),
                        ).props("outlined dense type=date").classes("ph-monitor-date-input")
                        monitor_end_date = ui.input(
                            "终止日期",
                            value=default_end_date.isoformat(),
                        ).props("outlined dense type=date").classes("ph-monitor-date-input")
                        query_button = ui.button(
                            "查询",
                            icon="search",
                            on_click=lambda: load_monitor(),
                        ).props("unelevated no-wrap")
                        reset_button = ui.button(
                            "重置",
                            icon="restart_alt",
                            on_click=lambda: reset_monitor_range(),
                        ).props("flat no-wrap")
                with ui.row().classes("ph-monitor-legend"):
                    for _count_key, label, color in ORDER_MONITOR_STATUS_SEGMENTS:
                        with ui.row().classes("items-center gap-1"):
                            ui.element("span").classes("ph-monitor-legend-dot").style(
                                f"background: {color};"
                            )
                            ui.label(label).classes("ph-meta")
                week_chart = ui.element("div").classes("ph-monitor-bar-chart")

            def render_stat(title_text: str, value_text: str, detail_text: str) -> None:
                with ui.column().classes("ph-monitor-stat gap-2"):
                    ui.label(title_text).classes("ph-meta")
                    ui.label(value_text).classes("ph-monitor-stat-value")
                    ui.label(detail_text).classes("ph-card-description")

            def render_summary(summary: dict) -> None:
                summary_grid.clear()
                with summary_grid:
                    render_stat(
                        "已 order 批次",
                        str(summary["total_ordered_batches"]),
                        f"{summary['total_ordered_proteins']} 个蛋白",
                    )
                    render_stat(
                        "上次 order",
                        _format_order_date(summary.get("last_ordered_at")),
                        _format_days_since(summary.get("days_since_last_order")),
                    )
                    with ui.column().classes("ph-monitor-stat gap-2"):
                        ui.label("订单节奏").classes("ph-meta")
                        ui.label(summary["cadence_text"]).classes("ph-monitor-stat-value")
                        ui.badge(
                            f"目标 {summary['cadence_target_days']} 天内",
                        ).props(f"outline color={_cadence_badge_color(summary['cadence_status'])}")

            monitor_payload_state: dict[str, dict] = {"value": {}}

            def render_owner_rankings() -> None:
                payload = monitor_payload_state["value"]
                period = owner_rank_period.value or "today"
                rankings = (payload.get("owner_rankings") or {}).get(period) or []
                owner_rank_range_label.text = ORDER_MONITOR_RANK_PERIOD_LABELS.get(
                    period,
                    "Today",
                )
                owner_rank_column.clear()
                max_protein_count = max(
                    (int(ranking.get("protein_count") or 0) for ranking in rankings),
                    default=0,
                )
                with owner_rank_column:
                    if not rankings:
                        empty_state("leaderboard", "暂无排行", "这个时间范围内还没有订单。")
                        return
                    for index, ranking in enumerate(rankings, start=1):
                        protein_count = int(ranking.get("protein_count") or 0)
                        batch_count = int(ranking.get("batch_count") or 0)
                        width = (
                            (protein_count / max_protein_count) * 100
                            if max_protein_count
                            else 0
                        )
                        with ui.element("div").classes("ph-owner-rank-row"):
                            ui.label(str(index)).classes("ph-owner-rank-number")
                            with ui.column().classes("min-w-0 gap-1"):
                                ui.label(
                                    person_label(
                                        ranking.get("owner_name"),
                                        ranking.get("owner_email"),
                                    )
                                ).classes("font-semibold text-slate-900")
                                with ui.element("div").classes("ph-owner-rank-track"):
                                    ui.element("div").classes("ph-owner-rank-fill").style(
                                        f"width: {width:.1f}%;"
                                    )
                                ui.label(f"{batch_count} 个批次").classes("ph-meta")
                            ui.label(f"{protein_count}").classes("ph-owner-rank-value")

            def render_receipt_progress(batches: list[dict]) -> None:
                receipt_progress_column.clear()
                with receipt_progress_column:
                    if not batches:
                        empty_state("inventory_2", "暂无已 order 批次", "批次进入 order 后会显示收货进度。")
                        return
                    for batch in batches:
                        well_count = int(batch.get("well_count") or 0)
                        received_count = int(batch.get("received_well_count") or 0)
                        percent = float(batch.get("receipt_progress_percent") or 0)
                        percent = min(max(percent, 0), 100)
                        with ui.element("div").classes("ph-receipt-progress-card"):
                            with ui.row().classes("w-full items-start justify-between gap-3"):
                                with ui.column().classes("min-w-0 gap-1"):
                                    ui.label(batch["name"]).classes("font-semibold text-slate-900")
                                    ui.label(
                                        f"{batch['project_name']} · "
                                        f"{person_label(batch.get('owner_name'), batch.get('owner_email'))}"
                                    ).classes("ph-meta")
                                open_button = ui.button(
                                    icon="open_in_new",
                                    on_click=lambda b=batch: ui.navigate.to(f"/batches/{b['id']}"),
                                ).props("flat round dense")
                                with open_button:
                                    ui.tooltip("打开批次")
                            with ui.element("div").classes("ph-receipt-progress-track"):
                                ui.element("div").classes("ph-receipt-progress-fill").style(
                                    f"width: {percent:.1f}%;"
                                )
                            with ui.row().classes("w-full items-center justify-between gap-3"):
                                ui.label(
                                    f"{received_count}/{well_count} 已收货 · {percent:.0f}%"
                                ).classes("ph-meta")
                                ui.label(
                                    f"{_format_order_date(batch.get('ordered_at'))} · "
                                    f"{_format_days_since(batch.get('days_since_order'))}"
                                ).classes("ph-meta")

            def render_weeks(weeks: list[dict]) -> None:
                week_chart.clear()
                max_count = max((week["order_count"] for week in weeks), default=0)
                with week_chart:
                    for week in weeks:
                        order_count = week["order_count"]
                        height = (order_count / max_count) * 100 if max_count else 0
                        with ui.column().classes("ph-monitor-chart-column gap-2"):
                            ui.label(str(order_count)).classes("font-semibold text-slate-900")
                            with ui.element("div").classes("ph-monitor-chart-track"):
                                if order_count:
                                    with ui.element("div").classes("ph-monitor-chart-stack").style(
                                        f"height: {height:.1f}%;"
                                    ):
                                        for count_key, label, color in ORDER_MONITOR_STATUS_SEGMENTS:
                                            count = int(week.get(count_key) or 0)
                                            if not count:
                                                continue
                                            segment_height = (count / order_count) * 100
                                            ui.element("div").classes("ph-monitor-chart-segment").style(
                                                f"height: {segment_height:.1f}%; background: {color};"
                                            ).props(f'title="{label}: {count}"')
                                else:
                                    ui.element("div").classes(
                                        "ph-monitor-chart-stack ph-monitor-chart-empty"
                                    )
                            ui.label(week["week_label"]).classes("ph-meta")

            async def load_monitor() -> None:
                try:
                    refresh_button.disable()
                    query = urlencode(
                        {
                            key: value
                            for key, value in {
                                "start_date": monitor_start_date.value,
                                "end_date": monitor_end_date.value,
                            }.items()
                            if value
                        }
                    )
                    endpoint = "/api/order-monitor"
                    if query:
                        endpoint = f"{endpoint}?{query}"
                    payload = await ui.run_javascript(
                        f"return await phApi({json.dumps(endpoint)})",
                        timeout=10,
                    )
                    chart_range_label.text = (
                        f"{payload['range_start']} 至 {payload['range_end']}"
                    )
                    monitor_payload_state["value"] = payload
                    render_summary(payload["summary"])
                    render_owner_rankings()
                    render_receipt_progress(
                        payload.get("batch_receipt_progress") or payload["batches"]
                    )
                    render_weeks(payload["weekly_orders"])
                except Exception as error:
                    notify_error(error)
                finally:
                    refresh_button.enable()

            async def reset_monitor_range() -> None:
                monitor_start_date.value = default_start_date.isoformat()
                monitor_end_date.value = default_end_date.isoformat()
                await load_monitor()

            await load_monitor()

    @ui.page("/admin/sequences")
    async def admin_sequences_page() -> None:
        shell()
        if not await ensure_logged_in():
            return

        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("管理员").classes("ph-eyebrow")
                    ui.label("序列搜索").classes("ph-title")
                    ui.label("搜索已进批次的设计蛋白和工具蛋白序列。").classes("ph-subtitle")
                refresh_button = ui.button(
                    "刷新",
                    icon="refresh",
                    on_click=lambda: load_sequences(),
                ).props("unelevated no-wrap")

            with ui.row().classes("ph-panel w-full items-end gap-3 p-4"):
                sequence_query = ui.input(
                    "序列片段",
                    placeholder="ACDEFG",
                ).props("outlined clearable").classes("min-w-[260px] flex-1")
                search_button = ui.button(
                    "搜索",
                    icon="search",
                    on_click=lambda: load_sequences(),
                ).props("unelevated no-wrap")
                ui.button(
                    "清空",
                    icon="restart_alt",
                    on_click=lambda: reset_sequence_search(),
                ).props("flat no-wrap")

            results_column = ui.column().classes("w-full gap-3")
            sequence_page_size = 100
            sequence_page_state = {"offset": 0}
            load_more_button = ui.button(
                "加载更多",
                icon="expand_more",
                on_click=lambda: load_more_sequences(),
            ).props("flat no-wrap")
            load_more_button.visible = False

            def render_sequence_result(result: dict) -> None:
                sequence = result.get("sequence") or ""
                preview = sequence[:90] + ("..." if len(sequence) > 90 else "")
                source_type = result.get("source_type") or ""
                source_color = "primary" if source_type == "batch_protein" else "secondary"
                with ui.card().classes("ph-resource-card ph-protein-card w-full p-4"):
                    with ui.element("div").classes("ph-protein-card-layout"):
                        with ui.row().classes("ph-protein-card-main"):
                            with ui.element("div").classes("ph-icon-box ph-icon-protein"):
                                ui.icon(_admin_sequence_source_icon(source_type))
                            with ui.column().classes("ph-protein-card-content"):
                                with ui.column().classes("w-full gap-1"):
                                    ui.label(result["name"]).classes("ph-card-title")
                                    with ui.row().classes("ph-protein-tags"):
                                        ui.badge(
                                            _admin_sequence_source_label(source_type)
                                        ).props(f"outline color={source_color}")
                                        ui.badge(
                                            _project_status_label(result.get("project_status"))
                                        ).props(
                                            f"outline color={_project_status_badge_color(result.get('project_status'))}"
                                        )
                                        if result.get("protein_type"):
                                            ui.badge(result["protein_type"]).props("outline")
                                        if result.get("target"):
                                            ui.badge(
                                                f"靶标 {result['target']}"
                                            ).props("outline color=secondary")
                                batch_text = ""
                                if result.get("batch_count"):
                                    batch_text = f" · {result['batch_count']} 个批次"
                                ui.label(
                                    f"项目 {result['project_name']} · "
                                    f"{result['sequence_length']} 个氨基酸"
                                    f"{batch_text}"
                                ).classes("ph-meta")
                                ui.label(preview).classes(
                                    "ph-protein-sequence-preview font-mono text-sm text-slate-700"
                                )
                        open_button = ui.button(
                            icon="open_in_new",
                            on_click=lambda path=result["detail_path"]: ui.navigate.to(path),
                        ).props("flat round dense")
                        with open_button:
                            ui.tooltip("打开详情")

            async def load_sequences() -> None:
                await fetch_sequences(reset=True)

            async def load_more_sequences() -> None:
                await fetch_sequences(reset=False)

            async def fetch_sequences(*, reset: bool) -> None:
                if reset:
                    sequence_page_state["offset"] = 0
                    load_more_button.visible = False
                    results_column.clear()
                    with results_column:
                        ui.label("正在加载序列...").classes("ph-muted")
                try:
                    search_button.disable()
                    refresh_button.disable()
                    load_more_button.disable()
                    params = {
                        "limit": sequence_page_size,
                        "offset": sequence_page_state["offset"],
                    }
                    if sequence_query.value:
                        params["q"] = sequence_query.value
                    endpoint = f"/api/admin/sequences?{urlencode(params)}"
                    results = await ui.run_javascript(
                        f"return await phApi({json.dumps(endpoint)})",
                        timeout=10,
                    )
                    if reset:
                        results_column.clear()
                    with results_column:
                        if reset and not results:
                            if sequence_query.value:
                                empty_state("search_off", "没有匹配序列", "换一段序列试试看。")
                            else:
                                empty_state("science", "还没有可搜索序列", "已进批次的设计蛋白和工具蛋白会显示在这里。")
                        for result in results:
                            render_sequence_result(result)
                    sequence_page_state["offset"] += len(results)
                    load_more_button.visible = len(results) == sequence_page_size
                except Exception as error:
                    if reset:
                        results_column.clear()
                        with results_column:
                            empty_state("lock", "无法加载序列", "请确认当前账号具有管理员权限。")
                    notify_error(error)
                finally:
                    search_button.enable()
                    refresh_button.enable()
                    load_more_button.enable()

            async def reset_sequence_search() -> None:
                sequence_query.value = ""
                await load_sequences()

            await load_sequences()

    @ui.page("/admin/users")
    async def admin_users_page() -> None:
        shell()
        if not await ensure_logged_in():
            return
        try:
            current_user = await ui.run_javascript(
                "return await phApi('/api/me')",
                timeout=10,
            )
        except Exception as error:
            notify_error(error)
            return
        if current_user.get("global_role") != "admin":
            ui.notify("只有管理员可以访问账户管理", type="warning")
            ui.navigate.to("/projects")
            return

        current_user_id = int(current_user["id"])
        selected_user_state: dict[str, dict | None] = {"user": None}
        temporary_password_state = {"value": ""}

        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("管理员").classes("ph-eyebrow")
                    ui.label("账户管理").classes("ph-title")
                    ui.label("创建账号、调整角色，并禁用不再使用的账号。").classes("ph-subtitle")
                with ui.row().classes("gap-2"):
                    refresh_button = ui.button(
                        "刷新",
                        icon="refresh",
                        on_click=lambda: load_users(),
                    ).props("flat no-wrap")
                    ui.button(
                        "新建账号",
                        icon="person_add",
                        on_click=lambda: open_create_user_dialog(),
                    ).props("unelevated no-wrap")

            with ui.element("div").classes("ph-panel ph-admin-user-filters w-full p-4"):
                user_query = ui.input(
                    "姓名或邮箱",
                    placeholder="name@example.com",
                ).props("outlined clearable dense")
                status_filter = ui.select(
                    ADMIN_ACCOUNT_STATUS_OPTIONS,
                    value="all",
                    label="状态",
                ).props("outlined dense")
                role_filter = ui.select(
                    ADMIN_USER_ROLE_FILTER_OPTIONS,
                    value="all",
                    label="角色",
                ).props("outlined dense")
                search_button = ui.button(
                    "搜索",
                    icon="search",
                    on_click=lambda: load_users(),
                ).props("unelevated no-wrap")
                ui.button(
                    "重置",
                    icon="restart_alt",
                    on_click=lambda: reset_user_filters(),
                ).props("flat no-wrap")

            users_column = ui.column().classes("w-full gap-3")

            def render_user(user: dict) -> None:
                is_active = bool(user.get("is_active", True))
                global_role = user.get("global_role") or "user"
                status_label = "启用" if is_active else "禁用"
                status_color = "positive" if is_active else "negative"
                is_self = int(user["id"]) == current_user_id
                with ui.card().classes("ph-resource-card ph-admin-user-row w-full p-4"):
                    with ui.row().classes("ph-admin-user-main w-full"):
                        with ui.element("div").classes("ph-icon-box ph-icon-project"):
                            ui.icon("admin_panel_settings" if global_role == "admin" else "person")
                        with ui.column().classes("min-w-0 flex-1 gap-2"):
                            with ui.row().classes("items-center gap-2 flex-wrap"):
                                ui.label(person_label(user.get("name"), user.get("email"))).classes("ph-card-title")
                                ui.badge(ROLE_LABELS.get(global_role, global_role)).props(
                                    f"outline color={_admin_user_role_badge_color(global_role)}"
                                )
                                ui.badge(status_label).props(f"outline color={status_color}")
                                if is_self:
                                    ui.badge("当前账号").props("outline color=primary")
                            ui.label(user["email"]).classes("ph-card-description")
                            with ui.element("div").classes("ph-admin-user-metadata"):
                                ui.label(
                                    f"创建 {format_datetime_minute(user.get('created_at')) or '未知'}"
                                ).classes("ph-meta")
                                ui.label(
                                    f"最后登录 {_admin_user_time_text(user.get('last_login_at'))}"
                                ).classes("ph-meta")
                                ui.label(
                                    f"密码更新 {_admin_user_time_text(user.get('password_updated_at'))}"
                                ).classes("ph-meta")
                                if not is_active:
                                    disabled_by = person_label(
                                        user.get("disabled_by_name"),
                                        user.get("disabled_by_email"),
                                    )
                                    ui.label(
                                        f"禁用 {format_datetime_minute(user.get('disabled_at')) or '未知'} · {disabled_by}"
                                    ).classes("ph-meta")
                                    if user.get("disabled_reason"):
                                        ui.label(f"原因 {user['disabled_reason']}").classes("ph-meta")
                    with ui.row().classes("ph-admin-user-actions"):
                        edit_button = ui.button(
                            icon="edit",
                            on_click=lambda u=user: open_edit_user_dialog(u),
                        ).props("flat round dense")
                        with edit_button:
                            ui.tooltip("编辑账号")
                        reset_button = ui.button(
                            icon="lock_reset",
                            on_click=lambda u=user: reset_user_password(u),
                        ).props("flat round dense")
                        with reset_button:
                            ui.tooltip("重置密码")
                        if is_active:
                            disable_button = ui.button(
                                icon="person_off",
                                on_click=lambda u=user: open_disable_user_dialog(u),
                            ).props("flat round dense color=negative")
                            if is_self:
                                disable_button.disable()
                            with disable_button:
                                ui.tooltip("禁用账号" if not is_self else "不能禁用当前账号")
                        else:
                            enable_button = ui.button(
                                icon="person",
                                on_click=lambda u=user: enable_user(u),
                            ).props("flat round dense color=positive")
                            with enable_button:
                                ui.tooltip("启用账号")

            async def load_users() -> None:
                users_column.clear()
                with users_column:
                    ui.label("正在加载账户...").classes("ph-muted")
                try:
                    search_button.disable()
                    refresh_button.disable()
                    params = {
                        "q": user_query.value or "",
                        "status": status_filter.value or "all",
                        "global_role": role_filter.value or "all",
                    }
                    endpoint = f"/api/admin/users?{urlencode(params)}"
                    users = await ui.run_javascript(
                        f"return await phApi({json.dumps(endpoint)})",
                        timeout=10,
                    )
                    users_column.clear()
                    with users_column:
                        if not users:
                            empty_state("manage_accounts", "没有匹配账户", "换一个关键词或筛选条件试试看。")
                        for user in users:
                            render_user(user)
                except Exception as error:
                    users_column.clear()
                    with users_column:
                        empty_state("lock", "无法加载账户", "请确认当前账号具有管理员权限。")
                    notify_error(error)
                finally:
                    search_button.enable()
                    refresh_button.enable()

            async def reset_user_filters() -> None:
                user_query.value = ""
                status_filter.value = "all"
                role_filter.value = "all"
                await load_users()

            def open_create_user_dialog() -> None:
                create_user_name.value = ""
                create_user_email.value = ""
                create_user_role.value = "user"
                create_user_dialog.open()

            async def create_user_from_dialog() -> None:
                payload = {
                    "name": create_user_name.value or "",
                    "email": create_user_email.value or "",
                    "global_role": create_user_role.value or "user",
                }
                try:
                    result = await ui.run_javascript(
                        f"return await phApi('/api/admin/users', "
                        f"{{method: 'POST', body: {json.dumps(payload)}}})",
                        timeout=10,
                    )
                    create_user_dialog.close()
                    show_temporary_password("账号已创建", result["user"], result["temporary_password"])
                    await load_users()
                except Exception as error:
                    notify_error(error)

            def open_edit_user_dialog(user: dict) -> None:
                selected_user_state["user"] = user
                edit_user_title.text = f"编辑账号：{person_label(user.get('name'), user.get('email'))}"
                edit_user_name.value = user.get("name") or ""
                edit_user_role.value = user.get("global_role") or "user"
                edit_user_dialog.open()

            async def update_user_from_dialog() -> None:
                user = selected_user_state["user"]
                if not user:
                    return
                payload = {
                    "name": edit_user_name.value or "",
                    "global_role": edit_user_role.value or "user",
                }
                try:
                    result = await ui.run_javascript(
                        f"return await phApi('/api/admin/users/{user['id']}', "
                        f"{{method: 'PATCH', body: {json.dumps(payload)}}})",
                        timeout=10,
                    )
                    edit_user_dialog.close()
                    selected_user_state["user"] = None
                    ui.notify(f"{person_label(result.get('name'), result.get('email'))} 已更新", type="positive")
                    await load_users()
                except Exception as error:
                    notify_error(error)

            def open_disable_user_dialog(user: dict) -> None:
                selected_user_state["user"] = user
                disable_user_title.text = f"禁用账号：{person_label(user.get('name'), user.get('email'))}"
                disable_user_reason.value = ""
                disable_user_dialog.open()

            async def disable_user_from_dialog() -> None:
                user = selected_user_state["user"]
                if not user:
                    return
                payload = {"reason": disable_user_reason.value or ""}
                try:
                    result = await ui.run_javascript(
                        f"return await phApi('/api/admin/users/{user['id']}/disable', "
                        f"{{method: 'POST', body: {json.dumps(payload)}}})",
                        timeout=10,
                    )
                    disable_user_dialog.close()
                    selected_user_state["user"] = None
                    ui.notify(f"{person_label(result.get('name'), result.get('email'))} 已禁用", type="positive")
                    await load_users()
                except Exception as error:
                    notify_error(error)

            async def enable_user(user: dict) -> None:
                try:
                    result = await ui.run_javascript(
                        f"return await phApi('/api/admin/users/{user['id']}/enable', "
                        "{method: 'POST'})",
                        timeout=10,
                    )
                    ui.notify(f"{person_label(result.get('name'), result.get('email'))} 已启用", type="positive")
                    await load_users()
                except Exception as error:
                    notify_error(error)

            async def reset_user_password(user: dict) -> None:
                try:
                    result = await ui.run_javascript(
                        f"return await phApi('/api/admin/users/{user['id']}/reset-password', "
                        "{method: 'POST'})",
                        timeout=10,
                    )
                    show_temporary_password("密码已重置", result["user"], result["temporary_password"])
                    await load_users()
                except Exception as error:
                    notify_error(error)

            def show_temporary_password(title: str, user: dict, password: str) -> None:
                temporary_password_state["value"] = password
                temporary_password_title.text = title
                temporary_password_user.text = (
                    f"{person_label(user.get('name'), user.get('email'))} · {user.get('email')}"
                )
                temporary_password_label.text = password
                temporary_password_dialog.open()

            async def copy_temporary_password() -> None:
                password = temporary_password_state["value"]
                if not password:
                    ui.notify("没有可复制的临时密码", type="warning")
                    return
                try:
                    await ui.run_javascript(
                        f"await navigator.clipboard.writeText({json.dumps(password)}); return true",
                        timeout=5,
                    )
                    ui.notify("临时密码已复制", type="positive")
                except Exception as error:
                    notify_error(error)

            with ui.dialog() as create_user_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("新建账号").classes("text-lg font-semibold")
                create_user_name = ui.input("姓名").props("outlined").classes("w-full")
                create_user_email = ui.input("邮箱").props("outlined").classes("w-full")
                create_user_role = ui.select(
                    ADMIN_USER_ROLE_OPTIONS,
                    value="user",
                    label="角色",
                ).props("outlined").classes("w-full")
                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=create_user_dialog.close).props("flat")
                    ui.button(
                        "创建",
                        icon="person_add",
                        on_click=create_user_from_dialog,
                    ).props("unelevated")

            with ui.dialog() as edit_user_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                edit_user_title = ui.label().classes("text-lg font-semibold")
                edit_user_name = ui.input("姓名").props("outlined").classes("w-full")
                edit_user_role = ui.select(
                    ADMIN_USER_ROLE_OPTIONS,
                    value="user",
                    label="角色",
                ).props("outlined").classes("w-full")
                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=edit_user_dialog.close).props("flat")
                    ui.button("保存", icon="save", on_click=update_user_from_dialog).props("unelevated")

            with ui.dialog() as disable_user_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                disable_user_title = ui.label().classes("text-lg font-semibold")
                disable_user_reason = ui.textarea(
                    "原因",
                    placeholder="例如：成员离职或账号暂时停用",
                ).props("outlined autogrow").classes("w-full")
                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=disable_user_dialog.close).props("flat")
                    ui.button(
                        "禁用",
                        icon="person_off",
                        on_click=disable_user_from_dialog,
                    ).props("unelevated color=negative")

            with ui.dialog() as temporary_password_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                temporary_password_title = ui.label().classes("text-lg font-semibold")
                temporary_password_user = ui.label().classes("ph-muted")
                temporary_password_label = ui.label().classes("ph-temp-password")
                with ui.row().classes("justify-end w-full"):
                    ui.button(
                        "复制",
                        icon="content_copy",
                        on_click=copy_temporary_password,
                    ).props("flat")
                    ui.button("完成", on_click=temporary_password_dialog.close).props("unelevated")

            await load_users()

    @ui.page("/public-proteins/{public_protein_id}")
    async def public_protein_page(public_protein_id: int) -> None:
        shell()
        if not await ensure_logged_in():
            return
        state = {"project_id": None}

        def open_project() -> None:
            if state["project_id"]:
                ui.navigate.to(f"/projects/{state['project_id']}")
            else:
                ui.run_javascript("history.back()")

        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("工具蛋白").classes("ph-eyebrow")
                    public_protein_title = ui.label("工具蛋白").classes("ph-title")
                    public_protein_description = ui.label().classes("ph-subtitle")
                with ui.column().classes("items-end gap-2"):
                    ui.button(
                        "返回项目",
                        icon="arrow_back",
                        on_click=open_project,
                    ).props("flat")
                    public_protein_meta = ui.row().classes("gap-2")

            with ui.column().classes("ph-sequence-panel"):
                with ui.row().classes("w-full items-center justify-between border-b border-slate-200 px-4 py-3"):
                    ui.label("氨基酸序列").classes("font-semibold text-slate-800")
                    public_sequence_length_badge = ui.badge().props("outline")
                public_sequence_text = ui.label().classes("ph-sequence-text")

            public_details_column = ui.column().classes("ph-panel w-full gap-3 p-4")

            async def load_public_protein() -> None:
                public_details_column.clear()
                with public_details_column:
                    ui.label("正在加载工具蛋白...").classes("ph-muted")
                try:
                    data = await ui.run_javascript(
                        f"return await phApi('/api/public-proteins/{public_protein_id}')",
                        timeout=10,
                    )
                    public_protein = data["public_protein"]
                    state["project_id"] = public_protein["project_id"]
                    public_protein_title.text = public_protein["name"]
                    public_protein_description.text = (
                        public_protein["description"] or "暂无描述"
                    )
                    public_sequence_text.text = sequence_display(public_protein["sequence"])
                    public_sequence_length_badge.text = (
                        f"{len(public_protein['sequence'])} 个氨基酸"
                    )
                    public_protein_meta.clear()
                    with public_protein_meta:
                        if public_protein.get("project_name"):
                            ui.badge(
                                f"项目 {public_protein['project_name']}"
                            ).props("outline color=primary")
                        ui.badge(
                            _project_status_label(public_protein.get("project_status"))
                        ).props(
                            f"outline color={_project_status_badge_color(public_protein.get('project_status'))}"
                        )
                        if public_protein.get("protein_type"):
                            ui.badge(public_protein["protein_type"]).props("outline")
                        if public_protein.get("target"):
                            ui.badge(
                                f"靶标 {public_protein['target']}"
                            ).props("outline color=secondary")
                    public_details_column.clear()
                    with public_details_column:
                        with ui.row().classes("ph-section-bar w-full"):
                            with ui.column().classes("gap-0"):
                                ui.label("记录信息").classes("text-xl font-semibold")
                                ui.label("工具蛋白用于工具酶、对照蛋白或通用序列。").classes("ph-muted")
                        with ui.row().classes("ph-file-row w-full"):
                            with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                with ui.element("div").classes("ph-icon-box ph-icon-protein"):
                                    ui.icon("person")
                                with ui.column().classes("min-w-0 gap-1"):
                                    ui.label(
                                        person_label(
                                            public_protein.get("created_by_name"),
                                            public_protein.get("created_by_email"),
                                        )
                                    ).classes("font-semibold text-slate-900")
                                    ui.label(
                                        public_protein.get("created_by_email") or "未记录邮箱"
                                    ).classes("ph-meta")
                        with ui.row().classes("ph-file-row w-full"):
                            with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                with ui.element("div").classes("ph-icon-box ph-icon-artifact"):
                                    ui.icon("schedule")
                                with ui.column().classes("min-w-0 gap-1"):
                                    ui.label("创建与更新").classes("font-semibold text-slate-900")
                                    ui.label(
                                        f"创建 {format_datetime_minute(public_protein.get('created_at'))} · "
                                        f"更新 {format_datetime_minute(public_protein.get('updated_at'))}"
                                    ).classes("ph-meta")
                except Exception as error:
                    public_details_column.clear()
                    with public_details_column:
                        empty_state("error", "工具蛋白加载失败", "请稍后重试或返回项目页。")
                    notify_error(error)

            await load_public_protein()

    @ui.page("/projects/{project_id}")
    async def project_page(project_id: int) -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("项目").classes("ph-eyebrow")
                    title = ui.label("项目").classes("ph-title")
                    description = ui.label().classes("ph-subtitle")
                with ui.row().classes("items-center gap-2"):
                    status_badge = ui.badge().props("outline")
                    role_badge = ui.badge().props("outline")

            with ui.row().classes("ph-workspace-layout w-full"):
                with ui.column().classes("ph-project-sidebar"):
                    with ui.column().classes("gap-1"):
                        ui.label("项目视图").classes("ph-eyebrow")
                        ui.label("浏览项目内容").classes("font-semibold text-slate-900")
                    with ui.tabs().props("vertical").classes("ph-side-tabs w-full") as tabs:
                        proteins_tab = ui.tab("设计蛋白", icon="science")
                        public_proteins_tab = ui.tab("工具蛋白", icon="biotech")
                        batches_tab = ui.tab("实验批次", icon="grid_view")
                        members_tab = ui.tab("成员", icon="group")
                with ui.tab_panels(tabs, value=proteins_tab).classes("ph-panel ph-workspace-panel"):
                    with ui.tab_panel(proteins_tab).classes("ph-proteins-panel"):
                        with ui.row().classes("ph-section-bar w-full"):
                            with ui.column().classes("gap-0"):
                                ui.label("设计蛋白").classes("text-xl font-semibold")
                                ui.label("查询和管理这个项目中进入批次和实验流程的蛋白。").classes("ph-muted")
                            with ui.row().classes("gap-2"):
                                bulk_import_button = ui.button("批量导入", icon="drive_folder_upload", on_click=lambda: bulk_import_dialog.open()).props("flat no-wrap")
                                new_protein_button = ui.button("新建设计蛋白", icon="add", on_click=lambda: protein_dialog.open()).props("unelevated no-wrap")
                        with ui.row().classes("ph-protein-filter-row w-full"):
                            protein_rating_filter = (
                                ui.select(
                                    PROTEIN_MANUAL_RATING_OPTIONS,
                                    value=[],
                                    label="评级",
                                    multiple=True,
                                )
                                .props("outlined dense use-chips clearable")
                                .classes("w-full")
                            )
                            protein_date_from = (
                                ui.input("开始日期")
                                .props("outlined dense type=date")
                                .classes("w-full")
                            )
                            protein_date_to = (
                                ui.input("结束日期")
                                .props("outlined dense type=date")
                                .classes("w-full")
                            )
                            protein_sort_select = (
                                ui.select(
                                    PROTEIN_LIST_SORT_OPTIONS,
                                    value="time_desc",
                                    label="排序",
                                )
                                .props("outlined dense")
                                .classes("w-full")
                            )
                            ui.button(
                                "筛选",
                                icon="filter_alt",
                                on_click=lambda: load_proteins(),
                            ).props("flat no-wrap")
                            ui.button(
                                "重置",
                                icon="restart_alt",
                                on_click=lambda: reset_protein_filters(),
                            ).props("flat no-wrap")
                        with ui.element("div").classes("ph-proteins-scroll w-full"):
                            proteins_column = ui.column().classes("w-full gap-3")
                    with ui.tab_panel(public_proteins_tab).classes("ph-proteins-panel"):
                        with ui.row().classes("ph-section-bar w-full"):
                            with ui.column().classes("gap-0"):
                                ui.label("工具蛋白").classes("text-xl font-semibold")
                                ui.label("维护这个项目内的工具蛋白、对照蛋白和常用公共信息。").classes("ph-muted")
                            new_public_protein_button = ui.button(
                                "新建工具蛋白",
                                icon="add",
                                on_click=lambda: open_public_protein_dialog(),
                            ).props("unelevated no-wrap")
                        with ui.element("div").classes("ph-proteins-scroll w-full"):
                            public_proteins_column = ui.column().classes("w-full gap-3")
                    with ui.tab_panel(batches_tab).classes("ph-batches-panel"):
                        with ui.row().classes("ph-section-bar w-full"):
                            with ui.column().classes("gap-0"):
                                ui.label("实验批次").classes("text-xl font-semibold")
                                ui.label("把项目中的蛋白排入 96 孔板，记录每个孔的实验结果。").classes("ph-muted")
                            new_batch_button = ui.button("新建批次", icon="add", on_click=lambda: batch_dialog.open()).props("unelevated")
                        with ui.element("div").classes("ph-batch-scroll w-full"):
                            batches_column = ui.column().classes("w-full gap-3")
                    with ui.tab_panel(members_tab).classes("ph-members-panel"):
                        with ui.row().classes("ph-section-bar w-full"):
                            with ui.column().classes("gap-0"):
                                ui.label("成员").classes("text-xl font-semibold")
                                ui.label("在这里管理项目访问权限。").classes("ph-muted")
                            add_member_button = ui.button("添加成员", icon="person_add", on_click=lambda: member_dialog.open()).props("unelevated")
                        with ui.element("div").classes("ph-members-scroll w-full"):
                            members_column = ui.column().classes("w-full gap-2")

            project_proteins = {"items": []}
            public_protein_form_target = {"public_protein": None}
            public_protein_delete_target = {"public_protein": None}
            selected_batch_proteins: set[int] = set()
            protein_rating_target = {"protein_id": None}
            project_access = {"role": ""}

            with ui.dialog() as similarity_dialog, ui.card().classes("ph-dialog-card w-full max-w-2xl gap-4"):
                similarity_title = ui.label("相似蛋白").classes("text-lg font-semibold")
                similarity_subtitle = ui.label().classes("ph-meta")
                similarity_matches_column = ui.column().classes("w-full gap-2")
                with ui.row().classes("justify-end w-full"):
                    ui.button("关闭", on_click=similarity_dialog.close).props("flat")

            def open_similarity_dialog(protein: dict) -> None:
                similarity_title.text = "高相似度匹配"
                similarity_subtitle.text = protein.get("name") or "未命名蛋白"
                _render_sequence_similarity_matches(protein, similarity_matches_column)
                similarity_dialog.open()

            async def load_project() -> None:
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/projects/{project_id}')", timeout=10)
                    project = data["project"]
                    title.text = project["name"]
                    description.text = project["description"] or "暂无描述"
                    status_badge.text = _project_status_label(project.get("status"))
                    status_badge.props(
                        f"outline color={_project_status_badge_color(project.get('status'))}"
                    )
                    role_badge.text = humanize(project["role"])
                    project_access["role"] = project["role"]
                    can_write_project = project["role"] in {"owner", "member"}
                    bulk_import_button.visible = can_write_project
                    new_protein_button.visible = can_write_project
                    new_public_protein_button.visible = can_write_project
                    new_batch_button.visible = can_write_project
                    add_member_button.visible = project["role"] == "owner"
                    members_column.clear()
                    with members_column:
                        for member in data["members"]:
                            with ui.row().classes("ph-member-row"):
                                with ui.row().classes("items-center gap-3"):
                                    with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                        ui.icon("person")
                                    with ui.column().classes("gap-0"):
                                        ui.label(person_label(member.get("name"), member.get("email"))).classes("font-medium")
                                        ui.label(member["email"]).classes("ph-meta")
                                ui.badge(humanize(member["role"])).props("outline")
                except Exception as error:
                    notify_error(error)

            def protein_list_path() -> str:
                query_params: list[tuple[str, str]] = []
                rating_values = protein_rating_filter.value or []
                if isinstance(rating_values, str):
                    rating_values = [rating_values]
                for rating in rating_values:
                    if rating:
                        query_params.append(("ratings", rating))
                if protein_date_from.value:
                    query_params.append(("date_from", protein_date_from.value))
                if protein_date_to.value:
                    query_params.append(("date_to", protein_date_to.value))
                query_params.append(("sort", protein_sort_select.value or "time_desc"))
                query = urlencode(query_params)
                path = f"/api/projects/{project_id}/proteins"
                return f"{path}?{query}" if query else path

            async def reset_protein_filters() -> None:
                protein_rating_filter.value = []
                protein_date_from.value = ""
                protein_date_to.value = ""
                protein_sort_select.value = "time_desc"
                await load_proteins()

            async def load_proteins() -> None:
                proteins_column.clear()
                with proteins_column:
                    ui.label("正在加载设计蛋白...").classes("ph-muted")
                try:
                    proteins = await ui.run_javascript(
                        f"return await phApi({json.dumps(protein_list_path())})",
                        timeout=10,
                    )
                    project_proteins["items"] = proteins
                    proteins_column.clear()
                    with proteins_column:
                        if not proteins:
                            empty_state("science", "还没有设计蛋白", "先创建设计蛋白并填写序列。")
                        for protein in proteins:
                            preview = protein["sequence"][:50] + (
                                "..." if len(protein["sequence"]) > 50 else ""
                            )
                            with ui.card().classes("ph-resource-card ph-protein-card w-full p-4"):
                                with ui.element("div").classes("ph-protein-card-layout"):
                                    with ui.row().classes("ph-protein-card-main"):
                                        with ui.element("div").classes("ph-icon-box ph-icon-protein"):
                                            ui.icon("science")
                                        with ui.column().classes("ph-protein-card-content"):
                                            with ui.column().classes("w-full gap-1"):
                                                ui.label(protein["name"]).classes("ph-card-title")
                                                with ui.row().classes("ph-protein-tags"):
                                                    ui.label(
                                                        protein_manual_rating_label(protein.get("manual_rating"))
                                                    ).classes(
                                                        protein_manual_rating_class(
                                                            protein.get("manual_rating")
                                                        )
                                                    )
                                                    if protein["protein_type"]:
                                                        ui.badge(protein["protein_type"]).props("outline")
                                                    _render_sequence_similarity_badge(
                                                        protein,
                                                        open_similarity_dialog,
                                                    )
                                            ui.label(protein["description"] or "暂无描述").classes("ph-card-description")
                                            target_text = f" · 靶标 {protein['target']}" if protein["target"] else ""
                                            effective_date = protein.get("effective_date") or protein["created_at"][:10]
                                            effective_date_source = (
                                                "记录时间"
                                                if protein.get("effective_date_source") == "pdb_deposit"
                                                else "上传时间"
                                            )
                                            ui.label(
                                                f"{len(protein['sequence'])} 个氨基酸 · "
                                                f"{protein['artifact_count']} 份资料"
                                                f" · {effective_date_source} {effective_date}"
                                                f"{target_text}"
                                            ).classes("ph-meta")
                                            ui.label(preview).classes("ph-protein-sequence-preview font-mono text-sm text-slate-700")
                                    with ui.row().classes("ph-protein-card-actions"):
                                        rating_button = ui.button(
                                            icon="sell",
                                            on_click=lambda p=protein: open_rating_dialog(p),
                                        ).props("flat round dense")
                                        rating_button.visible = project_access["role"] in {"owner", "member"}
                                        with rating_button:
                                            ui.tooltip("设置评级")
                                        open_button = ui.button(
                                            icon="open_in_new",
                                            on_click=lambda p=protein: ui.navigate.to(f"/proteins/{p['id']}"),
                                        ).props("flat round dense")
                                        with open_button:
                                            ui.tooltip("打开蛋白")
                    render_batch_protein_options()
                except Exception as error:
                    proteins_column.clear()
                    with proteins_column:
                        ui.label("设计蛋白加载失败，请稍后重试。").classes("ph-muted")
                    notify_error(error)

            async def load_public_proteins() -> None:
                public_proteins_column.clear()
                with public_proteins_column:
                    ui.label("正在加载工具蛋白...").classes("ph-muted")
                try:
                    public_proteins = await ui.run_javascript(
                        f"return await phApi('/api/projects/{project_id}/public-proteins')",
                        timeout=10,
                    )
                    public_proteins_column.clear()
                    with public_proteins_column:
                        if not public_proteins:
                            empty_state("biotech", "还没有工具蛋白", "先添加工具蛋白或对照蛋白。")
                        for public_protein in public_proteins:
                            sequence = public_protein["sequence"]
                            preview = sequence[:50] + (
                                "..." if len(sequence) > 50 else ""
                            )
                            created_by = person_label(
                                public_protein.get("created_by_name"),
                                public_protein.get("created_by_email"),
                            )
                            with ui.card().classes("ph-resource-card ph-protein-card w-full p-4"):
                                with ui.element("div").classes("ph-protein-card-layout"):
                                    with ui.row().classes("ph-protein-card-main"):
                                        with ui.element("div").classes("ph-icon-box ph-icon-protein"):
                                            ui.icon("biotech")
                                        with ui.column().classes("ph-protein-card-content"):
                                            with ui.column().classes("w-full gap-1"):
                                                ui.label(public_protein["name"]).classes("ph-card-title")
                                                with ui.row().classes("ph-protein-tags"):
                                                    if public_protein.get("protein_type"):
                                                        ui.badge(public_protein["protein_type"]).props("outline")
                                                    if public_protein.get("target"):
                                                        ui.badge(public_protein["target"]).props("outline color=secondary")
                                            ui.label(public_protein["description"] or "暂无描述").classes("ph-card-description")
                                            ui.label(
                                                f"{len(sequence)} 个氨基酸 · 创建人 {created_by} · 创建时间 {public_protein['created_at'][:10]}"
                                            ).classes("ph-meta")
                                            ui.label(preview).classes("ph-protein-sequence-preview font-mono text-sm text-slate-700")
                                    with ui.row().classes("ph-protein-card-actions"):
                                        open_button = ui.button(
                                            icon="open_in_new",
                                            on_click=lambda p=public_protein: ui.navigate.to(f"/public-proteins/{p['id']}"),
                                        ).props("flat round dense")
                                        with open_button:
                                            ui.tooltip("打开工具蛋白")
                                        edit_button = ui.button(
                                            icon="edit",
                                            on_click=lambda p=public_protein: open_public_protein_dialog(p),
                                        ).props("flat round dense")
                                        edit_button.visible = project_access["role"] in {"owner", "member"}
                                        with edit_button:
                                            ui.tooltip("编辑工具蛋白")
                                        delete_button = ui.button(
                                            icon="delete",
                                            on_click=lambda p=public_protein: open_delete_public_protein_dialog(p),
                                        ).props("flat round dense color=negative")
                                        delete_button.visible = project_access["role"] in {"owner", "member"}
                                        with delete_button:
                                            ui.tooltip("删除工具蛋白")
                except Exception as error:
                    public_proteins_column.clear()
                    with public_proteins_column:
                        ui.label("工具蛋白加载失败，请稍后重试。").classes("ph-muted")
                    notify_error(error)

            async def load_batches() -> None:
                batches_column.clear()
                with batches_column:
                    ui.label("正在加载批次...").classes("ph-muted")
                try:
                    batches = await ui.run_javascript(f"return await phApi('/api/projects/{project_id}/batches')", timeout=10)
                    batches_column.clear()
                    with batches_column:
                        if not batches:
                            empty_state("grid_view", "还没有实验批次", "选择一批蛋白创建 96 孔板。")
                        for batch in batches:
                            with ui.card().classes("ph-resource-card w-full p-4"):
                                with ui.row().classes("w-full items-center justify-between gap-4"):
                                    with ui.row().classes("min-w-0 flex-1 items-start gap-3"):
                                        with ui.element("div").classes("ph-icon-box ph-icon-protein"):
                                            ui.icon("grid_view")
                                        with ui.column().classes("min-w-0 gap-2"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.label(batch["name"]).classes("ph-card-title")
                                                ui.badge(f"{batch['plate_format']} 孔").props("outline")
                                                ui.badge(
                                                    humanize(batch.get("order_status") or "not_ordered")
                                                ).props("outline color=secondary")
                                            ui.label(batch["description"] or "暂无描述").classes("ph-card-description")
                                            if batch.get("receipt_note"):
                                                ui.label(f"收货：{batch['receipt_note']}").classes("ph-meta")
                                            received_count = int(batch.get("received_well_count") or 0)
                                            if received_count:
                                                ui.label(
                                                    f"已收货：{received_count}/{batch['well_count']} 个孔"
                                                ).classes("ph-meta")
                                            ui.label(
                                                f"{batch['well_count']} 个孔 · {batch['experiment_count']} 个实验 · {batch['result_count']} 个结果"
                                            ).classes("ph-meta")
                                    ui.button(
                                        "打开",
                                        icon="open_in_new",
                                        on_click=lambda b=batch: ui.navigate.to(f"/batches/{b['id']}"),
                                    ).props("flat")
                except Exception as error:
                    batches_column.clear()
                    with batches_column:
                        ui.label("批次加载失败，请稍后重试。").classes("ph-muted")
                    notify_error(error)

            with ui.dialog() as protein_rating_dialog, ui.card().classes("ph-dialog-card w-full max-w-sm gap-4"):
                ui.label("设置手动评级").classes("text-lg font-semibold")
                rating_protein_name = ui.label().classes("ph-meta")
                rating_select = ui.select(
                    PROTEIN_MANUAL_RATING_OPTIONS,
                    value="unrated",
                    label="评级",
                ).props("outlined").classes("w-full")

                def open_rating_dialog(protein: dict) -> None:
                    protein_rating_target["protein_id"] = protein["id"]
                    rating_protein_name.text = protein["name"]
                    rating_select.value = protein.get("manual_rating") or "unrated"
                    protein_rating_dialog.open()

                async def save_rating() -> None:
                    try:
                        protein_id = protein_rating_target["protein_id"]
                        if protein_id is None:
                            return
                        payload = {"manual_rating": rating_select.value or "unrated"}
                        await ui.run_javascript(
                            f"return await phApi('/api/proteins/{protein_id}/manual-rating', "
                            f"{{method: 'PATCH', body: {json.dumps(payload)}}})",
                            timeout=10,
                        )
                        protein_rating_dialog.close()
                        ui.notify("评级已更新", type="positive")
                        await load_proteins()
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=protein_rating_dialog.close).props("flat")
                    ui.button("保存", icon="save", on_click=save_rating)

            with ui.dialog() as protein_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("新建设计蛋白").classes("text-lg font-semibold")
                protein_name = ui.input("名称").props("outlined").classes("w-full ph-protein-name-input")
                protein_type = ui.select(PROTEIN_TYPE_OPTIONS, value="TCR", label="类型").props("outlined").classes("w-full ph-protein-type-select")
                protein_target = ui.input("靶标").props("outlined").classes("w-full ph-protein-target-input")
                protein_sequence = ui.textarea("氨基酸序列").props("outlined").classes("w-full ph-protein-sequence-input")
                with ui.row().classes("w-full items-center justify-between gap-3"):
                    protein_import_status = ui.label().classes("ph-meta ph-protein-import-status")
                    protein_import_button = ui.button("从 PDB/mmCIF 读取", icon="upload_file").props("flat")
                protein_description = ui.textarea("描述").props("outlined").classes("w-full ph-protein-description-input")

                protein_import_button.on(
                    "click",
                    js_handler=f"""
                    () => {{
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.accept = '.pdb,.ent,.cif,.mmcif,chemical/x-pdb,chemical/x-mmcif';
                        input.style.display = 'none';
                        input.addEventListener('change', async () => {{
                            if (!input.files || input.files.length === 0) {{
                                input.remove();
                                return;
                            }}
                            const status = document.querySelector('.ph-protein-import-status');
                            const sequenceInput = document.querySelector('.ph-protein-sequence-input textarea');
                            const nameInput = document.querySelector('.ph-protein-name-input input');
                            const updateInput = (element, value) => {{
                                if (!element) return;
                                element.value = value;
                                element.dispatchEvent(new Event('input', {{bubbles: true}}));
                                element.dispatchEvent(new Event('change', {{bubbles: true}}));
                            }};
                            try {{
                                if (status) status.textContent = '正在读取结构文件...';
                                const form = new FormData();
                                form.append('file', input.files[0]);
                                const data = await phApi('/api/projects/{project_id}/proteins/parse-structure', {{
                                    method: 'POST',
                                    body: form,
                                }});
                                window.phProteinStructureFile = input.files[0];
                                updateInput(sequenceInput, data.sequence);
                                if (nameInput && !nameInput.value.trim()) {{
                                    const fallbackName = (data.filename || 'protein').replace(/\\.[^.]+$/, '') || 'protein';
                                    updateInput(nameInput, fallbackName);
                                }}
                                if (status) status.textContent = `已读取 ${{data.length}} 个氨基酸 · ${{data.source}}`;
                                phNotify('序列已读取', 'positive');
                            }} catch (error) {{
                                window.phProteinStructureFile = null;
                                if (status) status.textContent = '';
                                phNotifyError(error, '读取失败');
                            }} finally {{
                                input.remove();
                            }}
                        }}, {{once: true}});
                        document.body.appendChild(input);
                        input.click();
                    }}
                    """,
                )

                async def create_protein() -> None:
                    try:
                        payload = await ui.run_javascript(
                            f"""
                            const fieldValue = (selector) => {{
                                const element = document.querySelector(selector);
                                return element ? element.value : '';
                            }};
                            return {{
                                name: fieldValue('.ph-protein-name-input input'),
                                sequence: fieldValue('.ph-protein-sequence-input textarea'),
                                description: fieldValue('.ph-protein-description-input textarea'),
                                protein_type: fieldValue('.ph-protein-type-select input'),
                                target: fieldValue('.ph-protein-target-input input'),
                                has_structure_file: Boolean(window.phProteinStructureFile),
                            }};
                            """,
                            timeout=10,
                        )
                        if payload.get("has_structure_file"):
                            await ui.run_javascript(
                                f"""
                                const payload = {json.dumps(payload)};
                                const file = window.phProteinStructureFile;
                                if (!file) {{
                                    throw new Error('请重新选择结构文件');
                                }}
                                const form = new FormData();
                                form.append('name', payload.name);
                                form.append('sequence', payload.sequence);
                                form.append('description', payload.description);
                                form.append('protein_type', payload.protein_type);
                                form.append('target', payload.target);
                                form.append('file', file, file.name);
                                return await phApi('/api/projects/{project_id}/proteins/with-structure', {{
                                    method: 'POST',
                                    body: form,
                                }});
                                """,
                                timeout=10,
                            )
                        else:
                            await ui.run_javascript(
                                f"return await phApi('/api/projects/{project_id}/proteins', {{method: 'POST', body: {json.dumps(payload)}}})",
                                timeout=10,
                            )
                        protein_dialog.close()
                        protein_name.value = ""
                        protein_type.value = "TCR"
                        protein_target.value = ""
                        protein_sequence.value = ""
                        protein_import_status.text = ""
                        protein_description.value = ""
                        await ui.run_javascript("window.phProteinStructureFile = null", timeout=5)
                        await load_proteins()
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=protein_dialog.close).props("flat")
                    ui.button("创建", icon="add", on_click=create_protein)

            with ui.dialog() as public_protein_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                public_protein_dialog_title = ui.label("新建工具蛋白").classes("text-lg font-semibold")
                public_protein_name = ui.input("名称").props("outlined").classes("w-full")
                public_protein_type = ui.input("类型").props("outlined").classes("w-full")
                public_protein_target = ui.input("靶标/用途").props("outlined").classes("w-full")
                public_protein_sequence = ui.textarea("氨基酸序列").props("outlined").classes("w-full")
                public_protein_description = ui.textarea("描述").props("outlined").classes("w-full")

                def open_public_protein_dialog(public_protein: dict | None = None) -> None:
                    public_protein_form_target["public_protein"] = public_protein
                    public_protein_dialog_title.text = (
                        "编辑工具蛋白" if public_protein else "新建工具蛋白"
                    )
                    public_protein_name.value = public_protein["name"] if public_protein else ""
                    public_protein_type.value = (
                        public_protein.get("protein_type", "") if public_protein else ""
                    )
                    public_protein_target.value = (
                        public_protein.get("target", "") if public_protein else ""
                    )
                    public_protein_sequence.value = (
                        public_protein["sequence"] if public_protein else ""
                    )
                    public_protein_description.value = (
                        public_protein.get("description", "") if public_protein else ""
                    )
                    public_protein_dialog.open()

                async def save_public_protein() -> None:
                    try:
                        payload = {
                            "name": public_protein_name.value or "",
                            "protein_type": public_protein_type.value or "",
                            "target": public_protein_target.value or "",
                            "sequence": public_protein_sequence.value or "",
                            "description": public_protein_description.value or "",
                        }
                        public_protein = public_protein_form_target["public_protein"]
                        if public_protein:
                            await ui.run_javascript(
                                f"return await phApi('/api/projects/{project_id}/public-proteins/{public_protein['id']}', "
                                f"{{method: 'PATCH', body: {json.dumps(payload)}}})",
                                timeout=10,
                            )
                        else:
                            await ui.run_javascript(
                                f"return await phApi('/api/projects/{project_id}/public-proteins', "
                                f"{{method: 'POST', body: {json.dumps(payload)}}})",
                                timeout=10,
                            )
                        public_protein_dialog.close()
                        public_protein_form_target["public_protein"] = None
                        public_protein_name.value = ""
                        public_protein_type.value = ""
                        public_protein_target.value = ""
                        public_protein_sequence.value = ""
                        public_protein_description.value = ""
                        await load_public_proteins()
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=public_protein_dialog.close).props("flat")
                    ui.button("保存", icon="save", on_click=save_public_protein).props("unelevated")

            with ui.dialog() as delete_public_protein_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                delete_public_protein_title = ui.label().classes("text-lg font-semibold")
                ui.label("删除后不会影响设计蛋白、批次或实验结果。").classes("ph-muted")

                def open_delete_public_protein_dialog(public_protein: dict) -> None:
                    public_protein_delete_target["public_protein"] = public_protein
                    delete_public_protein_title.text = f"删除工具蛋白：{public_protein['name']}"
                    delete_public_protein_dialog.open()

                async def delete_selected_public_protein() -> None:
                    try:
                        public_protein = public_protein_delete_target["public_protein"]
                        if not public_protein:
                            return
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/public-proteins/{public_protein['id']}', "
                            "{method: 'DELETE'})",
                            timeout=10,
                        )
                        delete_public_protein_dialog.close()
                        public_protein_delete_target["public_protein"] = None
                        await load_public_proteins()
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=delete_public_protein_dialog.close).props("flat")
                    ui.button(
                        "删除",
                        icon="delete",
                        on_click=delete_selected_public_protein,
                    ).props("unelevated color=negative")

            with ui.dialog() as bulk_import_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("批量导入设计蛋白").classes("text-lg font-semibold")
                bulk_protein_type = ui.select(PROTEIN_TYPE_OPTIONS, value="TCR", label="类型").props("outlined").classes("w-full ph-bulk-protein-type-select")
                bulk_protein_target = ui.input("靶标").props("outlined").classes("w-full ph-bulk-protein-target-input")
                bulk_protein_description = ui.textarea("描述").props("outlined").classes("w-full ph-bulk-protein-description-input")
                bulk_import_status = ui.label("等待选择结构文件夹；打分表 CSV 可选").classes("ph-meta ph-bulk-import-status")
                with ui.row().classes("w-full items-center justify-between gap-2"):
                    bulk_select_button = ui.button("选择结构文件夹", icon="drive_folder_upload").props("flat no-wrap")
                    bulk_score_button = ui.button("选择打分表 CSV", icon="table_chart").props("flat no-wrap")

                bulk_select_button.on(
                    "click",
                    js_handler=f"""
                    () => {{
                        const status = document.querySelector('.ph-bulk-import-status');
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.multiple = true;
                        input.webkitdirectory = true;
                        input.setAttribute('webkitdirectory', '');
                        input.accept = '.pdb,.ent,.cif,.mmcif,chemical/x-pdb,chemical/x-mmcif';
                        input.style.display = 'none';
                        input.addEventListener('change', async () => {{
                            if (!input.files || input.files.length === 0) {{
                                input.remove();
                                return;
                            }}
                            const files = Array.from(input.files).filter((file) =>
                                /\\.(pdb|ent|cif|mmcif)$/i.test(file.name)
                            );
                            if (files.length === 0) {{
                                window.phBulkImportFiles = [];
                                input.remove();
                                phNotify('没有可导入的 PDB/mmCIF 文件', 'negative');
                                return;
                            }}
                            window.phBulkImportFiles = files;
                            const scoreFile = window.phBulkScoreFile || null;
                            if (status) status.textContent = scoreFile
                                ? `已选择 ${{files.length}} 个文件和打分表，点击导入开始`
                                : `已选择 ${{files.length}} 个文件，可直接导入或继续选择打分表 CSV`;
                            phNotify(`已选择 ${{files.length}} 个文件`, 'positive');
                            input.remove();
                        }}, {{once: true}});
                        document.body.appendChild(input);
                        input.click();
                    }}
                    """,
                )

                bulk_score_button.on(
                    "click",
                    js_handler=f"""
                    () => {{
                        const status = document.querySelector('.ph-bulk-import-status');
                        const input = document.createElement('input');
                        input.type = 'file';
                        input.accept = '.csv,text/csv';
                        input.style.display = 'none';
                        input.addEventListener('change', () => {{
                            const file = input.files && input.files[0];
                            if (!file) {{
                                input.remove();
                                return;
                            }}
                            if (!file.name.toLowerCase().endsWith('.csv')) {{
                                window.phBulkScoreFile = null;
                                phNotify('请只选择一个打分表 CSV', 'negative');
                                input.remove();
                                return;
                            }}
                            window.phBulkScoreFile = file;
                            const files = window.phBulkImportFiles || [];
                            if (status) status.textContent = files.length
                                ? `已选择 ${{files.length}} 个文件和打分表，点击导入开始`
                                : `已选择打分表 ${{file.name}}，继续选择结构文件夹`;
                            phNotify('已选择打分表 CSV', 'positive');
                            input.remove();
                        }}, {{once: true}});
                        document.body.appendChild(input);
                        input.click();
                    }}
                    """,
                )

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=bulk_import_dialog.close).props("flat")
                    ui.button("导入", icon="upload_file").props("unelevated").on(
                        "click",
                        js_handler=f"""
                        async () => {{
                            const status = document.querySelector('.ph-bulk-import-status');
                            const files = window.phBulkImportFiles || [];
                            const scoreFile = window.phBulkScoreFile || null;
                            const fieldValue = (selector) => {{
                                const element = document.querySelector(selector);
                                return element ? element.value : '';
                            }};
                            if (files.length === 0) {{
                                phNotify('请先选择结构文件夹', 'negative');
                                return;
                            }}
                            try {{
                                if (status) status.textContent = scoreFile
                                    ? `正在导入 ${{files.length}} 个文件并上传打分表...`
                                    : `正在导入 ${{files.length}} 个文件...`;
                                const form = new FormData();
                                form.append('protein_type', fieldValue('.ph-bulk-protein-type-select input') || 'TCR');
                                form.append('target', fieldValue('.ph-bulk-protein-target-input input'));
                                form.append('description', fieldValue('.ph-bulk-protein-description-input textarea'));
                                if (scoreFile) {{
                                    form.append('score_file', scoreFile, scoreFile.name);
                                }}
                                for (const file of files) {{
                                    form.append('files', file, file.webkitRelativePath || file.name);
                                }}
                                const result = await phApi('/api/projects/{project_id}/proteins/import-structures', {{
                                    method: 'POST',
                                    body: form,
                                }});
                                const proteins = result && Array.isArray(result.proteins) ? result.proteins : [];
                                const scoreImport = result && result.score_import ? result.score_import : {{}};
                                const matched = Number.isFinite(scoreImport.matched_count)
                                    ? scoreImport.matched_count
                                    : 0;
                                const skipped = Array.isArray(scoreImport.skipped_names)
                                    ? scoreImport.skipped_names
                                    : [];
                                window.phBulkImportFiles = [];
                                window.phBulkScoreFile = null;
                                if (!scoreFile) {{
                                    if (status) status.textContent = `已导入 ${{proteins.length}} 个设计蛋白`;
                                    phNotify(`已导入 ${{proteins.length}} 个设计蛋白`, 'positive');
                                }} else if (skipped.length) {{
                                    const preview = skipped.slice(0, 6).join(', ');
                                    const suffix = skipped.length > 6 ? `${{preview}} 等 ${{skipped.length}} 行` : preview;
                                    if (status) status.textContent = `已导入 ${{proteins.length}} 个设计蛋白，打分表匹配 ${{matched}} 个，跳过 ${{skipped.length}} 行`;
                                    phNotify(`已导入 ${{proteins.length}} 个设计蛋白，打分表跳过：${{suffix}}`, 'warning');
                                }} else {{
                                    if (status) status.textContent = `已导入 ${{proteins.length}} 个设计蛋白，打分表匹配 ${{matched}} 个`;
                                    phNotify(`已导入 ${{proteins.length}} 个设计蛋白，打分表匹配 ${{matched}} 个`, 'positive');
                                }}
                                window.location.reload();
                            }} catch (error) {{
                                if (status) status.textContent = '导入失败';
                                phNotifyError(error, '导入失败');
                            }}
                        }}
                        """,
                    )

            with ui.dialog() as batch_dialog, ui.card().classes("ph-dialog-card w-full max-w-2xl gap-4"):
                ui.label("新建实验批次").classes("text-lg font-semibold")
                batch_name = ui.input("名称").props("outlined").classes("w-full")
                batch_description = ui.textarea("描述").props("outlined autogrow").classes("w-full")
                batch_start_position = ui.select(
                    PLATE_96_POSITION_OPTIONS,
                    value="A01",
                    label="起始孔位",
                ).props("outlined dense").classes("w-full")
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("选择蛋白").classes("font-semibold text-slate-800")
                    with ui.row().classes("items-center gap-2"):
                        ui.button(
                            "全选当前项目蛋白",
                            icon="select_all",
                            on_click=lambda: select_all_batch_proteins(),
                        ).props("flat dense no-wrap")
                        selected_batch_label = ui.label("已选择 0 个蛋白").classes("ph-meta")
                batch_proteins_column = ui.column().classes("ph-batch-protein-list")

                def update_selected_batch_label() -> None:
                    selected_batch_label.text = f"已选择 {len(selected_batch_proteins)} 个蛋白"

                def toggle_batch_protein(protein_id: int, selected: bool) -> None:
                    if selected:
                        selected_batch_proteins.add(protein_id)
                    else:
                        selected_batch_proteins.discard(protein_id)
                    update_selected_batch_label()

                def select_all_batch_proteins() -> None:
                    selected_batch_proteins.clear()
                    selected_batch_proteins.update(
                        protein["id"] for protein in project_proteins["items"]
                    )
                    render_batch_protein_options()

                def render_batch_protein_options() -> None:
                    batch_proteins_column.clear()
                    with batch_proteins_column:
                        if not project_proteins["items"]:
                            ui.label("还没有可加入批次的蛋白。").classes("ph-muted")
                        for protein in project_proteins["items"]:
                            with ui.row().classes("ph-batch-protein-row"):
                                with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                    ui.checkbox(
                                        value=protein["id"] in selected_batch_proteins,
                                        on_change=lambda event, protein_id=protein["id"]: toggle_batch_protein(
                                            protein_id, bool(event.value)
                                        ),
                                    )
                                    with ui.column().classes("min-w-0 gap-0"):
                                        ui.label(protein["name"]).classes("font-medium")
                                        ui.label(
                                            f"{len(protein['sequence'])} 个氨基酸"
                                        ).classes("ph-meta")
                                if protein["protein_type"]:
                                    ui.badge(protein["protein_type"]).props("outline")
                                ui.label(
                                    protein_manual_rating_label(protein.get("manual_rating"))
                                ).classes(
                                    protein_manual_rating_class(protein.get("manual_rating"))
                                )
                                _render_sequence_similarity_badge(
                                    protein,
                                    open_similarity_dialog,
                                )
                    update_selected_batch_label()

                async def create_batch_from_selection() -> None:
                    try:
                        payload = {
                            "name": batch_name.value,
                            "description": batch_description.value or "",
                            "protein_ids": [
                                protein["id"]
                                for protein in project_proteins["items"]
                                if protein["id"] in selected_batch_proteins
                            ],
                            "plate_format": "96",
                            "start_position": batch_start_position.value or "A01",
                        }
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/batches', "
                            f"{{method: 'POST', body: {json.dumps(payload)}}})",
                            timeout=10,
                        )
                        batch_dialog.close()
                        batch_name.value = ""
                        batch_description.value = ""
                        batch_start_position.value = "A01"
                        selected_batch_proteins.clear()
                        render_batch_protein_options()
                        await load_batches()
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=batch_dialog.close).props("flat")
                    ui.button("创建", icon="add", on_click=create_batch_from_selection).props("unelevated")

            with ui.dialog() as member_dialog, ui.card().classes("ph-dialog-card w-full max-w-2xl gap-4"):
                ui.label("添加成员").classes("text-lg font-semibold")
                with ui.row().classes("w-full items-center gap-2"):
                    member_query = ui.input("按姓名搜索").props("outlined").classes("flex-1")
                    ui.button("搜索", icon="search", on_click=lambda: search_members()).props("unelevated")
                selected_member = {"email": None}
                with ui.column().classes("w-full gap-2"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label("搜索结果").classes("font-semibold text-slate-800")
                        selected_member_label = ui.label("未选择").classes("ph-meta")
                    member_results = ui.column().classes("ph-member-results")
                    with member_results:
                        ui.label("输入姓名并搜索后，候选成员会显示在这里。").classes("ph-muted")

                async def search_members() -> None:
                    query = (member_query.value or "").strip()
                    selected_member["email"] = None
                    selected_member_label.text = "未选择"
                    member_results.clear()
                    if not query:
                        with member_results:
                            ui.label("请输入姓名关键词。").classes("ph-muted")
                        return
                    try:
                        candidates = await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/member-candidates?query=' + encodeURIComponent({query!r}))",
                            timeout=10,
                        )
                        member_results.clear()
                        with member_results:
                            if not candidates:
                                ui.label("没有找到可添加的成员。").classes("ph-muted")
                            for candidate in candidates:
                                def choose(candidate: dict = candidate) -> None:
                                    selected_member["email"] = candidate["email"]
                                    selected_member_label.text = (
                                        f"已选择 {person_label(candidate.get('name'), candidate.get('email'))}"
                                    )

                                with ui.row().classes("ph-member-candidate-row"):
                                    with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                        with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                            ui.icon("person")
                                        with ui.column().classes("min-w-0 gap-0"):
                                            ui.label(person_label(candidate.get("name"), candidate.get("email"))).classes("font-medium")
                                            ui.label(candidate["email"]).classes("ph-meta")
                                    ui.button("选择", icon="check", on_click=choose).props("flat dense")
                    except Exception as error:
                        notify_error(error)

                async def add_member() -> None:
                    if not selected_member["email"]:
                        ui.notify("请先搜索并选择成员", type="warning")
                        return
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/members', {{method: 'POST', body: {{email: {selected_member['email']!r}, role: 'member'}}}})",
                            timeout=10,
                        )
                        member_dialog.close()
                        member_query.value = ""
                        selected_member["email"] = None
                        selected_member_label.text = "未选择"
                        member_results.clear()
                        with member_results:
                            ui.label("输入姓名并搜索后，候选成员会显示在这里。").classes("ph-muted")
                        await load_project()
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=member_dialog.close).props("flat")
                    ui.button("添加", icon="person_add", on_click=add_member)

            await ui.context.client.connected()
            await load_project()
            await load_proteins()
            await load_public_proteins()
            await load_batches()

    @ui.page("/batches/{batch_id}")
    async def batch_page(batch_id: int) -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("实验批次").classes("ph-eyebrow")
                    batch_title = ui.label("实验批次").classes("ph-title")
                    batch_description = ui.label().classes("ph-subtitle")
                with ui.column().classes("items-end gap-2"):
                    ui.button("返回", icon="arrow_back", on_click=lambda: ui.run_javascript("history.back()")).props("flat")
                    with ui.row().classes("items-center gap-2"):
                        batch_status_badge = ui.badge("未order").props("outline")
                        batch_status_button = ui.button(
                            "修改状态/说明",
                            icon="published_with_changes",
                            on_click=lambda: status_dialog.open(),
                        ).props("flat dense no-wrap")
                    batch_meta = ui.row().classes("gap-2")

            with ui.column().classes("ph-panel w-full gap-3 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label("收货说明").classes("text-xl font-semibold")
                        receipt_meta_label = ui.label().classes("ph-muted")
                    receipt_edit_button = ui.button(
                        "编辑",
                        icon="edit_note",
                        on_click=lambda: status_dialog.open(),
                    ).props("flat no-wrap")
                receipt_detail_summary = ui.label("收货明细：暂无").classes("ph-meta")
                receipt_positions_label = ui.label("暂无已收孔位").classes("ph-muted")
                receipt_note_label = ui.label("暂无收货说明").classes("ph-muted whitespace-pre-wrap")

            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        mapping_title = ui.label("批次 Mapping").classes("text-xl font-semibold")
                        mapping_summary = ui.label().classes("ph-muted")
                    with ui.row().classes("items-center gap-2"):
                        ui.button(
                            "导出板位表",
                            icon="download",
                            on_click=lambda: download_plate_workbook(),
                        ).props("flat no-wrap")
                        ui.button(
                            "导出Summary",
                            icon="download",
                            on_click=lambda: download_summary_workbook(),
                        ).props("flat no-wrap")
                mapping_table = (
                    ui.element("div")
                    .classes("ph-batch-mapping ph-batch-mapping-scroll")
                    .props("tabindex=0")
                )

            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label("打分密度图").classes("text-xl font-semibold")
                score_density_column = ui.column().classes("w-full gap-3")

            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label("翻译").classes("text-xl font-semibold")
                        translation_status = ui.label("等待翻译").classes("ph-muted")
                    with ui.row().classes("items-center gap-2"):
                        ui.button(
                            "下载 DNA",
                            icon="download",
                            on_click=lambda: download_translation_sequences(),
                        ).props("flat no-wrap")
                with ui.element("div").classes("ph-translation-actions w-full"):
                    translation_padding = ui.select(
                        {"no": "not padding", "yes": "padding"},
                        value="no",
                        label="padding",
                    ).props("outlined dense").classes("w-full")
                    translation_add_w = ui.select(
                        {"no": "not add W", "yes": "add W"},
                        value="no",
                        label="additional W",
                    ).props("outlined dense").classes("w-full")
                    translation_organism = ui.select(
                        TRANSLATION_ORGANISM_OPTIONS,
                        value="E. coli",
                        label="organism",
                    ).props("outlined dense").classes("w-full")
                    translation_backbone = ui.input(
                        "backbone",
                        value="5",
                    ).props("outlined dense").classes("w-full")
                    translation_resistance = ui.select(
                        TRANSLATION_RESISTANCE_OPTIONS,
                        value="Amp",
                        label="抗性",
                    ).props("outlined dense").classes("w-full")
                    translate_button = ui.button(
                        "翻译",
                        icon="translate",
                        on_click=lambda: translate_batch_sequences_ui(),
                    ).props("unelevated no-wrap")
                translation_results = (
                    ui.element("div")
                    .classes("ph-batch-mapping ph-batch-mapping-scroll")
                    .props("tabindex=0")
                )

            def position_mapping_select_js(
                *,
                state_name: str,
                status_selector: str,
                waiting_text: str,
            ) -> str:
                return f"""
                () => {{
                    const statusLabel = document.querySelector('{status_selector}');
                    const setStatus = (text) => {{
                        if (statusLabel) statusLabel.textContent = text;
                    }};
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = '.csv,text/csv';
                    input.style.display = 'none';
                    input.addEventListener('change', () => {{
                        const file = input.files && input.files[0];
                        if (!file) {{
                            setStatus('{waiting_text}');
                            input.remove();
                            return;
                        }}
                        if (!file.name.toLowerCase().endsWith('.csv')) {{
                            window.{state_name} = null;
                            setStatus('板位映射 CSV 选择失败');
                            phNotify('请只选择一个板位映射 CSV', 'negative');
                            input.remove();
                            return;
                        }}
                        window.{state_name} = file;
                        setStatus(`已选择板位映射 CSV：${{file.name}}`);
                        phNotify('已选择板位映射 CSV', 'positive');
                        input.remove();
                    }}, {{once: true}});
                    document.body.appendChild(input);
                    input.click();
                }}
                """

            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label("HPLC 结果").classes("text-xl font-semibold")
                        ui.label("选择包含 chromatogram CSV 和 vial_fc.csv 的文件夹。").classes("ph-muted")
                with ui.element("div").classes("ph-hplc-upload-actions w-full"):
                    hplc_upload_status = ui.label("等待选择 HPLC 文件夹").classes(
                        "ph-muted ph-hplc-upload-status"
                    )
                    with ui.row().classes("gap-2 items-center justify-end no-wrap ph-hplc-upload-buttons"):
                        hplc_mapping_button = ui.button(
                            "选择板位映射 CSV",
                            icon="table_chart",
                        ).props("outline no-wrap").classes("ph-hplc-mapping-button")
                        hplc_upload_button = ui.button(
                            "上传 HPLC 文件夹",
                            icon="upload_file",
                        ).props("unelevated no-wrap").classes("ph-hplc-upload-button")

                    def hplc_upload_js() -> str:
                        return f"""
                        () => {{
                            const statusLabel = document.querySelector('.ph-hplc-upload-status');
                            const setStatus = (text) => {{
                                if (statusLabel) statusLabel.textContent = text;
                            }};
                            const input = document.createElement('input');
                            input.type = 'file';
                            input.multiple = true;
                            input.webkitdirectory = true;
                            input.accept = '.csv,text/csv';
                            input.style.display = 'none';
                            input.addEventListener('change', async () => {{
                                const files = Array.from(input.files || []);
                                const csvFiles = files.filter((file) => file.name.toLowerCase().endsWith('.csv'));
                                const chromatogramFiles = csvFiles.filter((file) => file.name.toLowerCase() !== 'vial_fc.csv');
                                const vialFile = csvFiles.find((file) => file.name.toLowerCase() === 'vial_fc.csv');
                                if (!csvFiles.length) {{
                                    setStatus('没有选择 HPLC CSV 文件');
                                    phNotify('请选择包含 HPLC CSV 的文件夹', 'negative');
                                    input.remove();
                                    return;
                                }}
                                if (!chromatogramFiles.length) {{
                                    setStatus('没有找到 chromatogram CSV');
                                    phNotify('文件夹里没有 chromatogram CSV', 'negative');
                                    input.remove();
                                    return;
                                }}
                                if (!vialFile) {{
                                    setStatus('缺少 vial_fc.csv');
                                    phNotify('文件夹里缺少 vial_fc.csv', 'negative');
                                    input.remove();
                                    return;
                                }}
                                const sourceName = files.length && files[0].webkitRelativePath
                                    ? files[0].webkitRelativePath.split('/')[0]
                                    : '';
                                const mappingFile = window.phHplcPositionMappingFile || null;
                                const form = new FormData();
                                form.append('source_name', sourceName);
                                for (const file of csvFiles) {{
                                    form.append('files', file, file.webkitRelativePath || file.name);
                                }}
                                if (mappingFile) {{
                                    form.append('position_mapping_file', mappingFile, mappingFile.name);
                                }}
                                try {{
                                    setStatus(`正在上传 ${{chromatogramFiles.length}} 个 HPLC 文件并绘图...`);
                                    phNotify('HPLC 结果上传中', 'info');
                                    const result = await phApi('/api/batches/{batch_id}/hplc-results', {{
                                        method: 'POST',
                                        body: form,
                                    }});
                                    const details = result && result.experiment ? result.experiment.details || {{}} : {{}};
                                    const count = details.sample_count || details.file_count || chromatogramFiles.length;
                                    const skippedResultPositions = Array.isArray(details.skipped_result_positions)
                                        ? details.skipped_result_positions
                                        : [];
                                    const skippedText = skippedResultPositions.length
                                        ? `，跳过未映射板位 ${{skippedResultPositions.join(', ')}}`
                                        : '';
                                    setStatus(`HPLC 结果上传成功：${{count}} 个图${{skippedText}}`);
                                    phNotify(skippedResultPositions.length ? 'HPLC 部分结果上传成功' : 'HPLC 结果上传成功', skippedResultPositions.length ? 'warning' : 'positive');
                                    window.phHplcPositionMappingFile = null;
                                    setTimeout(() => window.location.reload(), 800);
                                }} catch (error) {{
                                    const message = error && error.message ? error.message : 'HPLC 导入失败';
                                    setStatus(`HPLC 结果上传失败：${{message}}`);
                                    phNotifyError(error, 'HPLC 导入失败');
                                }} finally {{
                                    input.remove();
                                }}
                            }}, {{once: true}});
                            document.body.appendChild(input);
                            input.click();
                        }}
                        """

                    hplc_mapping_button.on(
                        "click",
                        js_handler=position_mapping_select_js(
                            state_name="phHplcPositionMappingFile",
                            status_selector=".ph-hplc-upload-status",
                            waiting_text="等待选择 HPLC 文件夹",
                        ),
                    )
                    hplc_upload_button.on("click", js_handler=hplc_upload_js())

            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label("SPR 结果").classes("text-xl font-semibold")
                        ui.label("PPTX 和浓度表分别上传。").classes("ph-muted")
                with ui.element("div").classes("ph-spr-upload-actions w-full"):
                    spr_run_date = ui.input(
                        "SPR 日期",
                        value=date.today().isoformat(),
                    ).props("outlined dense").classes("w-full ph-spr-run-date")
                    spr_upload_status = ui.label("等待上传 SPR 文件").classes(
                        "ph-muted ph-spr-upload-status"
                    )
                    with ui.row().classes("gap-2 items-center justify-end no-wrap ph-spr-upload-buttons"):
                        spr_mapping_button = ui.button(
                            "选择板位映射 CSV",
                            icon="table_chart",
                        ).props("outline no-wrap").classes("ph-spr-mapping-button")
                        spr_upload_button = ui.button(
                            "上传 SPR PPTX",
                            icon="upload_file",
                        ).props("unelevated no-wrap").classes("ph-spr-upload-button")
                        spr_concentration_button = ui.button(
                            "上传 SPR 浓度表",
                            icon="upload_file",
                        ).props("unelevated no-wrap").classes("ph-spr-upload-button")

                    def spr_pptx_upload_js() -> str:
                        return f"""
                        () => {{
                            const dateInput = document.querySelector('.ph-spr-run-date input');
                            const statusLabel = document.querySelector('.ph-spr-upload-status');
                            const setStatus = (text) => {{
                                if (statusLabel) statusLabel.textContent = text;
                            }};
                            const runDate = dateInput ? dateInput.value.trim() : '';
                            if (!runDate) {{
                                setStatus('缺少 SPR 日期');
                                phNotify('请先填写 SPR 日期', 'negative');
                                return;
                            }}
                            const input = document.createElement('input');
                            input.type = 'file';
                            input.accept = '.pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation';
                            input.style.display = 'none';
                            input.addEventListener('change', async () => {{
                                const file = input.files && input.files[0];
                                if (!file) {{
                                    setStatus('未选择文件');
                                    input.remove();
                                    return;
                                }}
                                const lower = file.name.toLowerCase();
                                if (!lower.endsWith('.pptx')) {{
                                    setStatus('请只选择一个 SPR PPTX');
                                    phNotify('请只选择一个 SPR PPTX', 'negative');
                                    input.remove();
                                    return;
                                }}
                                const form = new FormData();
                                form.append('run_date', runDate);
                                form.append('file', file, file.name);
                                const mappingFile = window.phSprPositionMappingFile || null;
                                if (mappingFile) {{
                                    form.append('position_mapping_file', mappingFile, mappingFile.name);
                                }}
                                try {{
                                    setStatus('正在上传 SPR PPTX 并解析图表...');
                                    phNotify('SPR 结果上传中', 'info');
                                    const result = await phApi('/api/batches/{batch_id}/spr-results', {{
                                        method: 'POST',
                                        body: form,
                                    }});
                                    const details = result && result.experiment ? result.experiment.details || {{}} : {{}};
                                    const positions = Array.isArray(details.uploaded_positions)
                                        ? details.uploaded_positions
                                        : [];
                                    const skipped = Array.isArray(details.skipped_positions)
                                        ? details.skipped_positions
                                        : [];
                                    const skippedResultPositions = Array.isArray(details.skipped_result_positions)
                                        ? details.skipped_result_positions
                                        : [];
                                    const count = details.sample_count || positions.length || 1;
                                    const concentrationCount = details.concentration_count || 0;
                                    const concentrationText = concentrationCount ? '（已关联浓度表）' : '';
                                    const successNotify = concentrationCount
                                        ? 'SPR 结果上传成功，已关联浓度表'
                                        : 'SPR 结果上传成功';
                                    if (skipped.length) {{
                                        const uploadedText = positions.length ? positions.join(', ') : '无';
                                        const skippedText = skipped.join(', ');
                                        setStatus(`SPR 部分上传成功：成功 ${{uploadedText}}；失败 ${{skippedText}} 已传过${{concentrationText}}`);
                                        phNotify(`SPR 部分上传成功，失败板位：${{skippedText}} 已传过`, 'warning');
                                    }} else if (skippedResultPositions.length) {{
                                        const skippedText = skippedResultPositions.join(', ');
                                        const positionText = positions.length ? `：${{positions.join(', ')}}` : '';
                                        setStatus(`SPR 部分上传成功：${{count}} 个结果${{positionText}}；跳过未映射板位 ${{skippedText}}${{concentrationText}}`);
                                        phNotify(`SPR 部分结果上传成功，跳过未映射板位：${{skippedText}}`, 'warning');
                                    }} else {{
                                        const positionText = positions.length ? `：${{positions.join(', ')}}` : '';
                                        setStatus(`SPR 结果上传成功：${{count}} 个结果${{positionText}}${{concentrationText}}`);
                                        phNotify(successNotify, 'positive');
                                    }}
                                    window.phSprPositionMappingFile = null;
                                    setTimeout(() => window.location.reload(), 800);
                                }} catch (error) {{
                                    const message = error && error.message ? error.message : 'SPR 导入失败';
                                    setStatus(`SPR 结果上传失败：${{message}}`);
                                    phNotifyError(error, 'SPR 导入失败');
                                }} finally {{
                                    input.remove();
                                }}
                            }}, {{once: true}});
                            document.body.appendChild(input);
                            input.click();
                        }}
                        """

                    def spr_concentration_upload_js() -> str:
                        return f"""
                        () => {{
                            const dateInput = document.querySelector('.ph-spr-run-date input');
                            const statusLabel = document.querySelector('.ph-spr-upload-status');
                            const setStatus = (text) => {{
                                if (statusLabel) statusLabel.textContent = text;
                            }};
                            const runDate = dateInput ? dateInput.value.trim() : '';
                            if (!runDate) {{
                                setStatus('缺少 SPR 日期');
                                phNotify('请先填写 SPR 日期', 'negative');
                                return;
                            }}
                            const input = document.createElement('input');
                            input.type = 'file';
                            input.accept = '.csv,text/csv';
                            input.style.display = 'none';
                            input.addEventListener('change', async () => {{
                                const file = input.files && input.files[0];
                                if (!file) {{
                                    setStatus('未选择文件');
                                    input.remove();
                                    return;
                                }}
                                const lower = file.name.toLowerCase();
                                if (!lower.endsWith('.csv')) {{
                                    setStatus('请只选择一个浓度 CSV');
                                    phNotify('请只选择一个浓度 CSV', 'negative');
                                    input.remove();
                                    return;
                                }}
                                const form = new FormData();
                                form.append('run_date', runDate);
                                form.append('file', file, file.name);
                                try {{
                                    setStatus('正在上传 SPR 浓度表并关联结果...');
                                    phNotify('SPR 浓度表上传中', 'info');
                                    const result = await phApi('/api/batches/{batch_id}/spr-concentrations', {{
                                        method: 'POST',
                                        body: form,
                                    }});
                                    const details = result && result.experiment ? result.experiment.details || {{}} : {{}};
                                    const concentrationCount = details.concentration_count || 0;
                                    setStatus(`SPR 浓度表上传成功：${{concentrationCount}} 行`);
                                    phNotify('SPR 浓度表上传成功', 'positive');
                                    setTimeout(() => window.location.reload(), 800);
                                }} catch (error) {{
                                    const message = error && error.message ? error.message : 'SPR 浓度表导入失败';
                                    setStatus(`SPR 浓度表上传失败：${{message}}`);
                                    phNotifyError(error, 'SPR 浓度表导入失败');
                                }} finally {{
                                    input.remove();
                                }}
                            }}, {{once: true}});
                            document.body.appendChild(input);
                            input.click();
                        }}
                        """

                    spr_mapping_button.on(
                        "click",
                        js_handler=position_mapping_select_js(
                            state_name="phSprPositionMappingFile",
                            status_selector=".ph-spr-upload-status",
                            waiting_text="等待上传 SPR 文件",
                        ),
                    )
                    spr_upload_button.on("click", js_handler=spr_pptx_upload_js())
                    spr_concentration_button.on("click", js_handler=spr_concentration_upload_js())

            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label("AKTA 结果").classes("text-xl font-semibold")
                        ui.label("上传 AKTA zip 并按日期归档。").classes("ph-muted")
                with ui.element("div").classes("ph-batch-upload-actions w-full"):
                    akta_run_date = ui.input(
                        "AKTA 日期",
                        value=date.today().isoformat(),
                    ).props("outlined dense").classes("w-full ph-akta-run-date")
                    akta_upload_status = ui.label("等待选择 AKTA zip 文件").classes(
                        "ph-muted ph-akta-upload-status"
                    )
                    with ui.row().classes("gap-2 items-center justify-end no-wrap ph-akta-upload-buttons"):
                        akta_mapping_button = ui.button(
                            "选择板位映射 CSV",
                            icon="table_chart",
                        ).props("outline no-wrap").classes("ph-akta-mapping-button")
                        akta_single_upload_button = ui.button(
                            "上传单个 AKTA ZIP",
                            icon="upload_file",
                        ).props("outline no-wrap").classes("ph-akta-single-upload-button")
                        akta_upload_button = ui.button(
                            "批量上传 AKTA 结果",
                            icon="upload_file",
                        ).props("unelevated no-wrap").classes("ph-akta-upload-button")

                    def akta_upload_js(*, multiple: bool) -> str:
                        multiple_value = "true" if multiple else "false"
                        return f"""
                        () => {{
                            const multiple = {multiple_value};
                            const dateInput = document.querySelector('.ph-akta-run-date input');
                            const statusLabel = document.querySelector('.ph-akta-upload-status');
                            const setStatus = (text) => {{
                                if (statusLabel) statusLabel.textContent = text;
                            }};
                            const runDate = dateInput ? dateInput.value.trim() : '';
                            if (!runDate) {{
                                setStatus('缺少 AKTA 日期');
                                phNotify('请先填写 AKTA 日期', 'negative');
                                return;
                            }}
                            const input = document.createElement('input');
                            input.type = 'file';
                            input.multiple = multiple;
                            input.accept = '.zip,application/zip';
                            input.style.display = 'none';
                            input.addEventListener('change', async () => {{
                                if (!input.files || input.files.length === 0) {{
                                    setStatus('未选择文件');
                                    input.remove();
                                    return;
                                }}
                                const selectedCount = input.files.length;
                                const form = new FormData();
                                form.append('run_date', runDate);
                                for (const file of input.files) {{
                                    form.append('files', file, file.name);
                                }}
                                const mappingFile = window.phAktaPositionMappingFile || null;
                                if (mappingFile) {{
                                    form.append('position_mapping_file', mappingFile, mappingFile.name);
                                }}
                                try {{
                                    setStatus(multiple
                                        ? `正在上传 ${{selectedCount}} 个 AKTA zip 并生成图片...`
                                        : '正在上传单个 AKTA zip 并生成图片...'
                                    );
                                    phNotify(multiple ? 'AKTA 批量结果上传中' : 'AKTA 单个结果上传中', 'info');
                                    const result = await phApi('/api/batches/{batch_id}/akta-results', {{
                                        method: 'POST',
                                        body: form,
                                    }});
                                    const details = result && result.experiment ? result.experiment.details || {{}} : {{}};
                                    const uploaded = Array.isArray(details.uploaded_positions)
                                        ? details.uploaded_positions
                                        : [];
                                    const skipped = Array.isArray(details.skipped_positions)
                                        ? details.skipped_positions
                                        : [];
                                    const skippedResultPositions = Array.isArray(details.skipped_result_positions)
                                        ? details.skipped_result_positions
                                        : [];
                                    if (skipped.length) {{
                                        const uploadedText = uploaded.length ? uploaded.join(', ') : '无';
                                        const skippedText = skipped.join(', ');
                                        setStatus(`AKTA 部分上传成功：成功 ${{uploadedText}}；失败 ${{skippedText}} 已传过`);
                                        phNotify(`AKTA 部分上传成功，失败板位：${{skippedText}} 已传过`, 'warning');
                                    }} else if (skippedResultPositions.length) {{
                                        const uploadedText = uploaded.length ? uploaded.join(', ') : '无';
                                        const skippedText = skippedResultPositions.join(', ');
                                        setStatus(`AKTA 部分上传成功：成功 ${{uploadedText}}；跳过未映射板位 ${{skippedText}}`);
                                        phNotify(`AKTA 部分结果上传成功，跳过未映射板位：${{skippedText}}`, 'warning');
                                    }} else {{
                                        const uploadedCount = uploaded.length || selectedCount;
                                        setStatus(multiple
                                            ? `AKTA 结果上传成功：${{uploadedCount}} 个文件`
                                            : 'AKTA 单个结果上传成功'
                                        );
                                        phNotify(multiple ? 'AKTA 结果上传成功' : 'AKTA 单个结果上传成功', 'positive');
                                    }}
                                    window.phAktaPositionMappingFile = null;
                                    setTimeout(() => window.location.reload(), 800);
                                }} catch (error) {{
                                    const message = error && error.message ? error.message : 'AKTA 导入失败';
                                    setStatus(`AKTA 结果上传失败：${{message}}`);
                                    phNotifyError(error, 'AKTA 导入失败');
                                }} finally {{
                                    input.remove();
                                }}
                            }}, {{once: true}});
                            document.body.appendChild(input);
                            input.click();
                        }}
                        """

                    akta_mapping_button.on(
                        "click",
                        js_handler=position_mapping_select_js(
                            state_name="phAktaPositionMappingFile",
                            status_selector=".ph-akta-upload-status",
                            waiting_text="等待选择 AKTA zip 文件",
                        ),
                    )
                    akta_single_upload_button.on(
                        "click",
                        js_handler=akta_upload_js(multiple=False),
                    )
                    akta_upload_button.on(
                        "click",
                        js_handler=akta_upload_js(multiple=True),
                    )

            with ui.dialog() as status_dialog, ui.card().classes("ph-dialog-card w-full max-w-2xl gap-4"):
                ui.label("修改批次状态").classes("text-lg font-semibold")
                batch_status_value = ui.select(
                    BATCH_ORDER_STATUS_OPTIONS,
                    value="not_ordered",
                    label="状态",
                    on_change=lambda event: handle_receipt_status_change(),
                ).props("outlined").classes("w-full")
                batch_receipt_note_value = ui.textarea(
                    "收货说明",
                    placeholder="例如：已收到 A1-A6，A7-A12 预计下周补发",
                ).props("outlined autogrow").classes("w-full")
                with ui.column().classes("w-full gap-2") as receipt_detail_section:
                    with ui.row().classes("w-full items-center justify-between gap-3"):
                        with ui.column().classes("gap-0"):
                            ui.label("收货明细").classes("font-semibold text-slate-800")
                            receipt_selection_label = ui.label("已选择 0/0 个孔位").classes("ph-meta")
                        with ui.row().classes("items-center gap-2"):
                            ui.button(
                                "全选",
                                icon="select_all",
                                on_click=lambda: set_receipt_selection(True),
                            ).props("flat dense no-wrap")
                            ui.button(
                                "清空",
                                icon="clear_all",
                                on_click=lambda: set_receipt_selection(False),
                            ).props("flat dense no-wrap")
                    receipt_wells_column = ui.column().classes("ph-receipt-well-list")
                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=status_dialog.close).props("flat")
                    ui.button(
                        "更新",
                        icon="published_with_changes",
                        on_click=lambda: update_batch_status(),
                    ).props("unelevated")

            translation_state = {"dna_fasta": ""}
            translation_in_flight = {"value": False}
            batch_editable_state = {
                "value": True,
                "can_write": True,
                "can_manage_receipt": False,
            }
            receipt_detail_state = {"wells": []}
            receipt_sync_state = {"updating": False}
            receipt_checkboxes: dict[int, object] = {}

            def _fasta_from_sequences(sequences: list[dict]) -> str:
                lines: list[str] = []
                for sequence in sequences:
                    lines.append(f">{sequence['position']} {sequence['protein_name']}")
                    dna_sequence = sequence.get("dna_sequence") or ""
                    lines.extend(
                        dna_sequence[index : index + 60]
                        for index in range(0, len(dna_sequence), 60)
                    )
                return "\n".join(lines) + ("\n" if lines else "")

            def _saved_translation_from_batch(data: dict) -> dict | None:
                batch = data["batch"]
                wells = data["wells"]
                sequences = [
                    {
                        "well_id": well["id"],
                        "position": well["position"],
                        "protein_id": well["protein_id"],
                        "protein_name": well["protein_name"],
                        "source_aa_sequence": well.get("source_aa_sequence")
                        or well.get("protein_sequence")
                        or "",
                        "translated_aa_sequence": well.get("translated_aa_sequence") or "",
                        "dna_sequence": well.get("dna_sequence") or "",
                    }
                    for well in wells
                    if well.get("dna_sequence")
                ]
                if not sequences:
                    return None
                return {
                    "padding": bool(batch.get("translation_padding")),
                    "add_additional_w": bool(batch.get("translation_additional_w")),
                    "organism": batch.get("translation_organism") or "E. coli",
                    "backbone": batch.get("translation_backbone") or "5",
                    "resistance": batch.get("translation_resistance") or "Amp",
                    "sequences": sequences,
                    "dna_fasta": _fasta_from_sequences(sequences),
                }

            def selected_receipt_well_ids() -> list[int]:
                if batch_status_value.value == "fully_received":
                    return [int(well["id"]) for well in receipt_detail_state["wells"]]
                if batch_status_value.value in {"not_ordered", "ordered"}:
                    return []
                return [
                    well_id
                    for well_id, checkbox in receipt_checkboxes.items()
                    if bool(checkbox.value)
                ]

            def sync_receipt_selection_label() -> None:
                total = len(receipt_detail_state["wells"])
                selected_count = len(selected_receipt_well_ids())
                receipt_selection_label.text = f"已选择 {selected_count}/{total} 个孔位"

            def handle_receipt_status_change() -> None:
                if receipt_sync_state["updating"]:
                    return
                receipt_sync_state["updating"] = True
                try:
                    if batch_status_value.value == "fully_received":
                        for checkbox in receipt_checkboxes.values():
                            checkbox.value = True
                    elif batch_status_value.value in {"not_ordered", "ordered"}:
                        for checkbox in receipt_checkboxes.values():
                            checkbox.value = False
                finally:
                    receipt_sync_state["updating"] = False
                sync_receipt_selection_label()

            def sync_receipt_status_from_selection() -> None:
                if receipt_sync_state["updating"]:
                    return
                total = len(receipt_detail_state["wells"])
                if not total:
                    sync_receipt_selection_label()
                    return
                selected_count = sum(
                    1 for checkbox in receipt_checkboxes.values() if bool(checkbox.value)
                )
                if selected_count == total:
                    batch_status_value.value = "fully_received"
                elif selected_count > 0:
                    batch_status_value.value = "partially_received"
                elif batch_status_value.value in {"partially_received", "fully_received"}:
                    batch_status_value.value = "ordered"
                sync_receipt_selection_label()

            def set_receipt_selection(received: bool) -> None:
                for checkbox in receipt_checkboxes.values():
                    checkbox.value = received
                sync_receipt_status_from_selection()

            def render_receipt_summary(wells: list[dict]) -> None:
                received_wells = [well for well in wells if well.get("received_at")]
                total = len(wells)
                receipt_detail_summary.text = (
                    f"收货明细：已收 {len(received_wells)}/{total} 个孔位"
                )
                if not received_wells:
                    receipt_positions_label.text = "暂无已收孔位"
                    receipt_positions_label.classes(replace="ph-muted")
                    return
                positions = [well["position"] for well in received_wells]
                preview = ", ".join(positions[:24])
                if len(positions) > 24:
                    preview = f"{preview} 等 {len(positions)} 个"
                receipt_positions_label.text = f"已收孔位：{preview}"
                receipt_positions_label.classes(replace="ph-meta")

            def render_receipt_well_options(wells: list[dict]) -> None:
                receipt_detail_state["wells"] = wells
                receipt_checkboxes.clear()
                receipt_wells_column.clear()
                with receipt_wells_column:
                    if not wells:
                        ui.label("暂无孔位").classes("ph-muted")
                    for well in wells:
                        received_at = format_datetime_minute(well.get("received_at"))
                        received_by = person_label(
                            well.get("received_by_name"),
                            well.get("received_by_email"),
                        )
                        with ui.element("div").classes("ph-receipt-well-row"):
                            checkbox = ui.checkbox(
                                value=bool(well.get("received_at")),
                                on_change=lambda event: sync_receipt_status_from_selection(),
                            ).props("dense")
                            receipt_checkboxes[int(well["id"])] = checkbox
                            ui.label(well["position"]).classes("ph-mapping-position")
                            with ui.column().classes("min-w-0 gap-0"):
                                ui.label(well["protein_name"]).classes("font-medium")
                                ui.label(f"{len(well.get('protein_sequence') or '')} aa").classes("ph-meta")
                            ui.badge(well.get("protein_type") or "无").props("outline")
                            ui.label(
                                f"{received_by} · {received_at}" if received_at else "未收货"
                            ).classes("ph-meta")
                sync_receipt_selection_label()

            async def download_plate_workbook() -> None:
                try:
                    await ui.run_javascript(
                        f"""
                        const token = phToken();
                        const response = await fetch('/api/batches/{batch_id}/plate/export', {{
                            headers: {{Authorization: `Bearer ${{token}}`}}
                        }});
                        if (!response.ok) {{
                            const text = await response.text();
                            let detail = text || 'Download failed';
                            try {{
                                const parsed = JSON.parse(text);
                                detail = parsed.detail || detail;
                            }} catch (error) {{}}
                            throw new Error(phErrorText(detail));
                        }}
                        const blob = await response.blob();
                        const disposition = response.headers.get('content-disposition') || '';
                        const match = disposition.match(/filename="([^"]+)"/);
                        const filename = match ? match[1] : 'batch-{batch_id}-plate.xlsx';
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        URL.revokeObjectURL(url);
                        """,
                        timeout=30,
                    )
                except Exception as error:
                    notify_error(error)

            async def download_summary_workbook() -> None:
                try:
                    await ui.run_javascript(
                        f"""
                        const token = phToken();
                        const response = await fetch('/api/batches/{batch_id}/summary/export', {{
                            headers: {{Authorization: `Bearer ${{token}}`}}
                        }});
                        if (!response.ok) {{
                            const text = await response.text();
                            let detail = text || 'Download failed';
                            try {{
                                const parsed = JSON.parse(text);
                                detail = parsed.detail || detail;
                            }} catch (error) {{}}
                            throw new Error(phErrorText(detail));
                        }}
                        const blob = await response.blob();
                        const disposition = response.headers.get('content-disposition') || '';
                        const match = disposition.match(/filename="([^"]+)"/);
                        const filename = match ? match[1] : 'batch-{batch_id}-summary.xlsx';
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        URL.revokeObjectURL(url);
                        """,
                        timeout=30,
                    )
                except Exception as error:
                    notify_error(error)

            async def translate_batch_sequences_ui() -> None:
                if not batch_editable_state["can_write"]:
                    ui.notify("只读模式，不能重新翻译", type="warning")
                    return
                if not batch_editable_state["value"]:
                    ui.notify("批次已下单，不能重新翻译", type="warning")
                    return
                if translation_in_flight["value"]:
                    return
                translation_in_flight["value"] = True
                previous_status = translation_status.text
                previous_button_text = translate_button.text
                translate_button.text = "翻译中"
                translate_button.disable()
                translation_status.text = "翻译中，较大的批次可能需要几分钟"
                ui.notify("翻译已开始，完成前请不要关闭页面", type="info")
                payload = {
                    "padding": translation_padding.value == "yes",
                    "add_additional_w": translation_add_w.value == "yes",
                    "organism": translation_organism.value or "E. coli",
                    "backbone": translation_backbone.value or "5",
                    "resistance": translation_resistance.value or "Amp",
                }
                try:
                    result = await ui.run_javascript(
                        f"""
                        return await phApi('/api/batches/{batch_id}/translations', {{
                            method: 'POST',
                            body: {json.dumps(payload)},
                        }});
                        """,
                        timeout=TRANSLATION_REQUEST_TIMEOUT_SECONDS,
                    )
                    render_translation(result)
                    ui.notify("翻译完成", type="positive")
                except Exception as error:
                    message = str(error).strip()
                    if message.startswith("Error: "):
                        message = message.removeprefix("Error: ").strip()
                    translation_status.text = f"翻译失败：{message or '操作失败'}"
                    notify_error(error)
                finally:
                    translate_button.text = previous_button_text
                    if batch_editable_state["value"]:
                        translate_button.enable()
                    else:
                        translate_button.disable()
                    translation_in_flight["value"] = False

            async def download_translation_sequences() -> None:
                if not translation_state["dna_fasta"]:
                    ui.notify("还没有翻译结果", type="warning")
                    return
                try:
                    await ui.run_javascript(
                        f"""
                        const fasta = {json.dumps(translation_state["dna_fasta"])};
                        const blob = new Blob([fasta], {{type: 'text/plain;charset=utf-8'}});
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'batch-{batch_id}-translated-dna.fasta';
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        URL.revokeObjectURL(url);
                        """,
                        timeout=10,
                    )
                except Exception as error:
                    notify_error(error)

            def render_translation(result: dict, *, sync_controls: bool = True) -> None:
                translation_results.clear()
                translation_state["dna_fasta"] = result.get("dna_fasta") or ""
                sequences = result.get("sequences") or []
                if sync_controls:
                    translation_padding.value = "yes" if result.get("padding") else "no"
                    translation_add_w.value = "yes" if result.get("add_additional_w") else "no"
                    translation_organism.value = result.get("organism") or "E. coli"
                    translation_backbone.value = result.get("backbone") or "5"
                    translation_resistance.value = result.get("resistance") or "Amp"
                translation_status.text = (
                    f"{len(sequences)} 条 DNA 序列 · {result['organism']} · BB {result['backbone']} · {result['resistance']}"
                )
                with translation_results:
                    with ui.element("div").classes("ph-translation-row ph-mapping-head"):
                        ui.label("孔位").classes("ph-mapping-cell")
                        ui.label("蛋白").classes("ph-mapping-cell")
                        ui.label("AA").classes("ph-mapping-cell")
                        ui.label("DNA").classes("ph-mapping-cell")
                        ui.label("长度").classes("ph-mapping-cell")
                    if not sequences:
                        with ui.element("div").classes("ph-translation-row"):
                            ui.label("暂无").classes("ph-mapping-cell ph-mapping-position")
                            ui.label("暂无翻译结果").classes("ph-mapping-cell")
                            ui.label("").classes("ph-mapping-cell")
                            ui.label("").classes("ph-mapping-cell")
                            ui.label("").classes("ph-mapping-cell")
                    for sequence in sequences:
                        dna_sequence = sequence.get("dna_sequence") or ""
                        aa_sequence = sequence.get("translated_aa_sequence") or ""
                        dna_preview = dna_sequence[:72] + ("..." if len(dna_sequence) > 72 else "")
                        with ui.element("div").classes("ph-translation-row"):
                            ui.label(sequence["position"]).classes("ph-mapping-cell ph-mapping-position")
                            ui.label(sequence["protein_name"]).classes("ph-mapping-cell")
                            ui.label(f"{len(aa_sequence)} aa").classes("ph-mapping-cell")
                            ui.label(dna_preview).classes("ph-mapping-cell ph-mapping-sequence")
                            ui.label(f"{len(dna_sequence)} bp").classes("ph-mapping-cell")

            async def save_well_position(well_id: int, position: str) -> None:
                if not batch_editable_state["can_write"]:
                    ui.notify("只读模式，不能修改孔位", type="warning")
                    return
                if not batch_editable_state["value"]:
                    ui.notify("批次已下单，不能修改孔位", type="warning")
                    return
                try:
                    result = await ui.run_javascript(
                        f"""
                        const wellId = {well_id};
                        const position = {json.dumps(position)};
                        const token = phToken();
                        const request = (mode) => fetch(
                            `/api/batches/{batch_id}/wells/${{wellId}}/position`,
                            {{
                                method: 'PATCH',
                                headers: {{
                                    Authorization: `Bearer ${{token}}`,
                                    'Content-Type': 'application/json',
                                }},
                                body: JSON.stringify({{position, mode}}),
                            }}
                        );
                        let response = await request('move');
                        if (response.status === 409) {{
                            const confirmed = window.confirm('目标孔位已有蛋白，是否交换孔位？');
                            if (!confirmed) return {{changed: false}};
                            response = await request('swap');
                        }}
                        const contentType = response.headers.get('content-type') || '';
                        const data = contentType.includes('application/json')
                            ? await response.json()
                            : await response.text();
                        if (!response.ok) {{
                            const detail = data && data.detail ? data.detail : data || 'Request failed';
                            throw new Error(phErrorText(detail));
                        }}
                        return {{changed: true, data}};
                        """,
                        timeout=10,
                    )
                    if result and result.get("changed"):
                        render_batch(result["data"])
                except Exception as error:
                    notify_error(error)

            async def update_batch_status() -> None:
                try:
                    payload = {"order_status": batch_status_value.value}
                    if batch_editable_state["can_manage_receipt"]:
                        payload["receipt_note"] = batch_receipt_note_value.value or ""
                        payload["received_well_ids"] = selected_receipt_well_ids()
                    result = await ui.run_javascript(
                        f"""
                        return await phApi('/api/batches/{batch_id}/status', {{
                            method: 'PATCH',
                            body: {json.dumps(payload)},
                        }});
                        """,
                        timeout=10,
                    )
                    status_dialog.close()
                    render_batch(result)
                    ui.notify("批次状态已更新", type="positive")
                except Exception as error:
                    notify_error(error)

            def render_batch(data: dict) -> None:
                mapping_table.clear()
                score_density_column.clear()
                batch = data["batch"]
                wells = data["wells"]
                experiments = data["experiments"]
                score_density_plots = data.get("score_density_plots") or []
                order_status = batch.get("order_status") or "not_ordered"
                can_write_batch = data.get("access_role") in {"owner", "member"}
                can_manage_receipt = data.get("access_role") == "owner"
                batch_editable = can_write_batch and order_status == "not_ordered"
                batch_editable_state["value"] = batch_editable
                batch_editable_state["can_write"] = can_write_batch
                batch_editable_state["can_manage_receipt"] = can_manage_receipt
                batch_title.text = batch["name"]
                batch_description.text = batch["description"] or "暂无描述"
                batch_status_badge.text = humanize(order_status)
                batch_status_value.value = order_status
                batch_receipt_note_value.value = batch.get("receipt_note") or ""
                batch_receipt_note_value.visible = can_manage_receipt
                receipt_detail_section.visible = can_manage_receipt
                batch_status_button.visible = (
                    can_write_batch and order_status != "fully_received"
                ) or can_manage_receipt
                receipt_edit_button.visible = can_manage_receipt
                receipt_note = batch.get("receipt_note") or ""
                receipt_note_label.text = receipt_note or "暂无收货说明"
                receipt_note_label.classes(
                    replace=(
                        "ph-muted whitespace-pre-wrap"
                        if not receipt_note
                        else "whitespace-pre-wrap"
                    )
                )
                receipt_updated_at = format_datetime_minute(batch.get("receipt_updated_at"))
                receipt_meta_label.text = (
                    f"最后更新：{person_label(batch.get('receipt_updated_by_name'), batch.get('receipt_updated_by_email'))} · {receipt_updated_at}"
                    if receipt_updated_at
                    else "项目负责人可以在这里记录部分收货情况"
                )
                render_receipt_summary(wells)
                render_receipt_well_options(wells)
                batch_meta.clear()
                with batch_meta:
                    ui.badge(f"{batch['plate_format']} 孔").props("outline")
                    ui.badge(humanize(order_status)).props("outline color=secondary")
                    ui.badge(f"{len(wells)} 个蛋白").props("outline color=secondary")
                    ui.badge(f"{len(experiments)} 个实验").props("outline color=secondary")
                for control in (
                    translation_padding,
                    translation_add_w,
                    translation_organism,
                    translation_backbone,
                    translation_resistance,
                ):
                    if batch_editable:
                        control.enable()
                    else:
                        control.disable()
                if batch_editable:
                    translate_button.enable()
                else:
                    translate_button.disable()
                mapping_summary.text = (
                    f"{batch['plate_format']} 孔 · {len(wells)} 条蛋白映射 · {len(experiments)} 个实验记录"
                )
                spr_run_date.visible = can_write_batch
                spr_mapping_button.visible = can_write_batch
                spr_upload_button.visible = can_write_batch
                spr_concentration_button.visible = can_write_batch
                spr_mapping_button.enable()
                spr_upload_button.enable()
                spr_concentration_button.enable()
                spr_upload_status.text = (
                    "等待选择 SPR PPTX 文件" if can_write_batch else "只读模式"
                )
                hplc_mapping_button.visible = can_write_batch
                hplc_upload_button.visible = can_write_batch
                hplc_mapping_button.enable()
                hplc_upload_button.enable()
                hplc_upload_status.text = (
                    "等待选择 HPLC 文件夹" if can_write_batch else "只读模式"
                )
                akta_run_date.visible = can_write_batch
                akta_mapping_button.visible = can_write_batch
                akta_single_upload_button.visible = can_write_batch
                akta_upload_button.visible = can_write_batch
                akta_mapping_button.enable()
                akta_single_upload_button.enable()
                akta_upload_button.enable()
                akta_upload_status.text = (
                    "等待选择 AKTA zip 文件" if can_write_batch else "只读模式"
                )
                saved_translation = _saved_translation_from_batch(data)
                if saved_translation:
                    render_translation(
                        saved_translation,
                        sync_controls=not bool(translation_state["dna_fasta"]),
                    )
                elif not translation_state["dna_fasta"]:
                    translation_results.clear()
                    translation_status.text = "等待翻译"
                    translation_state["dna_fasta"] = ""
                with score_density_column:
                    if not score_density_plots:
                        empty_state(
                            "show_chart",
                            "暂无打分密度图",
                            "这个批次里还没有可用于作图的数值字段。",
                        )
                    else:
                        with ui.element("div").classes("ph-score-density-grid"):
                            for plot in score_density_plots:
                                with ui.element("div").classes("ph-score-density-card"):
                                    with ui.row().classes("ph-score-density-card-header"):
                                        with ui.column().classes("gap-0"):
                                            ui.label(plot["label"]).classes("font-semibold text-slate-900")
                                            ui.label(
                                                f"{plot['sample_count']} 个数值"
                                            ).classes("ph-meta")
                                        ui.badge(plot["metric"]).props("outline")
                                    with ui.element("div").classes("ph-score-density-frame"):
                                        ui.html(plot["svg"])
                with mapping_table:
                    with ui.element("div").classes("ph-mapping-row ph-mapping-head"):
                        ui.label("孔位").classes("ph-mapping-cell")
                        ui.label("蛋白").classes("ph-mapping-cell")
                        ui.label("类型").classes("ph-mapping-cell")
                        ui.label("收货").classes("ph-mapping-cell")
                        ui.label("AA 序列").classes("ph-mapping-cell")
                        ui.label("长度").classes("ph-mapping-cell")
                        ui.label("操作").classes("ph-mapping-cell")
                    if not wells:
                        with ui.element("div").classes("ph-mapping-row"):
                            ui.label("暂无").classes("ph-mapping-cell ph-mapping-position")
                            ui.label("暂无蛋白映射").classes("ph-mapping-cell")
                            ui.label("").classes("ph-mapping-cell")
                            ui.label("").classes("ph-mapping-cell")
                            ui.label("").classes("ph-mapping-cell")
                            ui.label("").classes("ph-mapping-cell")
                            ui.label("").classes("ph-mapping-cell")
                    for well in wells:
                        sequence = well.get("source_aa_sequence") or well.get("protein_sequence") or ""
                        sequence_preview = sequence[:50] + ("..." if len(sequence) > 50 else "")
                        with ui.element("div").classes("ph-mapping-row"):
                            with ui.element("div").classes("ph-mapping-cell"):
                                position_select = (
                                    ui.select(
                                        PLATE_96_POSITION_OPTIONS,
                                        value=well["position"],
                                    )
                                    .props("outlined dense")
                                    .classes("w-full")
                                )
                                if not batch_editable:
                                    position_select.disable()
                            ui.label(well["protein_name"]).classes("ph-mapping-cell")
                            ui.label(well.get("protein_type") or "无").classes("ph-mapping-cell")
                            ui.label(
                                "已收" if well.get("received_at") else "未收"
                            ).classes("ph-mapping-cell")
                            ui.label(sequence_preview).classes("ph-mapping-cell ph-mapping-sequence")
                            ui.label(f"{len(sequence)} aa").classes("ph-mapping-cell")
                            with ui.element("div").classes("ph-mapping-cell"):
                                save_button = ui.button(
                                    "保存",
                                    icon="save",
                                    on_click=lambda w=well, select=position_select: save_well_position(
                                        w["id"], select.value
                                    ),
                                ).props("flat dense no-wrap")
                                if not batch_editable:
                                    save_button.disable()

            async def load_batch() -> None:
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/batches/{batch_id}')", timeout=10)
                    render_batch(data)
                except Exception as error:
                    notify_error(error)

            await load_batch()

    @ui.page("/proteins/{protein_id}")
    async def protein_page(protein_id: int) -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("蛋白").classes("ph-eyebrow")
                    protein_title = ui.label("蛋白").classes("ph-title")
                    protein_description = ui.label().classes("ph-subtitle")
                with ui.column().classes("items-end gap-2"):
                    ui.button("返回", icon="arrow_back", on_click=lambda: ui.run_javascript("history.back()")).props("flat")
                    protein_meta = ui.row().classes("gap-2")

            with ui.column().classes("ph-sequence-panel"):
                with ui.row().classes("w-full items-center justify-between border-b border-slate-200 px-4 py-3"):
                    ui.label("氨基酸序列").classes("font-semibold text-slate-800")
                    sequence_length_badge = ui.badge().props("outline")
                sequence_text = ui.label().classes("ph-sequence-text")

            score_details_section = ui.column().classes("w-full gap-3")

            with ui.row().classes("ph-section-bar w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("结构文件").classes("text-xl font-semibold")
                    ui.label("这个蛋白导入时保存的 PDB/mmCIF 文件。").classes("ph-muted")
            structure_file_column = ui.column().classes("w-full gap-3")
            structure_viewer_id = f"ph-structure-viewer-{protein_id}"

            with ui.row().classes("ph-section-bar w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("批次结果").classes("text-xl font-semibold")
                    ui.label("这个蛋白在实验批次中的孔位和回填结果。").classes("ph-muted")
            batch_results_column = ui.column().classes("w-full gap-3")

            with ui.row().classes("ph-section-bar w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("实验资料").classes("text-xl font-semibold")
                    ui.label("这个蛋白关联的文件和生成结果会显示在这里。").classes("ph-muted")
            artifacts_column = ui.column().classes("w-full gap-3")

            with ui.dialog() as similarity_dialog, ui.card().classes("ph-dialog-card w-full max-w-2xl gap-4"):
                similarity_title = ui.label("相似蛋白").classes("text-lg font-semibold")
                similarity_subtitle = ui.label().classes("ph-meta")
                similarity_matches_column = ui.column().classes("w-full gap-2")
                with ui.row().classes("justify-end w-full"):
                    ui.button("关闭", on_click=similarity_dialog.close).props("flat")

            def open_similarity_dialog(protein: dict) -> None:
                similarity_title.text = "高相似度匹配"
                similarity_subtitle.text = protein.get("name") or "未命名蛋白"
                _render_sequence_similarity_matches(protein, similarity_matches_column)
                similarity_dialog.open()

            def reset_structure_view() -> None:
                ui.run_javascript(
                    f"phResetProteinStructureView({json.dumps(structure_viewer_id)})"
                )

            async def render_protein_structure(protein: dict) -> None:
                try:
                    await ui.run_javascript(
                        "return await phRenderProteinStructure("
                        + json.dumps(
                            {
                                "containerId": structure_viewer_id,
                                "downloadPath": (
                                    f"/api/proteins/{protein_id}/structure/download"
                                ),
                                "filename": protein.get("structure_filename") or "",
                                "mimeType": protein.get("structure_mime_type") or "",
                            }
                        )
                        + ")",
                        timeout=45,
                    )
                except Exception as error:
                    notify_error(error, "结构视图加载失败")

            async def load_protein() -> None:
                artifacts_column.clear()
                batch_results_column.clear()
                score_details_section.clear()
                structure_file_column.clear()
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/proteins/{protein_id}')", timeout=10)
                    protein = data["protein"]
                    can_delete_artifacts = data.get("access_role") == "owner"
                    spr_notes_by_artifact_id = _spr_result_notes_by_artifact_id(
                        data["batch_results"]
                    )
                    hplc_notes_by_artifact_id = _hplc_result_notes_by_artifact_id(
                        data["batch_results"]
                    )
                    protein_title.text = protein["name"]
                    sequence_text.text = sequence_display(protein["sequence"])
                    protein_description.text = protein["description"] or "暂无描述"
                    sequence_length_badge.text = f"{len(protein['sequence'])} 个氨基酸"
                    protein_meta.clear()
                    with protein_meta:
                        if protein["protein_type"]:
                            ui.badge(protein["protein_type"]).props("outline")
                        ui.label(
                            protein_manual_rating_label(protein.get("manual_rating"))
                        ).classes(
                            protein_manual_rating_class(protein.get("manual_rating"))
                        )
                        if protein["target"]:
                            ui.badge(f"靶标 {protein['target']}").props("outline color=secondary")
                        _render_sequence_similarity_badge(protein, open_similarity_dialog)
                    with score_details_section:
                        score_details = protein.get("score_details") or {}
                        if score_details:
                            with ui.row().classes("ph-section-bar w-full"):
                                with ui.column().classes("gap-0"):
                                    ui.label("打分表数据").classes("text-xl font-semibold")
                                    ui.label("上传打分表时按 pdb_name 匹配到这个蛋白的表格数据。").classes("ph-muted")
                            with ui.element("div").classes("ph-spr-result-grid"):
                                for key_text, value_text in score_details.items():
                                    with ui.element("div").classes("ph-spr-result-item"):
                                        ui.label(str(key_text)).classes("ph-spr-result-key")
                                        ui.label(str(value_text)).classes("ph-spr-result-value")
                    with structure_file_column:
                        if not protein["structure_storage_path"]:
                            empty_state("description", "还没有结构文件", "从 PDB/mmCIF 新建或批量导入设计蛋白后会显示在这里。")
                        else:
                            with ui.row().classes("ph-file-row"):
                                with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                    with ui.element("div").classes("ph-icon-box ph-icon-artifact"):
                                        ui.icon("view_in_ar")
                                    with ui.column().classes("min-w-0 gap-1"):
                                        ui.label(protein["structure_filename"]).classes("font-semibold text-slate-900")
                                        ui.label(format_bytes(protein["structure_size_bytes"])).classes("ph-meta")
                                ui.button(
                                    "下载",
                                    icon="download",
                                    on_click=lambda p=protein: download_protein_structure(
                                        p["structure_filename"]
                                    ),
                                ).props("flat")
                            with ui.column().classes("ph-structure-viewer"):
                                with ui.row().classes("ph-structure-viewer-header"):
                                    with ui.column().classes("gap-0"):
                                        ui.label("3D 结构").classes("font-semibold text-slate-800")
                                        ui.label("Mol* Viewer").classes("ph-meta")
                                    with ui.row().classes("ph-structure-viewer-actions"):
                                        reset_button = ui.button(
                                            icon="center_focus_strong",
                                            on_click=reset_structure_view,
                                        ).props("flat round dense")
                                        with reset_button:
                                            ui.tooltip("重置视角")
                                ui.html(
                                    (
                                        f'<div id="{structure_viewer_id}" '
                                        'class="ph-structure-viewer-frame">'
                                        '<div class="ph-structure-viewer-status">'
                                        "等待加载 3D 结构..."
                                        "</div>"
                                        "</div>"
                                    )
                                ).classes("w-full")
                            await render_protein_structure(protein)
                    with batch_results_column:
                        if not data["batch_results"]:
                            empty_state("grid_view", "还没有批次结果", "把这个蛋白加入实验批次后，结果会显示在这里。")
                        for result in data["batch_results"]:
                            with ui.row().classes("ph-file-row"):
                                with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                    with ui.element("div").classes("ph-icon-box ph-icon-protein"):
                                        ui.icon("grid_view")
                                    with ui.column().classes("min-w-0 gap-1"):
                                        ui.label(
                                            f"{result['batch_name']} · {result['experiment_name']} · {result['position']}"
                                        ).classes("font-semibold text-slate-900")
                                        meta = result["experiment_type"]
                                        ui.label(meta).classes("ph-meta")
                                        ui.label(result.get("result_value") or "未回填").classes("text-sm text-slate-800")
                                        note_text = _batch_result_note_text(result)
                                        if note_text:
                                            ui.label(note_text).classes("ph-card-description")
                                ui.button(
                                    "打开批次",
                                    icon="open_in_new",
                                    on_click=lambda r=result: ui.navigate.to(f"/batches/{r['batch_id']}"),
                                ).props("flat")
                    with artifacts_column:
                        if not data["artifacts"]:
                            empty_state("description", "还没有实验资料", "从批次上传或系统生成后会显示在这里。")
                        akta_preview_artifact_ids = []
                        spr_preview_artifact_ids = []
                        hplc_preview_artifact_ids = []
                        grouped: dict[str, list[dict]] = {}
                        group_titles: dict[str, str] = {}
                        for key, title_text in ARTIFACT_GROUPS:
                            grouped.setdefault(key, [])
                            group_titles[key] = title_text
                        for artifact in data["artifacts"]:
                            key = artifact["artifact_type"] if artifact["artifact_type"] in grouped else "other"
                            grouped.setdefault(key, []).append(artifact)
                        for key, files in grouped.items():
                            if not files:
                                continue
                            with ui.column().classes("ph-artifact-group"):
                                ui.label(group_titles.get(key, humanize(key))).classes("font-semibold text-slate-800")
                                for artifact in files:
                                    if _is_akta_png_artifact(artifact):
                                        akta_preview_artifact_ids.append(artifact["id"])
                                        akta_run_date = _run_date_from_prefixed_filename(
                                            artifact["filename"], "AKTA_"
                                        )
                                        with ui.column().classes("ph-akta-preview"):
                                            with ui.row().classes("ph-akta-preview-header"):
                                                with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                                    with ui.element("div").classes("ph-icon-box ph-icon-artifact"):
                                                        ui.icon("show_chart")
                                                    with ui.column().classes("min-w-0 gap-1"):
                                                        ui.label(artifact["filename"]).classes("font-semibold text-slate-900")
                                                        ui.label(
                                                            _preview_meta(
                                                                "AKTA 在线预览",
                                                                akta_run_date,
                                                                format_bytes(artifact["size_bytes"]),
                                                            )
                                                        ).classes("ph-meta")
                                                with ui.row().classes("gap-2"):
                                                    ui.button(
                                                        "下载",
                                                        icon="download",
                                                        on_click=lambda a=artifact: download_artifact(a["id"], a["filename"]),
                                                    ).props("flat")
                                            with ui.element("div").classes("ph-akta-preview-frame"):
                                                ui.html(
                                                    (
                                                        '<div class="ph-akta-preview-content">'
                                                        '<img class="ph-akta-preview-image" '
                                                        f'data-akta-artifact-id="{artifact["id"]}" '
                                                        f'alt="{html_escape(artifact["filename"], quote=True)}">'
                                                        '<div class="ph-muted ph-akta-preview-status">'
                                                        "正在加载 AKTA 图像..."
                                                        "</div>"
                                                        "</div>"
                                                    )
                                                )
                                    elif _is_hplc_svg_artifact(artifact):
                                        hplc_preview_artifact_ids.append(artifact["id"])
                                        hplc_note = hplc_notes_by_artifact_id.get(
                                            artifact["id"], {}
                                        )
                                        with ui.column().classes("ph-akta-preview"):
                                            with ui.row().classes("ph-akta-preview-header"):
                                                with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                                    with ui.element("div").classes("ph-icon-box ph-icon-artifact"):
                                                        ui.icon("show_chart")
                                                    with ui.column().classes("min-w-0 gap-1"):
                                                        ui.label(artifact["filename"]).classes("font-semibold text-slate-900")
                                                        ui.label(
                                                            _preview_meta(
                                                                "HPLC 在线预览",
                                                                hplc_note.get("plate_position") or "",
                                                                format_bytes(artifact["size_bytes"]),
                                                            )
                                                        ).classes("ph-meta")
                                                with ui.row().classes("gap-2"):
                                                    ui.button(
                                                        "下载",
                                                        icon="download",
                                                        on_click=lambda a=artifact: download_artifact(a["id"], a["filename"]),
                                                    ).props("flat")
                                            with ui.element("div").classes("ph-akta-preview-frame"):
                                                ui.html(
                                                    (
                                                        '<div class="ph-akta-preview-content">'
                                                        '<img class="ph-akta-preview-image" '
                                                        f'data-hplc-artifact-id="{artifact["id"]}" '
                                                        f'alt="{html_escape(artifact["filename"], quote=True)}">'
                                                        '<div class="ph-muted ph-akta-preview-status">'
                                                        "正在加载 HPLC 图像..."
                                                        "</div>"
                                                        "</div>"
                                                    )
                                                )
                                            display_items = _hplc_display_items(hplc_note)
                                            if display_items:
                                                with ui.element("div").classes("ph-spr-result-grid"):
                                                    for key_text, value_text in display_items:
                                                        with ui.element("div").classes("ph-spr-result-item"):
                                                            ui.label(key_text).classes("ph-spr-result-key")
                                                            ui.label(value_text).classes("ph-spr-result-value")
                                    elif _is_spr_svg_artifact(artifact):
                                        spr_preview_artifact_ids.append(artifact["id"])
                                        spr_note = spr_notes_by_artifact_id.get(
                                            artifact["id"], {}
                                        )
                                        with ui.column().classes("ph-akta-preview"):
                                            with ui.row().classes("ph-akta-preview-header"):
                                                with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                                    with ui.element("div").classes("ph-icon-box ph-icon-artifact"):
                                                        ui.icon("show_chart")
                                                    with ui.column().classes("min-w-0 gap-1"):
                                                        ui.label(artifact["filename"]).classes("font-semibold text-slate-900")
                                                        sample_id = spr_note.get("sample_id") or "SPR"
                                                        spr_run_date = str(
                                                            spr_note.get("run_date") or ""
                                                        )
                                                        ui.label(
                                                            _preview_meta(
                                                                "SPR 在线预览",
                                                                sample_id,
                                                                spr_run_date,
                                                                format_bytes(artifact["size_bytes"]),
                                                            )
                                                        ).classes("ph-meta")
                                                with ui.row().classes("gap-2"):
                                                    ui.button(
                                                        "下载",
                                                        icon="download",
                                                        on_click=lambda a=artifact: download_artifact(a["id"], a["filename"]),
                                                    ).props("flat")
                                            with ui.element("div").classes("ph-akta-preview-frame"):
                                                ui.html(
                                                    (
                                                        '<div class="ph-akta-preview-content">'
                                                        '<img class="ph-akta-preview-image" '
                                                        f'data-spr-artifact-id="{artifact["id"]}" '
                                                        f'alt="{html_escape(artifact["filename"], quote=True)}">'
                                                        '<div class="ph-muted ph-akta-preview-status">'
                                                        "正在加载 SPR 图像..."
                                                        "</div>"
                                                        "</div>"
                                                    )
                                                )
                                            display_items = _spr_table_display_items(
                                                spr_note.get("table_row")
                                            )
                                            if display_items:
                                                with ui.element("div").classes("ph-spr-result-grid"):
                                                    for key_text, value_text in display_items:
                                                        with ui.element("div").classes("ph-spr-result-item"):
                                                            ui.label(key_text).classes("ph-spr-result-key")
                                                            ui.label(value_text).classes("ph-spr-result-value")
                                    else:
                                        with ui.row().classes("ph-file-row"):
                                            with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                                with ui.element("div").classes("ph-icon-box ph-icon-artifact"):
                                                    ui.icon("description")
                                                with ui.column().classes("min-w-0 gap-1"):
                                                    ui.label(artifact["filename"]).classes("font-semibold text-slate-900")
                                                    ui.label(f"{humanize(artifact['artifact_type'])} · {format_bytes(artifact['size_bytes'])}").classes("ph-meta")
                                            with ui.row().classes("gap-2"):
                                                ui.button("下载", icon="download", on_click=lambda a=artifact: download_artifact(a["id"], a["filename"])).props("flat")
                                                delete_button = ui.button("删除", icon="delete", on_click=lambda a=artifact: delete_artifact(a["id"])).props("flat color=negative")
                                                delete_button.visible = (
                                                    can_delete_artifacts
                                                    and artifact["artifact_type"] != "experimental_result"
                                                )
                        if akta_preview_artifact_ids:
                            await load_preview_images(
                                akta_preview_artifact_ids,
                                data_attribute="data-akta-artifact-id",
                                error_message="AKTA 图像加载失败",
                            )
                        if spr_preview_artifact_ids:
                            await load_preview_images(
                                spr_preview_artifact_ids,
                                data_attribute="data-spr-artifact-id",
                                error_message="SPR 图像加载失败",
                            )
                        if hplc_preview_artifact_ids:
                            await load_preview_images(
                                hplc_preview_artifact_ids,
                                data_attribute="data-hplc-artifact-id",
                                error_message="HPLC 图像加载失败",
                            )
                except Exception as error:
                    notify_error(error)

            async def download_protein_structure(filename: str) -> None:
                escaped_filename = filename.replace("\\", "\\\\").replace("'", "\\'")
                try:
                    await ui.run_javascript(
                        f"""
                        const token = phToken();
                        const response = await fetch('/api/proteins/{protein_id}/structure/download', {{
                            headers: {{Authorization: `Bearer ${{token}}`}}
                        }});
                        if (!response.ok) {{
                            const text = await response.text();
                            let detail = text || 'Download failed';
                            try {{
                                const parsed = JSON.parse(text);
                                detail = parsed.detail || detail;
                            }} catch (error) {{}}
                            throw new Error(phErrorText(detail));
                        }}
                        const blob = await response.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = '{escaped_filename}';
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        URL.revokeObjectURL(url);
                        """,
                        timeout=30,
                    )
                except Exception as error:
                    notify_error(error)

            async def download_artifact(artifact_id: int, filename: str) -> None:
                escaped_filename = filename.replace("\\", "\\\\").replace("'", "\\'")
                try:
                    await ui.run_javascript(
                        f"""
                        const token = phToken();
                        const response = await fetch('/api/artifacts/{artifact_id}/download', {{
                            headers: {{Authorization: `Bearer ${{token}}`}}
                        }});
                        if (!response.ok) {{
                            const text = await response.text();
                            let detail = text || 'Download failed';
                            try {{
                                const parsed = JSON.parse(text);
                                detail = parsed.detail || detail;
                            }} catch (error) {{}}
                            throw new Error(phErrorText(detail));
                        }}
                        const blob = await response.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = '{escaped_filename}';
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        URL.revokeObjectURL(url);
                        """,
                        timeout=30,
                    )
                except Exception as error:
                    notify_error(error)

            async def delete_artifact(artifact_id: int) -> None:
                try:
                    await ui.run_javascript(f"return await phApi('/api/artifacts/{artifact_id}', {{method: 'DELETE'}})", timeout=10)
                    await load_protein()
                except Exception as error:
                    notify_error(error)

            async def load_preview_images(
                artifact_ids: list[int],
                *,
                data_attribute: str,
                error_message: str,
            ) -> None:
                try:
                    await ui.run_javascript(
                        f"""
                        const artifactIds = {json.dumps(artifact_ids)};
                        const dataAttribute = {json.dumps(data_attribute)};
                        const errorMessage = {json.dumps(error_message, ensure_ascii=False)};
                        const waitForPreviewImage = async (artifactId) => {{
                            for (let attempt = 0; attempt < 20; attempt += 1) {{
                                const image = document.querySelector(`[${{dataAttribute}}="${{artifactId}}"]`);
                                if (image) return image;
                                await new Promise((resolve) => setTimeout(resolve, 50));
                            }}
                            return null;
                        }};
                        await Promise.all(artifactIds.map(async (artifactId) => {{
                            const image = await waitForPreviewImage(artifactId);
                            if (!image) return;
                            const frame = image.closest('.ph-akta-preview-frame');
                            const status = frame ? frame.querySelector('.ph-akta-preview-status') : null;
                            try {{
                                const token = phToken();
                                const response = await fetch(`/api/artifacts/${{artifactId}}/download`, {{
                                    headers: {{Authorization: `Bearer ${{token}}`}}
                                }});
                                if (!response.ok) {{
                                    const text = await response.text();
                                    let detail = text || errorMessage;
                                    try {{
                                        const parsed = JSON.parse(text);
                                        detail = parsed.detail || detail;
                                    }} catch (error) {{}}
                                    throw new Error(phErrorText(detail));
                                }}
                                const blob = await response.blob();
                                const previousUrl = image.dataset.objectUrl;
                                if (previousUrl) URL.revokeObjectURL(previousUrl);
                                const url = URL.createObjectURL(blob);
                                image.dataset.objectUrl = url;
                                image.src = url;
                                image.style.display = 'block';
                                if (status) {{
                                    status.textContent = '';
                                    status.style.display = 'none';
                                }}
                            }} catch (error) {{
                                image.style.display = 'none';
                                if (status) {{
                                    status.textContent = error && error.message ? error.message : errorMessage;
                                    status.style.display = 'block';
                                }}
                            }}
                        }}));
                        """,
                        timeout=30,
                    )
                except Exception as error:
                    notify_error(error, error_message)

            await load_protein()
