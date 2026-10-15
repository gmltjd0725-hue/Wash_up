from launch import LaunchDescription

from launch.actions import (
    SetEnvironmentVariable,
    DeclareLaunchArgument,
    RegisterEventHandler,
    LogInfo,
)

from launch.conditions import (
    IfCondition
)

from launch.event_handlers import (
    OnProcessExit
)

from launch_ros.actions import (
    Node
)

from launch_ros.substitutions import (
    FindPackageShare
)

from launch.substitutions import (
    PathJoinSubstitution,
    LaunchConfiguration,
)


def generate_launch_description():

    params_file = PathJoinSubstitution([
        FindPackageShare(
            "laundry_sorting"
        ),
        "config",
        "laundry_params.yaml"
    ])

    gui = LaunchConfiguration(
        "gui"
    )

    # ==========================================================
    # 항상 실행
    # ==========================================================

    webcam_node = Node(
        package="laundry_sorting",
        executable="webcam_publisher",
        name="webcam_publisher",
        output="screen"
    )

    controller_node = Node(
        package="laundry_sorting",
        executable="laundry_controller",
        name="laundry_controller",
        parameters=[
            params_file
        ],
        output="screen"
    )

    # ==========================================================
    # STAGE 1
    #
    # OCR + COLOR
    #
    # A OR LIGHT_PINK -> BIN_A
    # B OR BROWN      -> BIN_B
    # ==========================================================

    bin_ocr_publisher_node = Node(
        package="laundry_sorting",
        executable="bin_ocr_publisher",
        name="bin_ocr_publisher",
        output="screen"
    )

    bin_color_publisher_node = Node(
        package="laundry_sorting",
        executable="bin_color_publisher",
        name="bin_color_publisher",
        output="screen"
    )

    bin_ocr_viewer_node = Node(
        package="laundry_sorting",
        executable="bin_ocr_viewer",
        name="bin_ocr_viewer",
        output="screen",
        condition=IfCondition(
            gui
        )
    )

    # ==========================================================
    # STAGE 2
    #
    # Laundry + Voice
    #
    # BIN_A/B가 등록되어
    # bin_ocr_publisher가 끝난 후 실행
    # ==========================================================

    laundry_detection_node = Node(
        package="laundry_sorting",
        executable="laundry_detection_publisher",
        name="laundry_detection_publisher",
        output="screen"
    )

    laundry_viewer_node = Node(
        package="laundry_sorting",
        executable="laundry_person_filter_viewer",
        name="laundry_person_filter_viewer",
        output="screen",
        condition=IfCondition(
            gui
        )
    )

    voice_node = Node(
        package="voice_processing",
        executable="voice_node",
        name="voice_node",
        output="screen"
    )

    start_stage_2 = RegisterEventHandler(

        OnProcessExit(

            target_action=(
                bin_ocr_publisher_node
            ),

            on_exit=[

                LogInfo(
                    msg=(
                        "BIN OCR + COLOR 완료 "
                        "-> Laundry + Voice 시작"
                    )
                ),

                laundry_detection_node,

                laundry_viewer_node,

                voice_node,
            ]
        )
    )

    return LaunchDescription([

        DeclareLaunchArgument(
            "gui",
            default_value="false",
            description=(
                "Show vision viewer windows"
            )
        ),

        SetEnvironmentVariable(
            "DB_USER",
            "laundry_user"
        ),

        SetEnvironmentVariable(
            "DB_PASSWORD",
            "laundry123"
        ),

        # 항상 실행
        webcam_node,
        controller_node,

        # Stage 1
        bin_ocr_publisher_node,
        bin_color_publisher_node,
        bin_ocr_viewer_node,

        # Stage 1 완료 후 Stage 2
        start_stage_2,
    ])
