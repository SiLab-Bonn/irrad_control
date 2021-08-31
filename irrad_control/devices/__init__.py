from os.path import isfile
from irrad_control.utils.tools import location, load_yaml, make_path


# Check if config files need to be loaded for device inits
def load_device_init_configs():
    # Loop over devices in device config dict
    for dev, init in DEVICES_CONFIG.items():

        # Config is in init
        if 'config' in init:

            # Check if config is already a dict or needs to be loaded from yaml
            if not isinstance(init['config'], dict):
                # Check if config file exists and overwrite, otherwise config is None
                init['config'] = None if not isfile(init['config']) else load_yaml(init['config'])


DEVICES_CONFIG = load_yaml(make_path(location(__file__), 'devices_config.yaml'))


load_device_init_configs()
