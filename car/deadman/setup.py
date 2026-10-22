import os
from glob import glob

from setuptools import setup

package_name = "deepracer_deadman"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Vivek Raja",
    maintainer_email="vivekraja98@gmail.com",
    description="On-car deadman: zero the servos 300 ms after the laptop heartbeat stops.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={"console_scripts": ["deadman_node = deepracer_deadman.deadman_node:main"]},
)
