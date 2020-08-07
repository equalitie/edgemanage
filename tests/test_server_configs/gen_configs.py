#!/usr/bin/env python
"""
Script for generating configuration files for the test web server
"""
from __future__ import absolute_import
from __future__ import print_function
import sys
import yaml
from six.moves import range
from six.moves import input

# Offset ID for the canary edges on the web server
CANARY_ID_OFFSET = 100


class ExplicitDumper(yaml.SafeDumper):
    """A dumper that will never emit YAML aliases."""
    def ignore_aliases(self, data):
        return True


def configure_in_chunks(name, total_size, id_offset=0):
    """
    Set a config dictionary for a chunk of relays
    """
    i = 1

    result_dict = {}
    while i <= total_size:
        # We can configure up to the number of edges remaining
        items_remaining = (total_size+1) - i
        chunk_size = int(input(
            "Num of {} to config ({} remaining): ".format(name, items_remaining)
        ))
        chunk_size = min(chunk_size, items_remaining)

        # Read a Python object to use for chunk_size number of items
        item_config = eval(input("Dictonary for {} {}: ".format(chunk_size, name)))

        # Create chunk_size items in the result dictionary with this value
        for i in range(i, i+chunk_size):
            result_dict[i+id_offset] = item_config
        i += 1

    return result_dict


def main():
    # Prompt on stderr
    orig_stdout = sys.stdout
    sys.stdout = sys.stderr

    num_edges = min(int(input("Number of edges (max %d): " % CANARY_ID_OFFSET)),
                    CANARY_ID_OFFSET)

    max_canaries = 254 - CANARY_ID_OFFSET
    num_canaries = min(int(input("Number of canaries (max: %d): " % max_canaries)),
                       max_canaries)

    # Iterate and assign values for a certain number of edges:
    edge_dictonary = configure_in_chunks("edges", num_edges)
    canary_dictonary = configure_in_chunks("canaries", num_canaries,
                                           id_offset=CANARY_ID_OFFSET)
    edge_dictonary.update(canary_dictonary)

    # Output results without references
    sys.stdout = orig_stdout
    print((
        yaml.dump({'edge_list': edge_dictonary}, default_flow_style=False, Dumper=ExplicitDumper)))


if __name__ == '__main__':
    main()
