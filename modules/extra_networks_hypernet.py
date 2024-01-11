from modules import extra_networks, shared
from modules.hypernetworks import hypernetwork


class ExtraNetworkHypernet(extra_networks.ExtraNetwork):
    def __init__(self):
        super().__init__('hypernet')

    def activate(self, p, params_list):
        additional = shared.opts.sd_hypernetwork

        if additional != "None" and additional in shared.hypernetworks and not any(x for x in params_list if x.items[0] == additional):
            hypernet_prompt_text = f"<hypernet:{additional}:{shared.opts.extra_networks_default_multiplier}>"
            p.all_prompts = [f"{prompt}{hypernet_prompt_text}" for prompt in p.all_prompts]
            params_list.append(extra_networks.ExtraNetworkParams(items=[additional, shared.opts.extra_networks_default_multiplier]))

        names = []
        multipliers = []

        for params in params_list:
            assert params.items

            names.append(params.items[0])
            multipliers.append(float(params.items[1]) if len(params.items) > 1 else 1.0)


        hypernetwork_model_info = p.get_all_model_info().hypernetwork_models if names else {}
        hypernetwork.load_hypernetworks(names, hypernetwork_model_info, multipliers)

        network_hashes = []
        for item in shared.loaded_hypernetworks:
            shorthash = item.shorthash()
            if not shorthash:
                continue

            alias = item.name
            if not alias:
                continue

            alias = alias.replace(":", "").replace(",", "")

            network_hashes.append(f"{alias}: {shorthash}")

        if network_hashes:
            p.extra_generation_params["Hypernetwork hashes"] = ", ".join(network_hashes)

    def deactivate(self, p):
        pass
