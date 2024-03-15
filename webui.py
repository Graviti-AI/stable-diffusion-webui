from __future__ import annotations

import os
import time

from modules.state_holder import make_state_holder
from modules.launch_utils import startup_timer
from modules import timer
from modules import initialize_util
from modules import initialize
from threading import Thread
from modules_forge.initialization import initialize_forge
from modules_forge import main_thread


startup_timer.record("launcher")

initialize_forge()

initialize.imports()

initialize.check_versions()

initialize.initialize()

MAX_ANYIO_WORKER_THREAD = 64


def create_api(app):
    from modules.api.api import Api
    from modules.call_queue import submit_to_gpu_worker

    api = Api(app, submit_to_gpu_worker)
    return api


def api_only_worker(server_port: int = 0):
    from fastapi import FastAPI
    from modules.shared_cmd_options import cmd_opts

    app = FastAPI()
    make_state_holder(app)
    initialize_util.setup_middleware(app)
    api = create_api(app)

    from modules.api.daemon_api import DaemonApi
    DaemonApi(app)

    from modules import script_callbacks
    script_callbacks.before_ui_callback()
    script_callbacks.app_started_callback(None, app)

    print(f"Startup time: {startup_timer.summary()}.")
    if not server_port:
        server_port = cmd_opts.port if cmd_opts.port else 7861

    api.launch(
        server_name=initialize_util.gradio_server_name(),
        port=server_port,
        root_path=f"/{cmd_opts.subpath}" if cmd_opts.subpath else ""
    )


def stop_route(request):
    from fastapi import Response, HTTPException, status
    from modules import shared

    if shared.state is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="shared.state is not initialized.")
    shared.state.server_command = "stop"
    return Response("Stopping.")


def webui_worker(server_port: int = 0):
    from modules.shared_cmd_options import cmd_opts
    from modules import shared
    from fastapi import FastAPI, HTTPException, status

    launch_api = cmd_opts.api
    if not server_port:
        server_port = cmd_opts.port if cmd_opts.port else 7861
    if shared.state is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="shared.state is not initialized.")
    shared.state.server_port = server_port

    from modules import shared, ui_tempdir, script_callbacks, ui, progress, ui_extra_networks

    if shared.opts is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="shared.opts is not initialized.")

    while 1:
        if shared.opts.clean_temp_dir_at_start:
            ui_tempdir.cleanup_tmpdr()
            startup_timer.record("cleanup temp dir")

        script_callbacks.before_ui_callback()
        startup_timer.record("scripts before_ui_callback")

        shared.demo = ui.create_ui()
        startup_timer.record("create ui")

        if not cmd_opts.no_gradio_queue:
            shared.demo.queue(MAX_ANYIO_WORKER_THREAD)

        gradio_auth_creds = list(initialize_util.get_gradio_auth_creds()) or None

        auto_launch_browser = False
        if os.getenv('SD_WEBUI_RESTARTING') != '1':
            if shared.opts.auto_launch_browser == "Remote" or cmd_opts.autolaunch:
                auto_launch_browser = True
            elif shared.opts.auto_launch_browser == "Local":
                auto_launch_browser = not cmd_opts.webui_is_non_local

        app, local_url, share_url = shared.demo.launch(
            share=cmd_opts.share,
            server_name=initialize_util.gradio_server_name(),
            server_port=server_port,
            ssl_keyfile=cmd_opts.tls_keyfile,
            ssl_certfile=cmd_opts.tls_certfile,
            ssl_verify=cmd_opts.disable_tls_verify,
            debug=cmd_opts.gradio_debug,
            auth=gradio_auth_creds,
            inbrowser=auto_launch_browser,
            prevent_thread_lock=True,
            allowed_paths=cmd_opts.gradio_allowed_path,
            max_threads=MAX_ANYIO_WORKER_THREAD,
            app_kwargs={
                "docs_url": "/docs",
                "redoc_url": "/redoc",
            },
            root_path=f"/{cmd_opts.subpath}" if cmd_opts.subpath else "",
        )
        make_state_holder(app)
        if cmd_opts.add_stop_route:
            app.add_route("/_stop", stop_route, methods=["POST"])

        startup_timer.record("gradio launch")

        # gradio uses a very open CORS policy via app.user_middleware, which makes it possible for
        # an attacker to trick the user into opening a malicious HTML page, which makes a request to the
        # running web ui and do whatever the attacker wants, including installing an extension and
        # running its code. We disable this here. Suggested by RyotaK.
        app.user_middleware = [x for x in app.user_middleware if x.cls.__name__ != 'CORSMiddleware']

        initialize_util.setup_middleware(app)

        progress.setup_progress_api(app)
        ui.setup_ui_api(app)

        if launch_api:
            create_api(app)
        from modules.api.daemon_api import DaemonApi
        DaemonApi(app)

        from modules.ui_common import add_static_filedir_to_demo
        add_static_filedir_to_demo(app, route="components")
        ui_extra_networks.add_pages_to_demo(app)

        startup_timer.record("add APIs")

        with startup_timer.subcategory("app_started_callback"):
            script_callbacks.app_started_callback(shared.demo, app)

        import modules.launch_utils
        modules.launch_utils.startup_record = startup_timer.dump()
        print(f"Startup time: {startup_timer.summary()}.")

        import gradio
        @app.on_event("shutdown")
        def shutdown_event():
            gradio.close_all()

        if cmd_opts.subpath:
            redirector = FastAPI()
            redirector.get("/")
            gradio.mount_gradio_app(redirector, shared.demo, path=f"/{cmd_opts.subpath}")

        server_command = None
        try:
            while shared.state and True:
                server_command = shared.state.wait_for_server_command(timeout=5)
                if server_command:
                    if server_command in ("stop", "restart"):
                        break
                    else:
                        print(f"Unknown server command: {server_command}")
        except KeyboardInterrupt:
            print('Caught KeyboardInterrupt, stopping...')
            server_command = "stop"

        if server_command == "stop":
            print("Stopping server...")
            # If we catch a keyboard interrupt, we want to stop the server and exit.
            shared.demo.close()
            break

        # disable auto launch webui in browser for subsequent UI Reload
        os.environ.setdefault('SD_WEBUI_RESTARTING', '1')

        print('Restarting UI...')
        shared.demo.close()
        time.sleep(0.5)
        startup_timer.reset()
        script_callbacks.app_reload_callback()
        startup_timer.record("app reload callback")
        script_callbacks.script_unloaded_callback()
        startup_timer.record("scripts unloaded callback")
        initialize.initialize_rest(reload_script_modules=True)

        from modules import sd_hijack, sd_hijack_optimizations
        script_callbacks.on_list_optimizers(sd_hijack_optimizations.list_optimizers)
        sd_hijack.list_optimizers()
        startup_timer.record("scripts list_optimizers")

        # disable auto restart
        if cmd_opts.disable_auto_restart:
            break

def api_only():
    Thread(target=api_only_worker, daemon=True).start()


def webui(server_port: int = 0):
    Thread(target=webui_worker, args=(server_port,), daemon=True).start()


if __name__ == "__main__":
    from modules.shared_cmd_options import cmd_opts

    if cmd_opts.nowebui:
        api_only()
    else:
        webui()

    main_thread.loop()
