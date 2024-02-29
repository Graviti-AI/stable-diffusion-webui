import base64
import os
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
    head += """
    <script>
        async function isUserInEEA() {
            try {
                // Fetch the user's IP address information
                const response = await fetch('https://ipapi.co/json/');
                const data = await response.json();

                // Check if the country is in the EEA
                // The list of EEA country codes might need updating from time to time
                const eeaCountries = [
                    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
                    'HU', 'IS', 'IE', 'IT', 'LV', 'LI', 'LT', 'LU', 'MT', 'NL', 'NO', 'PL',
                    'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'GB', 'GF', 'GP', 'MQ', 'ME', 'YT',
                    'RE', 'MF', 'GI', 'AX', 'PM', 'GL', 'BL', 'SX', 'AW', 'CW', 'WF', 'PF',
                    'NC', 'TF', 'AI', 'BM', 'IO', 'VG', 'KY', 'FK', 'MS', 'PN', 'SH', 'GS',
                    'TC', 'AD', 'SM', 'VA', 'JE', 'GG', 'SJ'
                ];

                return eeaCountries.includes(data.country_code);
            } catch (error) {
                console.error('Error determining user location:', error);
                return false; // Or handle the error as appropriate for your application
            }
        }
    </script>
    """
    head += """
    <script>
        // Define dataLayer and the gtag function.
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        const adStorageConsent = Cookies.get('_ad_consent_ad_storage');
        const adUserDataConsent = Cookies.get('_ad_consent_user_data');
        const adPersonalizationConsent = Cookies.get('_ad_consent_personalization');
        const adAnalyticsStorageConsent = Cookies.get('_ad_consent_analytics_storage');

        if (
            typeof adStorageConsent === 'undefined' ||
            typeof adUserDataConsent === 'undefined' ||
            typeof adPersonalizationConsent === 'undefined' ||
            typeof adAnalyticsStorageConsent === 'undefined'
        ) {
            isUserInEEA().then(isInEEA => {
                if (isInEEA) {
                    gtag('consent', 'default', {
                        'ad_storage': adStorageConsent == null? 'denied' : adStorageConsent,
                        'ad_user_data': adUserDataConsent == null? 'denied' : adUserDataConsent,
                        'ad_personalization': adPersonalizationConsent == null? 'denied' : adPersonalizationConsent,
                        'analytics_storage': adAnalyticsStorageConsent == null? 'denied' : adAnalyticsStorageConsent,
                        'wait_for_update': 500
                    });
                    gtag("set", "ads_data_redaction", true);
                } else {
                    gtag('consent', 'default', {
                        'ad_storage': adStorageConsent == null? 'granted' : adStorageConsent,
                        'ad_user_data': adUserDataConsent == null? 'granted' : adUserDataConsent,
                        'ad_personalization': adPersonalizationConsent == null? 'granted' : adPersonalizationConsent,
                        'analytics_storage': adAnalyticsStorageConsent == null? 'granted' : adAnalyticsStorageConsent,
                        'wait_for_update': 500
                    });
                    gtag("set", "ads_data_redaction", true);
                    if (adStorageConsent == null) {
                        Cookies.set('_ad_consent_ad_storage', 'granted', { expires: 730 });
                    }
                    if (adUserDataConsent == null) {
                        Cookies.set('_ad_consent_user_data', 'granted', { expires: 730 });
                    }
                    if (adPersonalizationConsent == null) {
                        Cookies.set('_ad_consent_personalization', 'granted', { expires: 730 });
                    }
                    if (adAnalyticsStorageConsent == null) {
                        Cookies.set('_ad_consent_analytics_storage', 'granted', { expires: 730 });
                    }

                }
            });
        } else {
            gtag('consent', 'default', {
                'ad_storage': adStorageConsent,
                'ad_user_data': adUserDataConsent,
                'ad_personalization': adPersonalizationConsent,
                'analytics_storage': adAnalyticsStorageConsent,
                'wait_for_update': 500
            });
            gtag("set", "ads_data_redaction", true);
        }

    </script>
    """
    head += '<script async src="https://www.googletagmanager.com/gtag/js?id=G-6SKEYMGQ07"></script>\n'

    head += f"""
        <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag('js', new Date());
        const domain = window.location.hostname;
        if (domain.includes("diffus.me")) {{
            gtag('config', 'G-649WH3932W', {{'user_id': '{base64_encoded_user_id}', 'user_properties': {{'user_tier': '{user.tire}'}}}});
        }} else {{
            gtag('config', 'G-6SKEYMGQ07', {{'user_id': '{base64_encoded_user_id}', 'user_properties': {{'user_tier': '{user.tire}'}}}});
        }}
        window.gaIsBlocked = true;
        gtag('event', 'login', {{
            event_callback: function() {{
                window.gaIsBlocked = false;
            }},
        }});
        gtag('event', 'conversion', {{'send_to': 'AW-347751974/bf1-CL-J5c0YEKaM6aUB'}});
        </script>\n
    """
    head += """
        <script>
        !function (w, d, t) {
        w.TiktokAnalyticsObject=t;var ttq=w[t]=w[t]||[];ttq.methods=["page","track","identify","instances","debug","on","off","once","ready","alias","group","enableCookie","disableCookie"],ttq.setAndDefer=function(t,e){t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}};for(var i=0;i<ttq.methods.length;i++)ttq.setAndDefer(ttq,ttq.methods[i]);ttq.instance=function(t){for(var e=ttq._i[t]||[],n=0;n<ttq.methods.length;n++)ttq.setAndDefer(e,ttq.methods[n]);return e},ttq.load=function(e,n){var i="https://analytics.tiktok.com/i18n/pixel/events.js";ttq._i=ttq._i||{},ttq._i[e]=[],ttq._i[e]._u=i,ttq._t=ttq._t||{},ttq._t[e]=+new Date,ttq._o=ttq._o||{},ttq._o[e]=n||{};var o=document.createElement("script");o.type="text/javascript",o.async=!0,o.src=i+"?sdkid="+e+"&lib="+t;var a=document.getElementsByTagName("script")[0];a.parentNode.insertBefore(o,a)};

        ttq.load('CNEPRBJC77UAB35RF8C0');
        ttq.page();
        }(window, document, 'ttq');
        </script>
    """
    head += '<script src="https://cdn.jsdelivr.net/gh/cferdinandi/tabby@12/dist/js/tabby.polyfills.min.js"></script>\n'
    head += '<script src="/components/js/scrollload/index.js"></script>\n'
    head += '<script src=" https://cdn.jsdelivr.net/npm/intro.js@7.2.0/intro.min.js"></script>\n'

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
