import os
from setuptools import setup

setup(
    name = "edgemanage",
    version = "2.0.0",
    author = "Hugh Nowlan",
    author_email = "nosmo@nosmo.me",
    description = "DNS record scraper",
    license = "Hacktivismo Enhanced-Source Software License Agreement",
    keywords = "edgemanage deflect DNS",
    url = "http://github.com/equalitie/edgemanage",
    packages=['edgemanage'],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Internet :: Name Service (DNS)",
        "Topic :: Utilities",
        ],
    scripts = ["edgemanage.py"],
    )
