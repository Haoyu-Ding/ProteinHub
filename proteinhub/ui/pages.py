from __future__ import annotations

import json

from nicegui import ui

from proteinhub.ui.support import (
    ARTIFACT_GROUPS,
    ARTIFACT_TYPE_OPTIONS,
    MEMBER_DISCIPLINE_OPTIONS,
    ROLE_LABELS,
    api_script,
    design_system,
    empty_state,
    ensure_logged_in,
    format_bytes,
    humanize,
    notify_error,
    person_label,
    sequence_display,
    shell,
)


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
                name = ui.input("姓名").props("outlined").classes("w-full")
                email = ui.input("邮箱").props("outlined").classes("w-full")
                password = ui.input("密码", password=True, password_toggle_button=True).props("outlined").classes("w-full")
                mode = ui.toggle(["登录", "注册"], value="登录").props("unelevated")
                name.bind_visibility_from(mode, "value", lambda value: value == "注册")

                async def submit() -> None:
                    endpoint = "/api/auth/login" if mode.value == "登录" else "/api/auth/register"
                    body = {"email": email.value, "password": password.value}
                    if mode.value == "注册":
                        body["name"] = name.value
                    try:
                        result = await ui.run_javascript(
                            f"return await phApi('{endpoint}', {{method: 'POST', body: {json.dumps(body)}}})",
                            timeout=10,
                        )
                        await ui.run_javascript(f"phSetToken({result['access_token']!r})")
                        ui.navigate.to("/projects")
                    except Exception as error:
                        notify_error(error)

                ui.button("继续", on_click=submit).classes("w-full").props("unelevated")

    @ui.page("/projects")
    async def projects_page() -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("ph-page"):
            with ui.row().classes("ph-page-header w-full"):
                with ui.column().classes("gap-1"):
                    ui.label("工作台").classes("ph-eyebrow")
                    ui.label("项目").classes("ph-title")
                    ui.label("项目权限会保护每个蛋白记录和实验资料。").classes("ph-subtitle")
                ui.button("新建项目", icon="add", on_click=lambda: project_dialog.open()).props("unelevated")

            project_grid = ui.grid(columns="repeat(auto-fill, minmax(280px, 1fr))").classes("ph-grid w-full")

            async def load_projects() -> None:
                project_grid.clear()
                try:
                    projects = await ui.run_javascript("return await phApi('/api/projects')", timeout=10)
                    with project_grid:
                        if not projects:
                            empty_state("folder_open", "还没有项目", "新建一个项目后，就可以开始收集蛋白。")
                        for project in projects:
                            with ui.card().classes("ph-resource-card gap-4 p-4"):
                                with ui.row().classes("w-full items-start gap-3"):
                                    with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                        ui.icon("folder_open")
                                    with ui.column().classes("min-w-0 flex-1 gap-1"):
                                        ui.label(project["name"]).classes("ph-card-title")
                                        ui.label(project["description"] or "暂无描述").classes("ph-card-description")
                                with ui.row().classes("w-full items-center justify-between"):
                                    ui.badge(humanize(project["role"])).props("outline")
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
                        await load_projects()
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=project_dialog.close).props("flat")
                    ui.button("创建", icon="add", on_click=create)

            await load_projects()

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
                role_badge = ui.badge().props("outline")

            with ui.row().classes("ph-workspace-layout w-full"):
                with ui.column().classes("ph-project-sidebar"):
                    with ui.column().classes("gap-1"):
                        ui.label("项目视图").classes("ph-eyebrow")
                        ui.label("浏览项目内容").classes("font-semibold text-slate-900")
                    with ui.tabs().props("vertical").classes("ph-side-tabs w-full") as tabs:
                        proteins_tab = ui.tab("蛋白信息", icon="science")
                        batches_tab = ui.tab("实验批次", icon="grid_view")
                        members_tab = ui.tab("成员", icon="group")
                with ui.tab_panels(tabs, value=proteins_tab).classes("ph-panel ph-workspace-panel"):
                    with ui.tab_panel(proteins_tab).classes("ph-proteins-panel"):
                        with ui.row().classes("ph-section-bar w-full"):
                            with ui.column().classes("gap-0"):
                                ui.label("蛋白信息").classes("text-xl font-semibold")
                                ui.label("查询和管理这个项目中的蛋白记录与实验资料。").classes("ph-muted")
                            ui.button("新建蛋白", icon="add", on_click=lambda: protein_dialog.open()).props("unelevated")
                        with ui.element("div").classes("ph-proteins-scroll w-full"):
                            proteins_column = ui.column().classes("w-full gap-3")
                    with ui.tab_panel(batches_tab).classes("ph-batches-panel"):
                        with ui.row().classes("ph-section-bar w-full"):
                            with ui.column().classes("gap-0"):
                                ui.label("实验批次").classes("text-xl font-semibold")
                                ui.label("把项目中的蛋白排入 96 孔板，记录每个孔的实验结果。").classes("ph-muted")
                            ui.button("新建批次", icon="add", on_click=lambda: batch_dialog.open()).props("unelevated")
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
            selected_batch_proteins: set[int] = set()

            async def load_project() -> None:
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/projects/{project_id}')", timeout=10)
                    project = data["project"]
                    title.text = project["name"]
                    description.text = project["description"] or "暂无描述"
                    role_badge.text = humanize(project["role"])
                    add_member_button.visible = project["role"] == "owner"
                    members_column.clear()
                    can_manage_members = project["role"] == "owner"
                    with members_column:
                        for member in data["members"]:
                            with ui.row().classes("ph-member-row"):
                                with ui.row().classes("items-center gap-3"):
                                    with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                        ui.icon("person")
                                    with ui.column().classes("gap-0"):
                                        ui.label(person_label(member.get("name"), member.get("email"))).classes("font-medium")
                                        ui.label(f"{member['email']} · {humanize(member.get('discipline'))}").classes("ph-meta")
                                if can_manage_members:
                                    with ui.row().classes("items-center gap-2"):
                                        role_select = (
                                            ui.select(
                                                ROLE_LABELS,
                                                value=member["role"],
                                                label="角色",
                                            )
                                            .props("outlined dense")
                                            .classes("min-w-32")
                                        )
                                        discipline_select = (
                                            ui.select(
                                                MEMBER_DISCIPLINE_OPTIONS,
                                                value=member.get("discipline") or "other",
                                                label="学科方向",
                                            )
                                            .props("outlined dense")
                                            .classes("min-w-36")
                                        )
                                        ui.button(
                                            "保存",
                                            icon="save",
                                            on_click=lambda m=member, r=role_select, d=discipline_select: update_member(
                                                m["id"], r.value, d.value
                                            ),
                                        ).props("flat dense no-wrap")
                                else:
                                    with ui.row().classes("gap-2"):
                                        ui.badge(humanize(member["role"])).props("outline")
                                        ui.badge(humanize(member.get("discipline"))).props("outline color=secondary")
                except Exception as error:
                    notify_error(error)

            async def update_member(member_id: int, role: str, discipline: str) -> None:
                try:
                    payload = {"role": role, "discipline": discipline}
                    await ui.run_javascript(
                        f"return await phApi('/api/projects/{project_id}/members/{member_id}', "
                        f"{{method: 'PATCH', body: {json.dumps(payload)}}})",
                        timeout=10,
                    )
                    ui.notify("成员设置已更新", type="positive")
                    await load_project()
                except Exception as error:
                    notify_error(error)

            async def load_proteins() -> None:
                proteins_column.clear()
                try:
                    proteins = await ui.run_javascript(f"return await phApi('/api/projects/{project_id}/proteins')", timeout=10)
                    project_proteins["items"] = proteins
                    with proteins_column:
                        if not proteins:
                            empty_state("science", "还没有蛋白", "先创建蛋白并填写序列。")
                        for protein in proteins:
                            preview = protein["sequence"][:50] + (
                                "..." if len(protein["sequence"]) > 50 else ""
                            )
                            with ui.card().classes("ph-resource-card ph-protein-card w-full p-4"):
                                with ui.row().classes("w-full items-center justify-between gap-4"):
                                    with ui.row().classes("min-w-0 flex-1 items-start gap-3"):
                                        with ui.element("div").classes("ph-icon-box ph-icon-protein"):
                                            ui.icon("science")
                                        with ui.column().classes("min-w-0 gap-2"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.label(protein["name"]).classes("ph-card-title")
                                                if protein["version_tag"]:
                                                    ui.badge(protein["version_tag"]).props("outline")
                                            ui.label(protein["description"] or "暂无描述").classes("ph-card-description")
                                            ui.label(f"{len(protein['sequence'])} 个氨基酸 · {protein['artifact_count']} 份资料").classes("ph-meta")
                                            ui.label(preview).classes("ph-protein-sequence-preview font-mono text-sm text-slate-700")
                                    ui.button("打开", icon="open_in_new", on_click=lambda p=protein: ui.navigate.to(f"/proteins/{p['id']}")).props("flat")
                    render_batch_protein_options()
                except Exception as error:
                    notify_error(error)

            async def load_batches() -> None:
                batches_column.clear()
                try:
                    batches = await ui.run_javascript(f"return await phApi('/api/projects/{project_id}/batches')", timeout=10)
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
                                            ui.label(batch["description"] or "暂无描述").classes("ph-card-description")
                                            ui.label(
                                                f"{batch['well_count']} 个孔 · {batch['experiment_count']} 个实验 · {batch['result_count']} 个结果"
                                            ).classes("ph-meta")
                                    ui.button(
                                        "打开",
                                        icon="open_in_new",
                                        on_click=lambda b=batch: ui.navigate.to(f"/batches/{b['id']}"),
                                    ).props("flat")
                except Exception as error:
                    notify_error(error)

            with ui.dialog() as protein_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("新建蛋白").classes("text-lg font-semibold")
                protein_name = ui.input("名称").props("outlined").classes("w-full ph-protein-name-input")
                protein_version_tag = ui.input("版本 / 标签").props("outlined").classes("w-full ph-protein-version-tag-input")
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
                                updateInput(sequenceInput, data.sequence);
                                if (nameInput && !nameInput.value.trim()) {{
                                    const fallbackName = (data.filename || 'protein').replace(/\\.[^.]+$/, '') || 'protein';
                                    updateInput(nameInput, fallbackName);
                                }}
                                if (status) status.textContent = `已读取 ${{data.length}} 个氨基酸 · ${{data.source}}`;
                                phNotify('序列已读取', 'positive');
                            }} catch (error) {{
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
                            """
                            const fieldValue = (selector) => {
                                const element = document.querySelector(selector);
                                return element ? element.value : '';
                            };
                            return {
                                name: fieldValue('.ph-protein-name-input input'),
                                sequence: fieldValue('.ph-protein-sequence-input textarea'),
                                description: fieldValue('.ph-protein-description-input textarea'),
                                version_tag: fieldValue('.ph-protein-version-tag-input input'),
                            };
                            """,
                            timeout=5,
                        )
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/proteins', {{method: 'POST', body: {json.dumps(payload)}}})",
                            timeout=10,
                        )
                        protein_dialog.close()
                        protein_name.value = ""
                        protein_version_tag.value = ""
                        protein_sequence.value = ""
                        protein_import_status.text = ""
                        protein_description.value = ""
                        await load_proteins()
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=protein_dialog.close).props("flat")
                    ui.button("创建", icon="add", on_click=create_protein)

            with ui.dialog() as batch_dialog, ui.card().classes("ph-dialog-card w-full max-w-2xl gap-4"):
                ui.label("新建实验批次").classes("text-lg font-semibold")
                batch_name = ui.input("名称").props("outlined").classes("w-full")
                batch_description = ui.textarea("描述").props("outlined autogrow").classes("w-full")
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("选择蛋白").classes("font-semibold text-slate-800")
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
                                if protein["version_tag"]:
                                    ui.badge(protein["version_tag"]).props("outline")
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
                        }
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/batches', "
                            f"{{method: 'POST', body: {json.dumps(payload)}}})",
                            timeout=10,
                        )
                        batch_dialog.close()
                        batch_name.value = ""
                        batch_description.value = ""
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
                with ui.row().classes("w-full items-center gap-3"):
                    member_role = ui.toggle(["成员", "负责人"], value="成员").props("unelevated")
                    member_discipline = ui.select(MEMBER_DISCIPLINE_OPTIONS, value="other", label="学科方向").props("outlined").classes("flex-1")

                async def search_members() -> None:
                    query = (member_query.value or "").strip()
                    selected_member["email"] = None
                    selected_member_label.text = "未选择"
                    member_results.clear()
                    if len(query) < 2:
                        with member_results:
                            ui.label("请输入至少两个字符。").classes("ph-muted")
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
                    role_value = "owner" if member_role.value == "负责人" else "member"
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/members', {{method: 'POST', body: {{email: {selected_member['email']!r}, role: {role_value!r}, discipline: {member_discipline.value!r}}}}})",
                            timeout=10,
                        )
                        member_dialog.close()
                        member_query.value = ""
                        selected_member["email"] = None
                        selected_member_label.text = "未选择"
                        member_results.clear()
                        with member_results:
                            ui.label("输入姓名并搜索后，候选成员会显示在这里。").classes("ph-muted")
                        member_role.value = "成员"
                        member_discipline.value = "other"
                        await load_project()
                    except Exception as error:
                        notify_error(error)

                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=member_dialog.close).props("flat")
                    ui.button("添加", icon="person_add", on_click=add_member)

            await load_project()
            await load_proteins()
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
                    batch_meta = ui.row().classes("gap-2")

            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        mapping_title = ui.label("批次 Mapping").classes("text-xl font-semibold")
                        mapping_summary = ui.label().classes("ph-muted")
                mapping_table = ui.element("div").classes("ph-batch-mapping ph-batch-mapping-scroll")

            with ui.column().classes("ph-panel w-full gap-4 p-4"):
                with ui.row().classes("ph-section-bar w-full"):
                    with ui.column().classes("gap-0"):
                        ui.label("实验结果").classes("text-xl font-semibold")
                        ui.label("选择实验类型后上传结果文件。").classes("ph-muted")
                with ui.element("div").classes("ph-batch-upload-actions w-full"):
                    experiment_type = ui.select(
                        {"FPLC": "FPLC", "SPR": "SPR", "HPLC": "HPLC"},
                        value="FPLC",
                        label="实验类型",
                    ).props("outlined dense").classes("w-full")
                    upload_status = ui.label("等待上传").classes("ph-muted")

                    def update_upload_status() -> None:
                        upload_status.text = f"{experiment_type.value} 结果文件"

                    experiment_type.on_value_change(lambda _: update_upload_status())
                    ui.button(
                        "上传结果",
                        icon="upload_file",
                        on_click=lambda: ui.notify("实验结果上传流程待接入", type="info"),
                    ).props("unelevated no-wrap")

            async def load_batch() -> None:
                mapping_table.clear()
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/batches/{batch_id}')", timeout=10)
                    batch = data["batch"]
                    wells = data["wells"]
                    experiments = data["experiments"]
                    batch_title.text = batch["name"]
                    batch_description.text = batch["description"] or "暂无描述"
                    batch_meta.clear()
                    with batch_meta:
                        ui.badge(f"{batch['plate_format']} 孔").props("outline")
                        ui.badge(f"{len(wells)} 个蛋白").props("outline color=secondary")
                        ui.badge(f"{len(experiments)} 个实验").props("outline color=secondary")
                    mapping_summary.text = (
                        f"{batch['plate_format']} 孔 · {len(wells)} 条蛋白映射 · {len(experiments)} 个实验记录"
                    )
                    update_upload_status()
                    with mapping_table:
                        with ui.element("div").classes("ph-mapping-row ph-mapping-head"):
                            ui.label("孔位").classes("ph-mapping-cell")
                            ui.label("蛋白").classes("ph-mapping-cell")
                            ui.label("标签").classes("ph-mapping-cell")
                            ui.label("AA 序列").classes("ph-mapping-cell")
                            ui.label("长度").classes("ph-mapping-cell")
                        if not wells:
                            with ui.element("div").classes("ph-mapping-row"):
                                ui.label("暂无").classes("ph-mapping-cell ph-mapping-position")
                                ui.label("暂无蛋白映射").classes("ph-mapping-cell")
                                ui.label("").classes("ph-mapping-cell")
                                ui.label("").classes("ph-mapping-cell")
                                ui.label("").classes("ph-mapping-cell")
                        for well in wells:
                            sequence = well.get("protein_sequence") or ""
                            sequence_preview = sequence[:50] + ("..." if len(sequence) > 50 else "")
                            with ui.element("div").classes("ph-mapping-row"):
                                ui.label(well["position"]).classes("ph-mapping-cell ph-mapping-position")
                                ui.label(well["protein_name"]).classes("ph-mapping-cell")
                                ui.label(well.get("protein_version_tag") or "无").classes("ph-mapping-cell")
                                ui.label(sequence_preview).classes("ph-mapping-cell ph-mapping-sequence")
                                ui.label(f"{len(sequence)} aa").classes("ph-mapping-cell")
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
            with ui.column().classes("ph-sequence-panel"):
                with ui.row().classes("w-full items-center justify-between border-b border-slate-200 px-4 py-3"):
                    ui.label("DNA 序列").classes("font-semibold text-slate-800")
                    dna_sequence_length_badge = ui.badge().props("outline")
                dna_sequence_text = ui.label().classes("ph-sequence-text")

            with ui.row().classes("ph-section-bar w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("批次结果").classes("text-xl font-semibold")
                    ui.label("这个蛋白在实验批次中的孔位和回填结果。").classes("ph-muted")
            batch_results_column = ui.column().classes("w-full gap-3")

            with ui.row().classes("ph-section-bar w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("实验资料").classes("text-xl font-semibold")
                    ui.label("上传这个蛋白相关的结构模型、实验结果和分析报告。").classes("ph-muted")
                with ui.row().classes("gap-2"):
                    artifact_type_select = ui.select(ARTIFACT_TYPE_OPTIONS, value="design_output", label="类型").props("outlined dense").classes("min-w-56")
                    artifact_type_select.props("id=protein-artifact-type-select")
                    upload_button = ui.button("上传", icon="upload").props("unelevated")
            artifacts_column = ui.column().classes("w-full gap-3")

            async def load_protein() -> None:
                artifacts_column.clear()
                batch_results_column.clear()
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/proteins/{protein_id}')", timeout=10)
                    protein = data["protein"]
                    protein_title.text = protein["name"]
                    sequence_text.text = sequence_display(protein["sequence"])
                    protein_description.text = protein["description"] or "暂无描述"
                    sequence_length_badge.text = f"{len(protein['sequence'])} 个氨基酸"
                    dna_sequence = protein.get("dna_sequence") or ""
                    dna_sequence_text.text = sequence_display(dna_sequence) if dna_sequence else "暂未生成"
                    dna_sequence_length_badge.text = f"{len(dna_sequence)} 个核苷酸"
                    protein_meta.clear()
                    with protein_meta:
                        if protein["version_tag"]:
                            ui.badge(protein["version_tag"]).props("outline")
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
                                        if result.get("result_note"):
                                            ui.label(result["result_note"]).classes("ph-card-description")
                                ui.button(
                                    "打开批次",
                                    icon="open_in_new",
                                    on_click=lambda r=result: ui.navigate.to(f"/batches/{r['batch_id']}"),
                                ).props("flat")
                    with artifacts_column:
                        if not data["artifacts"]:
                            empty_state("upload_file", "还没有上传资料", "上传这个蛋白相关的文件或生成结果。")
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
                                                ui.label(f"{humanize(artifact['artifact_type'])} · {format_bytes(artifact['size_bytes'])}").classes("ph-meta")
                                        with ui.row().classes("gap-2"):
                                            ui.button("下载", icon="download", on_click=lambda a=artifact: download_artifact(a["id"], a["filename"])).props("flat")
                                            ui.button("删除", icon="delete", on_click=lambda a=artifact: delete_artifact(a["id"])).props("flat color=negative")
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

            upload_button.on(
                "click",
                js_handler=f"""
                () => {{
                    const artifactTypeLabels = {json.dumps({label: key for key, label in ARTIFACT_TYPE_OPTIONS.items()}, ensure_ascii=False)};
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
                            const selectedType = document.querySelector('#protein-artifact-type-select input')?.value || '其他文件';
                            const artifactType = artifactTypeLabels[selectedType] || selectedType || 'other';
                            await phApi('/api/proteins/{protein_id}/artifacts?artifact_type=' + encodeURIComponent(artifactType), {{
                                method: 'POST',
                                body: form,
                            }});
                            window.location.reload();
                        }} catch (error) {{
                            phNotifyError(error, '上传失败');
                        }} finally {{
                            input.remove();
                        }}
                    }}, {{once: true}});
                    document.body.appendChild(input);
                    input.click();
                }}
                """,
            )
            await load_protein()
