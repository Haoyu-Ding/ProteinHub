from __future__ import annotations

import json

from nicegui import ui


STATUS_OPTIONS = [
    "draft",
    "designed",
    "ready_for_synthesis",
    "synthesizing",
    "testing",
    "validated",
    "failed",
]
PRIORITY_OPTIONS = ["low", "medium", "high"]
DISCIPLINE_OPTIONS = {
    "": "Unassigned",
    "design": "Design",
    "synthesis": "Synthesis",
    "assay": "Assay",
    "other": "Other",
}
MEMBER_DISCIPLINES = ["design", "synthesis", "assay", "other"]
ARTIFACT_TYPES = [
    "design_output",
    "structure_model",
    "synthesis_protocol",
    "experimental_result",
    "analysis_report",
    "other",
]
ARTIFACT_GROUPS = [
    ("design_output", "Design outputs"),
    ("structure_model", "Structure models"),
    ("synthesis_protocol", "Synthesis files"),
    ("experimental_result", "Experimental results"),
    ("analysis_report", "Analysis reports"),
    ("other", "Other files"),
    ("file", "Other files"),
]


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
            padding-bottom: 16px;
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
        .ph-icon-sequence { background: #fff6e5; color: var(--ph-amber); }
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

        .ph-board-row {
            width: 100%;
            display: grid;
            grid-template-columns: minmax(190px, 1.5fr) minmax(130px, 1fr) 132px 110px minmax(160px, 1fr) 112px;
            align-items: center;
            gap: 12px;
            padding: 14px 16px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-board-head {
            background: #f8fafc;
            color: var(--ph-muted);
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            box-shadow: none;
        }

        .ph-board-cell {
            min-width: 0;
        }

        .ph-status-strip {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            width: 100%;
        }

        .ph-stat {
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: #ffffff;
            padding: 14px;
        }

        .ph-stat-value {
            color: var(--ph-text);
            font-size: 24px;
            font-weight: 750;
            line-height: 1.1;
        }

        .ph-workflow-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 12px;
            width: 100%;
        }

        .ph-note-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 12px;
            width: 100%;
        }

        .ph-note-box {
            min-height: 116px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: #fbfcfd;
            padding: 14px;
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
        .ph-file-row,
        .ph-comment-row {
            width: 100%;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            padding: 14px 16px;
            border: 1px solid var(--ph-border);
            border-radius: 8px;
            background: var(--ph-surface);
        }

        .ph-comment-row {
            align-items: flex-start;
            justify-content: flex-start;
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
            .ph-board-row {
                grid-template-columns: 1fr;
            }

            .ph-board-head {
                display: none;
            }
        }
        </style>
        """
    )


def api_script() -> None:
    ui.add_head_html(
        """
        <script>
        window.phApi = async function(path, options = {}) {
            const token = localStorage.getItem('proteinhub_token');
            const headers = options.headers || {};
            if (token) headers.Authorization = `Bearer ${token}`;
            if (options.body && !(options.body instanceof FormData)) {
                headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(options.body);
            }
            const response = await fetch(path, {...options, headers});
            if (response.status === 204) return null;
            const contentType = response.headers.get('content-type') || '';
            const data = contentType.includes('application/json') ? await response.json() : await response.text();
            if (!response.ok) {
                const detail = data && data.detail ? data.detail : 'Request failed';
                throw new Error(detail);
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
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def humanize(value: str | None) -> str:
    if not value:
        return "Unassigned"
    return value.replace("_", " ").title()


def short_email(email: str | None) -> str:
    if not email:
        return "Unassigned"
    return email.split("@", 1)[0]


def status_color(status: str) -> str:
    return {
        "draft": "grey",
        "designed": "blue",
        "ready_for_synthesis": "orange",
        "synthesizing": "teal",
        "testing": "purple",
        "validated": "green",
        "failed": "red",
    }.get(status, "grey")


def priority_color(priority: str) -> str:
    return {"high": "red", "medium": "orange", "low": "grey"}.get(priority, "grey")


def empty_state(icon: str, title: str, detail: str) -> None:
    with ui.column().classes("ph-empty"):
        ui.icon(icon).classes("text-3xl text-slate-400")
        ui.label(title).classes("font-semibold text-slate-800")
        ui.label(detail).classes("ph-muted")


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
            ui.link("Projects", "/projects").classes("text-sm no-underline text-slate-700")
            ui.button("Logout", on_click=lambda: ui.run_javascript("phClearToken(); window.location.href='/login'")).props("flat dense")


async def ensure_logged_in() -> bool:
    token = await ui.run_javascript("phToken()", timeout=5)
    if not token:
        ui.navigate.to("/login")
        return False
    try:
        await ui.run_javascript("return await phApi('/api/me')")
        return True
    except Exception:
        ui.navigate.to("/login")
        return False


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
                        ui.label("Sequence-centered protein design workspace").classes("ph-muted")
                email = ui.input("Email").props("outlined").classes("w-full")
                password = ui.input("Password", password=True, password_toggle_button=True).props("outlined").classes("w-full")
                mode = ui.toggle(["Login", "Register"], value="Login").props("unelevated")

                async def submit() -> None:
                    endpoint = "/api/auth/login" if mode.value == "Login" else "/api/auth/register"
                    try:
                        result = await ui.run_javascript(
                            f"return await phApi('{endpoint}', {{method: 'POST', body: {{email: {email.value!r}, password: {password.value!r}}}}})",
                            timeout=10,
                        )
                        await ui.run_javascript(f"phSetToken({result['access_token']!r})")
                        ui.navigate.to("/projects")
                    except Exception as error:
                        ui.notify(str(error), type="negative")

                ui.button("Continue", on_click=submit).classes("w-full").props("unelevated")

    @ui.page("/projects")
    async def projects_page() -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("Workspace").classes("ph-eyebrow")
                    ui.label("Projects").classes("ph-title")
                    ui.label("Project-level permissions protect every protein, sequence, and artifact.").classes("ph-subtitle")
                ui.button("New Project", icon="add", on_click=lambda: project_dialog.open()).props("unelevated")

            project_grid = ui.grid(columns="repeat(auto-fill, minmax(280px, 1fr))").classes("ph-grid w-full")

            async def load_projects() -> None:
                project_grid.clear()
                try:
                    projects = await ui.run_javascript("return await phApi('/api/projects')", timeout=10)
                    with project_grid:
                        if not projects:
                            empty_state("folder_open", "No projects yet", "Create one to start collecting sequences.")
                        for project in projects:
                            with ui.card().classes("ph-resource-card gap-4 p-4"):
                                with ui.row().classes("w-full items-start gap-3"):
                                    with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                        ui.icon("folder_open")
                                    with ui.column().classes("min-w-0 flex-1 gap-1"):
                                        ui.label(project["name"]).classes("ph-card-title")
                                        ui.label(project["description"] or "No description").classes("ph-card-description")
                                with ui.row().classes("w-full items-center justify-between"):
                                    ui.badge(project["role"]).props("outline")
                                    ui.button("Open", icon="arrow_forward", on_click=lambda p=project: ui.navigate.to(f"/projects/{p['id']}")).props("flat")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            with ui.dialog() as project_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("New Project").classes("text-lg font-semibold")
                name = ui.input("Name").props("outlined").classes("w-full")
                description = ui.textarea("Description").props("outlined").classes("w-full")

                async def create() -> None:
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/projects', {{method: 'POST', body: {{name: {name.value!r}, description: {description.value!r}}}}})",
                            timeout=10,
                        )
                        project_dialog.close()
                        name.value = ""
                        description.value = ""
                        await load_projects()
                    except Exception as error:
                        ui.notify(str(error), type="negative")

                with ui.row().classes("justify-end w-full"):
                    ui.button("Cancel", on_click=project_dialog.close).props("flat")
                    ui.button("Create", icon="add", on_click=create)

            await load_projects()

    @ui.page("/projects/{project_id}")
    async def project_page(project_id: int) -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("Project").classes("ph-eyebrow")
                    title = ui.label("Project").classes("ph-title")
                    description = ui.label().classes("ph-subtitle")
                role_badge = ui.badge().props("outline")

            with ui.tabs().classes("w-full") as tabs:
                board_tab = ui.tab("Board")
                proteins_tab = ui.tab("Proteins")
                members_tab = ui.tab("Members")
            with ui.tab_panels(tabs, value=board_tab).classes("ph-panel w-full"):
                with ui.tab_panel(board_tab).classes("gap-4"):
                    with ui.row().classes("ph-section-bar w-full"):
                        with ui.column().classes("gap-0"):
                            ui.label("Collaboration board").classes("text-xl font-semibold")
                            ui.label("Track designs as they move from computation to synthesis and testing.").classes("ph-muted")
                        ui.button("Refresh", icon="refresh", on_click=lambda: load_board()).props("flat")
                    status_strip = ui.element("div").classes("ph-status-strip")
                    board_column = ui.column().classes("w-full gap-2")
                with ui.tab_panel(proteins_tab).classes("gap-4"):
                    with ui.row().classes("ph-section-bar w-full"):
                        with ui.column().classes("gap-0"):
                            ui.label("Proteins").classes("text-xl font-semibold")
                            ui.label("Protein records inside this project.").classes("ph-muted")
                        ui.button("New Protein", icon="add", on_click=lambda: protein_dialog.open()).props("unelevated")
                    proteins_column = ui.column().classes("w-full gap-3")
                with ui.tab_panel(members_tab).classes("gap-4"):
                    with ui.row().classes("ph-section-bar w-full"):
                        with ui.column().classes("gap-0"):
                            ui.label("Members").classes("text-xl font-semibold")
                            ui.label("Project access is managed here.").classes("ph-muted")
                        add_member_button = ui.button("Add Member", icon="person_add", on_click=lambda: member_dialog.open()).props("unelevated")
                    members_column = ui.column().classes("w-full gap-2")

            async def load_project() -> None:
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/projects/{project_id}')", timeout=10)
                    project = data["project"]
                    title.text = project["name"]
                    description.text = project["description"] or "No description"
                    role_badge.text = project["role"]
                    add_member_button.visible = project["role"] == "owner"
                    members_column.clear()
                    with members_column:
                        for member in data["members"]:
                            with ui.row().classes("ph-member-row"):
                                with ui.row().classes("items-center gap-3"):
                                    with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                        ui.icon("person")
                                    with ui.column().classes("gap-0"):
                                        ui.label(member["email"]).classes("font-medium")
                                        ui.label(humanize(member.get("discipline"))).classes("ph-meta")
                                with ui.row().classes("gap-2"):
                                    ui.badge(member["role"]).props("outline")
                                    ui.badge(humanize(member.get("discipline"))).props("outline color=secondary")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            async def load_board() -> None:
                board_column.clear()
                status_strip.clear()
                try:
                    rows = await ui.run_javascript(f"return await phApi('/api/projects/{project_id}/board')", timeout=10)
                    counts = {status: 0 for status in STATUS_OPTIONS}
                    for row in rows:
                        counts[row["status"]] = counts.get(row["status"], 0) + 1
                    with status_strip:
                        for status in ["ready_for_synthesis", "synthesizing", "testing", "validated"]:
                            with ui.element("div").classes("ph-stat"):
                                ui.label(str(counts.get(status, 0))).classes("ph-stat-value")
                                ui.label(humanize(status)).classes("ph-meta")
                    with board_column:
                        if not rows:
                            empty_state("view_kanban", "No candidate sequences", "Create sequences under a protein to start the handoff workflow.")
                        else:
                            with ui.element("div").classes("ph-board-row ph-board-head"):
                                ui.label("Sequence")
                                ui.label("Protein")
                                ui.label("Status")
                                ui.label("Priority")
                                ui.label("Owner")
                                ui.label("")
                            for row in rows:
                                with ui.element("div").classes("ph-board-row"):
                                    with ui.column().classes("ph-board-cell gap-1"):
                                        with ui.row().classes("items-center gap-2"):
                                            ui.label(row["name"]).classes("font-semibold text-slate-900")
                                            if row["version_tag"]:
                                                ui.badge(row["version_tag"]).props("outline")
                                        ui.label(f"{len(row['sequence'])} aa · {row['artifact_count']} files").classes("ph-meta")
                                    ui.label(row["protein_name"]).classes("ph-board-cell text-slate-700")
                                    ui.badge(humanize(row["status"])).props(f"outline color={status_color(row['status'])}")
                                    ui.badge(humanize(row["priority"])).props(f"outline color={priority_color(row['priority'])}")
                                    with ui.column().classes("ph-board-cell gap-0"):
                                        ui.label(short_email(row.get("assigned_to_email"))).classes("text-sm text-slate-800")
                                        ui.label(humanize(row.get("discipline_owner"))).classes("ph-meta")
                                    ui.button("Open", icon="open_in_new", on_click=lambda s=row: ui.navigate.to(f"/sequences/{s['id']}")).props("flat")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            async def load_proteins() -> None:
                proteins_column.clear()
                try:
                    proteins = await ui.run_javascript(f"return await phApi('/api/projects/{project_id}/proteins')", timeout=10)
                    with proteins_column:
                        if not proteins:
                            empty_state("science", "No proteins yet", "Create one, then add sequences.")
                        for protein in proteins:
                            with ui.card().classes("ph-resource-card w-full p-4"):
                                with ui.row().classes("w-full items-center justify-between gap-4"):
                                    with ui.row().classes("min-w-0 flex-1 items-start gap-3"):
                                        with ui.element("div").classes("ph-icon-box ph-icon-protein"):
                                            ui.icon("science")
                                        with ui.column().classes("min-w-0 gap-1"):
                                            ui.label(protein["name"]).classes("ph-card-title")
                                            ui.label(protein["description"] or "No description").classes("ph-card-description")
                                    ui.button("Sequences", icon="list", on_click=lambda p=protein: ui.navigate.to(f"/proteins/{p['id']}")).props("flat")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            with ui.dialog() as protein_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("New Protein").classes("text-lg font-semibold")
                protein_name = ui.input("Name").props("outlined").classes("w-full")
                protein_description = ui.textarea("Description").props("outlined").classes("w-full")

                async def create_protein() -> None:
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/proteins', {{method: 'POST', body: {{name: {protein_name.value!r}, description: {protein_description.value!r}}}}})",
                            timeout=10,
                        )
                        protein_dialog.close()
                        protein_name.value = ""
                        protein_description.value = ""
                        await load_proteins()
                    except Exception as error:
                        ui.notify(str(error), type="negative")

                with ui.row().classes("justify-end w-full"):
                    ui.button("Cancel", on_click=protein_dialog.close).props("flat")
                    ui.button("Create", icon="add", on_click=create_protein)

            with ui.dialog() as member_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("Add Member").classes("text-lg font-semibold")
                member_email = ui.input("Email").props("outlined").classes("w-full")
                member_role = ui.toggle(["member", "owner"], value="member")
                member_discipline = ui.select(MEMBER_DISCIPLINES, value="other", label="Discipline").props("outlined").classes("w-full")

                async def add_member() -> None:
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/members', {{method: 'POST', body: {{email: {member_email.value!r}, role: {member_role.value!r}, discipline: {member_discipline.value!r}}}}})",
                            timeout=10,
                        )
                        member_dialog.close()
                        member_email.value = ""
                        member_discipline.value = "other"
                        await load_project()
                    except Exception as error:
                        ui.notify(str(error), type="negative")

                with ui.row().classes("justify-end w-full"):
                    ui.button("Cancel", on_click=member_dialog.close).props("flat")
                    ui.button("Add", icon="person_add", on_click=add_member)

            await load_project()
            await load_board()
            await load_proteins()

    @ui.page("/proteins/{protein_id}")
    async def protein_page(protein_id: int) -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("Protein").classes("ph-eyebrow")
                    ui.label("Sequences").classes("ph-title")
                    ui.label("Sequences are the center of ProteinHub; artifacts attach here.").classes("ph-subtitle")
                ui.button("New Sequence", icon="add", on_click=lambda: sequence_dialog.open()).props("unelevated")
            sequences_column = ui.column().classes("w-full gap-3")

            async def load_sequences() -> None:
                sequences_column.clear()
                try:
                    sequences = await ui.run_javascript(f"return await phApi('/api/proteins/{protein_id}/sequences')", timeout=10)
                    with sequences_column:
                        if not sequences:
                            empty_state("science", "No sequences yet", "Create a sequence before attaching artifacts.")
                        for sequence in sequences:
                            preview = sequence_display(sequence["sequence"][:120])
                            with ui.card().classes("ph-resource-card w-full p-4"):
                                with ui.row().classes("w-full items-start justify-between gap-4"):
                                    with ui.row().classes("min-w-0 flex-1 items-start gap-3"):
                                        with ui.element("div").classes("ph-icon-box ph-icon-sequence"):
                                            ui.icon("science")
                                        with ui.column().classes("min-w-0 gap-2"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.label(sequence["name"]).classes("ph-card-title")
                                                if sequence["version_tag"]:
                                                    ui.badge(sequence["version_tag"]).props("outline")
                                                ui.badge(humanize(sequence["status"])).props(f"outline color={status_color(sequence['status'])}")
                                                ui.badge(humanize(sequence["priority"])).props(f"outline color={priority_color(sequence['priority'])}")
                                            ui.label(f"{len(sequence['sequence'])} aa").classes("ph-meta")
                                            ui.label(f"{humanize(sequence.get('discipline_owner'))} · {short_email(sequence.get('assigned_to_email'))}").classes("ph-meta")
                                            ui.label(preview + (" ..." if len(sequence["sequence"]) > 120 else "")).classes("ph-sequence-preview font-mono text-sm text-slate-700")
                                    ui.button("Open", icon="science", on_click=lambda s=sequence: ui.navigate.to(f"/sequences/{s['id']}")).props("flat")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            with ui.dialog() as sequence_dialog, ui.card().classes("ph-dialog-card w-full max-w-2xl gap-4"):
                ui.label("New Sequence").classes("text-lg font-semibold")
                sequence_name = ui.input("Name").props("outlined").classes("w-full")
                version_tag = ui.input("Version / tag").props("outlined").classes("w-full")
                sequence_text = ui.textarea("Sequence").props("outlined").classes("w-full")
                sequence_description = ui.textarea("Description").props("outlined").classes("w-full")

                async def create_sequence() -> None:
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/proteins/{protein_id}/sequences', {{method: 'POST', body: {{name: {sequence_name.value!r}, sequence: {sequence_text.value!r}, description: {sequence_description.value!r}, version_tag: {version_tag.value!r}}}}})",
                            timeout=10,
                        )
                        sequence_dialog.close()
                        sequence_name.value = ""
                        version_tag.value = ""
                        sequence_text.value = ""
                        sequence_description.value = ""
                        await load_sequences()
                    except Exception as error:
                        ui.notify(str(error), type="negative")

                with ui.row().classes("justify-end w-full"):
                    ui.button("Cancel", on_click=sequence_dialog.close).props("flat")
                    ui.button("Create", icon="add", on_click=create_sequence)

            await load_sequences()

    @ui.page("/sequences/{sequence_id}")
    async def sequence_page(sequence_id: int) -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("Sequence").classes("ph-eyebrow")
                    sequence_title = ui.label("Sequence").classes("ph-title")
                    sequence_description = ui.label().classes("ph-subtitle")
                sequence_meta = ui.row().classes("gap-2")

            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label("Workflow handoff").classes("text-xl font-semibold")
                        ui.label("State, responsibility, and notes for the next collaborating group.").classes("ph-muted")
                    ui.button("Save workflow", icon="save", on_click=lambda: save_workflow()).props("unelevated")
                with ui.element("div").classes("ph-workflow-grid"):
                    status_select = ui.select(STATUS_OPTIONS, label="Status").props("outlined").classes("w-full")
                    priority_select = ui.select(PRIORITY_OPTIONS, label="Priority").props("outlined").classes("w-full")
                    discipline_select = ui.select(DISCIPLINE_OPTIONS, label="Responsible discipline").props("outlined").classes("w-full")
                    assigned_select = ui.select({0: "Unassigned"}, label="Assigned to").props("outlined").classes("w-full")
                with ui.element("div").classes("ph-note-grid"):
                    design_rationale = ui.textarea("Design rationale").props("outlined autogrow").classes("w-full")
                    handoff_note = ui.textarea("Handoff note").props("outlined autogrow").classes("w-full")
                    risk_note = ui.textarea("Risk note").props("outlined autogrow").classes("w-full")
            with ui.column().classes("ph-sequence-panel"):
                with ui.row().classes("w-full items-center justify-between border-b border-slate-200 px-4 py-3"):
                    ui.label("Amino acid sequence").classes("font-semibold text-slate-800")
                    sequence_length_badge = ui.badge().props("outline")
                sequence_text = ui.label().classes("ph-sequence-text")

            notes_column = ui.element("div").classes("ph-note-grid")
            with ui.row().classes("ph-section-bar w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("Artifacts").classes("text-xl font-semibold")
                    ui.label("Files grouped by design, synthesis, and experiment handoff stage.").classes("ph-muted")
                with ui.row().classes("gap-2"):
                    artifact_type_select = ui.select(ARTIFACT_TYPES, value="design_output", label="Type").props("outlined dense").classes("min-w-56")
                    artifact_type_select.props("id=artifact-type-select")
                    upload_button = ui.button("Upload", icon="upload").props("unelevated")
            artifacts_column = ui.column().classes("w-full gap-3")
            with ui.row().classes("ph-section-bar w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("Activity").classes("text-xl font-semibold")
                    ui.label("Short notes for handoff decisions and experiment feedback.").classes("ph-muted")
            comments_column = ui.column().classes("w-full gap-2")
            with ui.row().classes("w-full items-start gap-2"):
                comment_body = ui.textarea("Add comment").props("outlined autogrow").classes("flex-1")
                ui.button("Comment", icon="send", on_click=lambda: add_comment()).props("unelevated")

            async def load_sequence() -> None:
                artifacts_column.clear()
                comments_column.clear()
                notes_column.clear()
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/sequences/{sequence_id}')", timeout=10)
                    sequence = data["sequence"]
                    sequence_title.text = sequence["name"]
                    sequence_text.text = sequence_display(sequence["sequence"])
                    sequence_description.text = sequence["description"] or "No description"
                    sequence_length_badge.text = f"{len(sequence['sequence'])} aa"
                    sequence_meta.clear()
                    with sequence_meta:
                        if sequence["version_tag"]:
                            ui.badge(sequence["version_tag"]).props("outline")
                        ui.badge(humanize(sequence["status"])).props(f"outline color={status_color(sequence['status'])}")
                        ui.badge(humanize(sequence["priority"])).props(f"outline color={priority_color(sequence['priority'])}")
                        if sequence.get("protein_name"):
                            ui.badge(sequence["protein_name"]).props("outline color=secondary")
                    status_select.value = sequence["status"]
                    priority_select.value = sequence["priority"]
                    discipline_select.value = sequence.get("discipline_owner") or ""
                    assignee_options = {0: "Unassigned"}
                    for member in data.get("project_members", []):
                        assignee_options[member["id"]] = member["email"]
                    assigned_select.options = assignee_options
                    assigned_select.value = sequence.get("assigned_to") or 0
                    design_rationale.value = sequence.get("design_rationale") or ""
                    handoff_note.value = sequence.get("handoff_note") or ""
                    risk_note.value = sequence.get("risk_note") or ""
                    with notes_column:
                        for title_text, body_text in [
                            ("Design rationale", sequence.get("design_rationale") or "No design rationale yet."),
                            ("Handoff note", sequence.get("handoff_note") or "No handoff note yet."),
                            ("Risk note", sequence.get("risk_note") or "No risk note yet."),
                        ]:
                            with ui.column().classes("ph-note-box gap-2"):
                                ui.label(title_text).classes("font-semibold text-slate-800")
                                ui.label(body_text).classes("ph-card-description")
                    with artifacts_column:
                        if not data["artifacts"]:
                            empty_state("upload_file", "No artifacts uploaded yet", "Upload files or generated outputs for this sequence.")
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
                                    with ui.row().classes("ph-file-row"):
                                        with ui.row().classes("min-w-0 flex-1 items-center gap-3"):
                                            with ui.element("div").classes("ph-icon-box ph-icon-artifact"):
                                                ui.icon("description")
                                            with ui.column().classes("min-w-0 gap-1"):
                                                ui.label(artifact["filename"]).classes("font-semibold text-slate-900")
                                                ui.label(f"{humanize(artifact['artifact_type'])} · {artifact['mime_type']} · {format_bytes(artifact['size_bytes'])}").classes("ph-meta")
                                        with ui.row().classes("gap-2"):
                                            ui.button("Download", icon="download", on_click=lambda a=artifact: download_artifact(a["id"], a["filename"])).props("flat")
                                            ui.button("Delete", icon="delete", on_click=lambda a=artifact: delete_artifact(a["id"])).props("flat color=negative")
                    with comments_column:
                        if not data.get("comments"):
                            empty_state("chat_bubble", "No activity yet", "Add a short note when ownership or decisions change.")
                        for comment in data.get("comments", []):
                            with ui.row().classes("ph-comment-row"):
                                with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                    ui.icon("chat_bubble")
                                with ui.column().classes("min-w-0 gap-1"):
                                    ui.label(f"{comment['author_email']} · {comment['created_at']}").classes("ph-meta")
                                    ui.label(comment["body"]).classes("text-sm text-slate-800")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            async def save_workflow() -> None:
                assigned_value = None if assigned_select.value in (None, 0, "0") else assigned_select.value
                payload = {
                    "status": status_select.value,
                    "priority": priority_select.value,
                    "assigned_to": assigned_value,
                    "discipline_owner": discipline_select.value or "",
                    "design_rationale": design_rationale.value or "",
                    "handoff_note": handoff_note.value or "",
                    "risk_note": risk_note.value or "",
                }
                try:
                    await ui.run_javascript(
                        f"return await phApi('/api/sequences/{sequence_id}/workflow', {{method: 'PATCH', body: {json.dumps(payload)}}})",
                        timeout=10,
                    )
                    ui.notify("Workflow saved", type="positive")
                    await load_sequence()
                except Exception as error:
                    ui.notify(str(error), type="negative")

            async def add_comment() -> None:
                try:
                    await ui.run_javascript(
                        f"return await phApi('/api/sequences/{sequence_id}/comments', {{method: 'POST', body: {{body: {comment_body.value!r}}}}})",
                        timeout=10,
                    )
                    comment_body.value = ""
                    await load_sequence()
                except Exception as error:
                    ui.notify(str(error), type="negative")

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
                            throw new Error(text || 'Download failed');
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
                    ui.notify(str(error), type="negative")

            async def delete_artifact(artifact_id: int) -> None:
                try:
                    await ui.run_javascript(f"return await phApi('/api/artifacts/{artifact_id}', {{method: 'DELETE'}})", timeout=10)
                    await load_sequence()
                except Exception as error:
                    ui.notify(str(error), type="negative")

            upload_button.on(
                "click",
                js_handler=f"""
                () => {{
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.style.display = 'none';
                    input.addEventListener('change', async () => {{
                        if (!input.files || input.files.length === 0) {{
                            input.remove();
                            return;
                        }}
                        const form = new FormData();
                        form.append('file', input.files[0]);
                        try {{
                            const artifactType = document.querySelector('#artifact-type-select input')?.value || 'other';
                            await phApi('/api/sequences/{sequence_id}/artifacts?artifact_type=' + encodeURIComponent(artifactType), {{
                                method: 'POST',
                                body: form,
                            }});
                            window.location.reload();
                        }} catch (error) {{
                            alert(error.message || 'Upload failed');
                        }} finally {{
                            input.remove();
                        }}
                    }}, {{once: true}});
                    document.body.appendChild(input);
                    input.click();
                }}
                """,
            )
            await load_sequence()
