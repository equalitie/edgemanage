from __future__ import absolute_import
from setuptools import setup

setup(
    name = "edgemanage",
    version = "2.1.2",
    author = "Donncha O Cearbhaill",
    author_email = "donncha@equalit.ie",
    description = "HTTP availability management tool",
    license = "Hacktivismo Enhanced-Source Software License Agreement",
    keywords = "edgemanage deflect DNS",
    url = "http://github.com/equalitie/edgemanage",
    packages=['edgemanage'],
    package_data={'edgemanage': ['templates/*.j2']},
    zip_safe=False,
    install_requires=[
        "Jinja2",
        "setproctitle",
        "pyyaml",
        "requests",
        "ipaddr",
        "six"
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Internet :: Name Service (DNS)",
        "Topic :: Utilities",
        ],
    scripts = ["edgemanage/edge_manage", "edgemanage/edge_query", "edgemanage/edge_conf"],
    )
