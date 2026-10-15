from setuptools import setup
from glob import glob
import os


package_name = "laundry_sorting"


setup(

    name=package_name,

    version="0.0.1",

    packages=[package_name],

    data_files=[

        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name]
        ),

        (
            "share/" + package_name,
            ["package.xml"]
        ),

        (
            os.path.join(
                "share",
                package_name,
                "config"
            ),
            glob("config/*.yaml")
        ),

        (
            os.path.join(
                "share",
                package_name,
                "sql"
            ),
            glob("sql/*.sql")
        ),

        (
            os.path.join(
                "share",
                package_name,
                "launch"
            ),
            glob("launch/*.launch.py")
        )
    ],

    install_requires=[
        "setuptools"
    ],

    zip_safe=True,

    maintainer="rokey",

    maintainer_email="rokey@todo.todo",

    description="Laundry sorting assistant",

    license="Apache-2.0",

    entry_points={

        "console_scripts": [

            "laundry_controller = "
            "laundry_sorting.laundry_controller:main",

            "webcam_publisher = "
            "laundry_sorting.webcam_publisher:main",

            "laundry_detection_publisher = "
            "laundry_sorting.laundry_detection_publisher:main",

            "laundry_person_filter_viewer = "
            "laundry_sorting.laundry_person_filter_viewer:main",

            "bin_ocr_viewer = "
            "laundry_sorting.bin_ocr_viewer:main",

            "bin_ocr_publisher = "
            "laundry_sorting.bin_ocr_publisher:main",

            "bin_color_publisher = "
            "laundry_sorting.bin_color_publisher:main",

            "bin_color_viewer = "
            "laundry_sorting.bin_color_viewer:main",

            "bin_position_resolver = "
            "laundry_sorting.bin_position_resolver:main",

            "laundry_pick_force_test = "
            "laundry_sorting.laundry_pick_force_test:main",

            "bin_move_test = "
            "laundry_sorting.bin_move_test:main",
        ]
    }
)
