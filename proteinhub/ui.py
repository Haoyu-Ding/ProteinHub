from __future__ import annotations

from nicegui import ui


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


def shell() -> None:
    api_script()
    ui.colors(primary="#2563eb", secondary="#0f766e", accent="#f97316")
    with ui.header().classes("items-center justify-between bg-white text-slate-900 border-b"):
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
        api_script()
        ui.colors(primary="#2563eb", secondary="#0f766e", accent="#f97316")
        with ui.column().classes("mx-auto mt-20 w-full max-w-sm gap-4"):
            ui.label("ProteinHub").classes("text-3xl font-semibold text-slate-900")
            ui.label("Sequence-centered protein design workspace").classes("text-sm text-slate-600")
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

            ui.button("Continue", on_click=submit).classes("w-full")

    @ui.page("/projects")
    async def projects_page() -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("mx-auto w-full max-w-5xl gap-6 p-6"):
            with ui.row().classes("w-full items-end justify-between gap-4"):
                with ui.column().classes("gap-1"):
                    ui.label("Projects").classes("text-2xl font-semibold")
                    ui.label("Project-level permissions protect every protein, sequence, and artifact.").classes("text-sm text-slate-600")
                ui.button("New Project", icon="add", on_click=lambda: project_dialog.open())

            project_grid = ui.grid(columns="repeat(auto-fill, minmax(260px, 1fr))").classes("w-full gap-4")

            async def load_projects() -> None:
                project_grid.clear()
                try:
                    projects = await ui.run_javascript("return await phApi('/api/projects')", timeout=10)
                    with project_grid:
                        if not projects:
                            ui.label("No projects yet. Create one to start collecting sequences.").classes("text-slate-600")
                        for project in projects:
                            with ui.card().classes("gap-2"):
                                ui.label(project["name"]).classes("text-lg font-semibold")
                                ui.label(project["description"] or "No description").classes("text-sm text-slate-600")
                                ui.badge(project["role"]).props("outline")
                                ui.button("Open", icon="folder_open", on_click=lambda p=project: ui.navigate.to(f"/projects/{p['id']}")).props("flat")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            with ui.dialog() as project_dialog, ui.card().classes("w-full max-w-md"):
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
        with ui.column().classes("mx-auto w-full max-w-6xl gap-6 p-6"):
            title = ui.label("Project").classes("text-2xl font-semibold")
            description = ui.label().classes("text-sm text-slate-600")
            role_badge = ui.badge().props("outline")

            with ui.tabs().classes("w-full") as tabs:
                proteins_tab = ui.tab("Proteins")
                members_tab = ui.tab("Members")
            with ui.tab_panels(tabs, value=proteins_tab).classes("w-full"):
                with ui.tab_panel(proteins_tab).classes("gap-4"):
                    with ui.row().classes("w-full justify-between"):
                        ui.label("Proteins").classes("text-xl font-semibold")
                        ui.button("New Protein", icon="add", on_click=lambda: protein_dialog.open())
                    proteins_column = ui.column().classes("w-full gap-3")
                with ui.tab_panel(members_tab).classes("gap-4"):
                    with ui.row().classes("w-full justify-between"):
                        ui.label("Members").classes("text-xl font-semibold")
                        add_member_button = ui.button("Add Member", icon="person_add", on_click=lambda: member_dialog.open())
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
                            with ui.row().classes("w-full items-center justify-between border-b py-2"):
                                ui.label(member["email"]).classes("font-medium")
                                ui.badge(member["role"]).props("outline")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            async def load_proteins() -> None:
                proteins_column.clear()
                try:
                    proteins = await ui.run_javascript(f"return await phApi('/api/projects/{project_id}/proteins')", timeout=10)
                    with proteins_column:
                        if not proteins:
                            ui.label("No proteins yet. Create one, then add sequences.").classes("text-slate-600")
                        for protein in proteins:
                            with ui.card().classes("w-full"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(protein["name"]).classes("text-lg font-semibold")
                                        ui.label(protein["description"] or "No description").classes("text-sm text-slate-600")
                                    ui.button("Sequences", icon="list", on_click=lambda p=protein: ui.navigate.to(f"/proteins/{p['id']}")).props("flat")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            with ui.dialog() as protein_dialog, ui.card().classes("w-full max-w-md"):
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

            with ui.dialog() as member_dialog, ui.card().classes("w-full max-w-md"):
                ui.label("Add Member").classes("text-lg font-semibold")
                member_email = ui.input("Email").props("outlined").classes("w-full")
                member_role = ui.toggle(["member", "owner"], value="member")

                async def add_member() -> None:
                    try:
                        await ui.run_javascript(
                            f"return await phApi('/api/projects/{project_id}/members', {{method: 'POST', body: {{email: {member_email.value!r}, role: {member_role.value!r}}}}})",
                            timeout=10,
                        )
                        member_dialog.close()
                        member_email.value = ""
                        await load_project()
                    except Exception as error:
                        ui.notify(str(error), type="negative")

                with ui.row().classes("justify-end w-full"):
                    ui.button("Cancel", on_click=member_dialog.close).props("flat")
                    ui.button("Add", icon="person_add", on_click=add_member)

            await load_project()
            await load_proteins()

    @ui.page("/proteins/{protein_id}")
    async def protein_page(protein_id: int) -> None:
        shell()
        if not await ensure_logged_in():
            return
        with ui.column().classes("mx-auto w-full max-w-6xl gap-6 p-6"):
            ui.label("Sequences").classes("text-2xl font-semibold")
            ui.label("Sequences are the center of ProteinHub; artifacts attach here.").classes("text-sm text-slate-600")
            with ui.row().classes("w-full justify-end"):
                ui.button("New Sequence", icon="add", on_click=lambda: sequence_dialog.open())
            sequences_column = ui.column().classes("w-full gap-3")

            async def load_sequences() -> None:
                sequences_column.clear()
                try:
                    sequences = await ui.run_javascript(f"return await phApi('/api/proteins/{protein_id}/sequences')", timeout=10)
                    with sequences_column:
                        if not sequences:
                            ui.label("No sequences yet.").classes("text-slate-600")
                        for sequence in sequences:
                            with ui.card().classes("w-full"):
                                with ui.row().classes("w-full items-start justify-between"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(sequence["name"]).classes("text-lg font-semibold")
                                        if sequence["version_tag"]:
                                            ui.badge(sequence["version_tag"]).props("outline")
                                        ui.label(sequence["sequence"][:80] + ("..." if len(sequence["sequence"]) > 80 else "")).classes("font-mono text-sm text-slate-700")
                                    ui.button("Open", icon="science", on_click=lambda s=sequence: ui.navigate.to(f"/sequences/{s['id']}")).props("flat")
                except Exception as error:
                    ui.notify(str(error), type="negative")

            with ui.dialog() as sequence_dialog, ui.card().classes("w-full max-w-2xl"):
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
        with ui.column().classes("mx-auto w-full max-w-6xl gap-6 p-6"):
            sequence_title = ui.label("Sequence").classes("text-2xl font-semibold")
            sequence_meta = ui.row().classes("gap-2")
            sequence_text = ui.label().classes("font-mono whitespace-pre-wrap rounded bg-slate-100 p-4 text-sm")
            sequence_description = ui.label().classes("text-sm text-slate-600")
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Artifacts").classes("text-xl font-semibold")
                upload_button = ui.button("Upload Artifact", icon="upload").props("flat")
            artifacts_column = ui.column().classes("w-full gap-3")

            async def load_sequence() -> None:
                artifacts_column.clear()
                try:
                    data = await ui.run_javascript(f"return await phApi('/api/sequences/{sequence_id}')", timeout=10)
                    sequence = data["sequence"]
                    sequence_title.text = sequence["name"]
                    sequence_text.text = sequence["sequence"]
                    sequence_description.text = sequence["description"] or "No description"
                    sequence_meta.clear()
                    with sequence_meta:
                        ui.badge(f"{len(sequence['sequence'])} aa").props("outline")
                        if sequence["version_tag"]:
                            ui.badge(sequence["version_tag"]).props("outline")
                    with artifacts_column:
                        if not data["artifacts"]:
                            ui.label("No artifacts uploaded yet.").classes("text-slate-600")
                        for artifact in data["artifacts"]:
                            with ui.card().classes("w-full"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    with ui.column().classes("gap-1"):
                                        ui.label(artifact["filename"]).classes("font-semibold")
                                        ui.label(f"{artifact['artifact_type']} · {artifact['mime_type']} · {artifact['size_bytes']} bytes").classes("text-sm text-slate-600")
                                    with ui.row().classes("gap-2"):
                                        ui.button("Download", icon="download", on_click=lambda a=artifact: download_artifact(a["id"], a["filename"])).props("flat")
                                        ui.button("Delete", icon="delete", on_click=lambda a=artifact: delete_artifact(a["id"])).props("flat color=negative")
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
                            await phApi('/api/sequences/{sequence_id}/artifacts', {{
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
