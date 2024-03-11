import base64
import os
import time
import gradio as gr

from modules import localization, shared, scripts
from modules.paths import script_path, data_path, cwd
import modules.user


def webpath(fn):
    if fn.startswith(cwd):
        web_path = os.path.relpath(fn, cwd)
    else:
        web_path = os.path.abspath(fn)

    return f'file={web_path}?{os.path.getmtime(fn)}'


def javascript_html(request: gr.Request):
    user = modules.user.User.current_user(request)
    base64_encoded_user_id = base64.b64encode(user.uid.encode('utf-8')).decode('utf-8')
    # Ensure localization is in `window` before scripts
    head = f'<script type="text/javascript">{localization.localization_js(request.cookies.get("localization", "None"))}</script>\n'

    script_js = os.path.join(script_path, "script.js")
    head += f'<script type="text/javascript" src="{webpath(script_js)}"></script>\n'
    head += '<script type="text/javascript" src="https://cdn.jsdelivr.net/npm/vue@2.7.14"></script>\n'
    head += '<script src="https://cdn.jsdelivr.net/npm/js-base64@3.7.5/base64.min.js"></script>\n'
    head += '<script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/buefy/0.9.23/buefy.min.js"></script>\n'
    head += '<script type="text/javascript" src="https://cdn.jsdelivr.net/npm/vuetify@2.4.0/dist/vuetify.js"></script>\n'
    head += '<script src="https://cdnjs.cloudflare.com/ajax/libs/clipboard.js/2.0.11/clipboard.min.js"></script>\n'
    head += '<script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"></script>\n'
    # head += '<script type="text/javascript" src="/public/js/calarity.js"></script>\n'
    head += '<script type="text/javascript" src="/public/js/posthog.js?v=0.2"></script>\n'
    head += '<script type="text/javascript" src="/components/js/notification/index.var.js"></script>\n'
    head += '<script type="text/javascript" src="/components/js/share/shareon.iife.js" defer init></script>\n'
    head += '<script type="text/javascript" src="/public/js/js.cookie.js"></script>\n'
    head += f'<script type="text/javascript" src="/public/js/analytics/consent.js?version={time.time()}"></script>\n'
    head += '<script async src="https://www.googletagmanager.com/gtag/js?id=G-6SKEYMGQ07"></script>\n'
    head += f'<script type="text/javascript" src="/public/js/analytics/init.js?version={time.time()}"></script>\n'
    head += f"""
    <script>
        configGtag('{base64_encoded_user_id}', {{'user_tier': '{user.tire}'}});
    </script>
    """
    head += f'<script type="module" src="/public/js/analytics/cookieconsent-config.mjs?version={time.time()}"></script>\n'
    head += '<script src="https://cdn.jsdelivr.net/gh/cferdinandi/tabby@12/dist/js/tabby.polyfills.min.js"></script>\n'
    head += '<script src="/components/js/scrollload/index.js"></script>\n'
    head += '<script src=" https://cdn.jsdelivr.net/npm/intro.js@7.2.0/intro.min.js"></script>\n'
    head += f'<script type="text/javascript" src="/public/js/analytics/turn.js?version={time.time()}"></script>\n'

    for script in scripts.list_scripts("javascript", ".js"):
        head += f'<script type="text/javascript" src="{webpath(script.path)}"></script>\n'

    for script in scripts.list_scripts("javascript", ".mjs"):
        head += f'<script type="module" src="{webpath(script.path)}"></script>\n'

    if shared.cmd_opts.theme:
        head += f'<script type="text/javascript">set_theme(\"{shared.cmd_opts.theme}\");</script>\n'

    return head


def css_html():
    head = ""

    head += '<link href="https://releases.transloadit.com/uppy/v3.7.0/uppy.min.css" rel="stylesheet" />\n'
    head += '<link href="/components/style/notification/style.css?v=0.2" rel="stylesheet" />\n'
    head += '<link href="/components/style/share/shareon.min.css" rel="stylesheet" />\n'
    head += '<link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/gh/cferdinandi/tabby@12/dist/css/tabby-ui.min.css">\n'

    head += '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/buefy/0.9.23/buefy.min.css">\n'
    head += '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/vuetify@2.4.0/dist/vuetify.min.css">\n'
    head += '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@mdi/font@5.8.55/css/materialdesignicons.min.css">\n'
    head += '<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Material+Icons">\n'
    head += '<link rel="stylesheet" href="https://use.fontawesome.com/releases/v5.2.0/css/all.css">\n'
    head += '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/intro.js@7.2.0/minified/introjs.min.css">\n'
    head += '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orestbida/cookieconsent@v3.0.0/dist/cookieconsent.css">\n'

    def stylesheet(fn):
        return f'<link rel="stylesheet" property="stylesheet" href="{webpath(fn)}">\n'

    for cssfile in scripts.list_files_with_name("style.css"):
        if not os.path.isfile(cssfile):
            continue

        head += stylesheet(cssfile)

    if os.path.exists(os.path.join(data_path, "user.css")):
        head += stylesheet(os.path.join(data_path, "user.css"))

    return head


def reload_javascript():
    css = css_html()

    def template_response(*args, **kwargs):
        js = javascript_html(args[1]['request'])
        res = shared.GradioTemplateResponseOriginal(*args, **kwargs)
        res.body = res.body.replace(b'</head>', f'{js}</head>'.encode("utf8"))
        res.body = res.body.replace(b'</body>', f'{css}</body>'.encode("utf8"))
        res.init_headers()
        return res

    gr.routes.templates.TemplateResponse = template_response


if not hasattr(shared, 'GradioTemplateResponseOriginal'):
    shared.GradioTemplateResponseOriginal = gr.routes.templates.TemplateResponse
