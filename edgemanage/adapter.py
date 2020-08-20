"""
Non-commandline adapter, work with Django
"""

import yaml
import os


class EdgemanageAdapter(object):

    def __init__(self, config_path, dnet):
        """
        Init adapter with `config`, `edge_list`
        """

        # load config
        with open(config_path) as config_f:
            self.config = yaml.safe_load(config_f.read())

        # load edge list
        with open(os.path.join(self.config["edgelist_dir"], dnet)) as edge_f:
            self.edge_list = [i.strip() for i in edge_f.read().split("\n")
                              if i.strip() and not i.startswith("#")]

    def get_config(self, config_str):
        return self.config[config_str] if config_str in self.config else None
