import os
from setuptools import setup

setup(
    name = "edgemanage",
    version = "2.0.2",
    author = "Hugh Nowlan",
    author_email = "nosmo@nosmo.me",
    description = "HTTP availability management tool",
    license = "Hacktivismo Enhanced-Source Software License Agreement",
    keywords = "edgemanage deflect DNS",
    url = "http://github.com/equalitie/edgemanage",
    packages=['edgemanage'],
    package_data={'edgemanage': ['templates/*.j2']},
    install_requires=[
        "Jinja2",
        "setproctitle",
        "pyyaml",
        "futures",
        "requests"
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Internet :: Name Service (DNS)",
        "Topic :: Utilities",
        ],
    scripts = ["edge_manage", "edge_query", "edge_conf"],
    )
