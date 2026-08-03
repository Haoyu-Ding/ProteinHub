from __future__ import annotations

import json
from datetime import date

from nicegui import ui

from proteinhub.ui.support import (
    ARTIFACT_GROUPS,
    ARTIFACT_TYPE_OPTIONS,
    BATCH_ORDER_STATUS_OPTIONS,
    MEMBER_DISCIPLINE_OPTIONS,
    PLATE_96_POSITION_OPTIONS,
    PROTEIN_TYPE_OPTIONS,
    ROLE_LABELS,
    TRANSLATION_ORGANISM_OPTIONS,
    TRANSLATION_RESISTANCE_OPTIONS,
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
                            with ui.card().classes("ph-resource-card ph-project-card p-4"):
                                with ui.row().classes("ph-project-card-main w-full"):
                                    with ui.element("div").classes("ph-icon-box ph-icon-project"):
                                        ui.icon("folder_open")
                                    with ui.column().classes("ph-project-card-text"):
                                        ui.label(project["name"]).classes("ph-card-title")
                                        ui.label(project["description"] or "暂无描述").classes("ph-card-description")
                                with ui.row().classes("ph-project-card-footer w-full"):
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
                            with ui.row().classes("gap-2"):
                                ui.button("批量导入", icon="drive_folder_upload", on_click=lambda: bulk_import_dialog.open()).props("flat no-wrap")
                                ui.button("新建蛋白", icon="add", on_click=lambda: protein_dialog.open()).props("unelevated no-wrap")
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
                                                if protein["protein_type"]:
                                                    ui.badge(protein["protein_type"]).props("outline")
                                            ui.label(protein["description"] or "暂无描述").classes("ph-card-description")
                                            target_text = f" · 靶标 {protein['target']}" if protein["target"] else ""
                                            ui.label(f"{len(protein['sequence'])} 个氨基酸 · {protein['artifact_count']} 份资料{target_text}").classes("ph-meta")
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
                                                ui.badge(
                                                    humanize(batch.get("order_status") or "not_ordered")
                                                ).props("outline color=secondary")
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
                            """
                            const fieldValue = (selector) => {
                                const element = document.querySelector(selector);
                                return element ? element.value : '';
                            };
                            return {
                                name: fieldValue('.ph-protein-name-input input'),
                                sequence: fieldValue('.ph-protein-sequence-input textarea'),
                                description: fieldValue('.ph-protein-description-input textarea'),
                                protein_type: fieldValue('.ph-protein-type-select input'),
                                target: fieldValue('.ph-protein-target-input input'),
                                has_structure_file: Boolean(window.phProteinStructureFile),
                            };
                            """,
                            timeout=5,
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

            with ui.dialog() as bulk_import_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("批量导入蛋白").classes("text-lg font-semibold")
                bulk_protein_type = ui.select(PROTEIN_TYPE_OPTIONS, value="TCR", label="类型").props("outlined").classes("w-full ph-bulk-protein-type-select")
                bulk_protein_target = ui.input("靶标").props("outlined").classes("w-full ph-bulk-protein-target-input")
                bulk_protein_description = ui.textarea("描述").props("outlined").classes("w-full ph-bulk-protein-description-input")
                bulk_import_status = ui.label("等待选择文件夹").classes("ph-meta ph-bulk-import-status")
                bulk_select_button = ui.button("选择文件夹", icon="drive_folder_upload").props("flat")

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
                            if (status) status.textContent = `已选择 ${{files.length}} 个文件，点击导入开始`;
                            phNotify(`已选择 ${{files.length}} 个文件`, 'positive');
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
                            const fieldValue = (selector) => {{
                                const element = document.querySelector(selector);
                                return element ? element.value : '';
                            }};
                            if (files.length === 0) {{
                                phNotify('请先选择文件夹', 'negative');
                                return;
                            }}
                            try {{
                                if (status) status.textContent = `正在导入 ${{files.length}} 个文件...`;
                                const form = new FormData();
                                form.append('protein_type', fieldValue('.ph-bulk-protein-type-select input') || 'TCR');
                                form.append('target', fieldValue('.ph-bulk-protein-target-input input'));
                                form.append('description', fieldValue('.ph-bulk-protein-description-input textarea'));
                                for (const file of files) {{
                                    form.append('files', file, file.webkitRelativePath || file.name);
                                }}
                                const imported = await phApi('/api/projects/{project_id}/proteins/import-structures', {{
                                    method: 'POST',
                                    body: form,
                                }});
                                window.phBulkImportFiles = [];
                                if (status) status.textContent = `已导入 ${{imported.length}} 个蛋白`;
                                phNotify(`已导入 ${{imported.length}} 个蛋白`, 'positive');
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
                    with ui.row().classes("items-center gap-2"):
                        batch_status_badge = ui.badge("未order").props("outline")
                        batch_status_button = ui.button(
                            "修改状态",
                            icon="published_with_changes",
                            on_click=lambda: status_dialog.open(),
                        ).props("flat dense no-wrap")
                    batch_meta = ui.row().classes("gap-2")

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
                                    if (skipped.length) {{
                                        const uploadedText = uploaded.length ? uploaded.join(', ') : '无';
                                        const skippedText = skipped.join(', ');
                                        setStatus(`AKTA 部分上传成功：成功 ${{uploadedText}}；失败 ${{skippedText}} 已传过`);
                                        phNotify(`AKTA 部分上传成功，失败板位：${{skippedText}} 已传过`, 'warning');
                                    }} else {{
                                        const uploadedCount = uploaded.length || selectedCount;
                                        setStatus(multiple
                                            ? `AKTA 结果上传成功：${{uploadedCount}} 个文件`
                                            : 'AKTA 单个结果上传成功'
                                        );
                                        phNotify(multiple ? 'AKTA 结果上传成功' : 'AKTA 单个结果上传成功', 'positive');
                                    }}
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

                    akta_single_upload_button.on(
                        "click",
                        js_handler=akta_upload_js(multiple=False),
                    )
                    akta_upload_button.on(
                        "click",
                        js_handler=akta_upload_js(multiple=True),
                    )

            with ui.dialog() as status_dialog, ui.card().classes("ph-dialog-card w-full max-w-md gap-4"):
                ui.label("修改批次状态").classes("text-lg font-semibold")
                batch_status_value = ui.select(
                    BATCH_ORDER_STATUS_OPTIONS,
                    value="not_ordered",
                    label="状态",
                ).props("outlined").classes("w-full")
                with ui.row().classes("justify-end w-full"):
                    ui.button("取消", on_click=status_dialog.close).props("flat")
                    ui.button(
                        "更新",
                        icon="published_with_changes",
                        on_click=lambda: update_batch_status(),
                    ).props("unelevated")

            translation_state = {"dna_fasta": ""}
            translation_in_flight = {"value": False}
            batch_editable_state = {"value": True}

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
                translation_status.text = "翻译中，请稍候"
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
                        timeout=30,
                    )
                    render_translation(result)
                    ui.notify("翻译完成", type="positive")
                except Exception as error:
                    translation_status.text = previous_status
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
                    result = await ui.run_javascript(
                        f"""
                        return await phApi('/api/batches/{batch_id}/status', {{
                            method: 'PATCH',
                            body: {{order_status: {batch_status_value.value!r}}},
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
                batch = data["batch"]
                wells = data["wells"]
                experiments = data["experiments"]
                order_status = batch.get("order_status") or "not_ordered"
                batch_editable = order_status == "not_ordered"
                batch_editable_state["value"] = batch_editable
                batch_title.text = batch["name"]
                batch_description.text = batch["description"] or "暂无描述"
                batch_status_badge.text = humanize(order_status)
                batch_status_value.value = order_status
                batch_status_button.visible = order_status != "fully_received"
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
                update_upload_status()
                akta_single_upload_button.enable()
                akta_upload_button.enable()
                akta_upload_status.text = "等待选择 AKTA zip 文件"
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
                with mapping_table:
                    with ui.element("div").classes("ph-mapping-row ph-mapping-head"):
                        ui.label("孔位").classes("ph-mapping-cell")
                        ui.label("蛋白").classes("ph-mapping-cell")
                        ui.label("类型").classes("ph-mapping-cell")
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

            with ui.row().classes("ph-section-bar w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("结构文件").classes("text-xl font-semibold")
                    ui.label("这个蛋白导入时保存的 PDB/mmCIF 文件。").classes("ph-muted")
            structure_file_column = ui.column().classes("w-full gap-3")

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
                structure_file_column.clear()
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/proteins/{protein_id}')", timeout=10)
                    protein = data["protein"]
                    protein_title.text = protein["name"]
                    sequence_text.text = sequence_display(protein["sequence"])
                    protein_description.text = protein["description"] or "暂无描述"
                    sequence_length_badge.text = f"{len(protein['sequence'])} 个氨基酸"
                    protein_meta.clear()
                    with protein_meta:
                        if protein["protein_type"]:
                            ui.badge(protein["protein_type"]).props("outline")
                        if protein["target"]:
                            ui.badge(f"靶标 {protein['target']}").props("outline color=secondary")
                    with structure_file_column:
                        if not protein["structure_storage_path"]:
                            empty_state("description", "还没有结构文件", "从 PDB/mmCIF 新建或批量导入蛋白后会显示在这里。")
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
