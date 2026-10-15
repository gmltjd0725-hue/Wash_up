from setuptools import setup


package_name = "object_detection"


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
        )
    ],

    install_requires=[
        "setuptools"
    ],

    zip_safe=True,

    maintainer="rokey",

    maintainer_email="rokey@todo.todo",

    description="YOLO laundry object detection",

    license="Apache-2.0",

    entry_points={

        "console_scripts": [

            "webcam = "
            "object_detection.webcam:main",

            "detection_node = "
            "object_detection.detection_node:main"
        ]
    }
)