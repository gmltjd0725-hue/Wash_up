FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# ==============================
# ROS2 / OpenCV 관련 패키지
# ==============================

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-opencv \
    python3-colcon-common-extensions \
    ros-jazzy-cv-bridge \
    ros-jazzy-sensor-msgs \
    ros-jazzy-std-msgs \
    && rm -rf /var/lib/apt/lists/*


# ==============================
# Python 패키지
# ==============================

COPY requirements.txt /tmp/requirements.txt

RUN pip3 install \
    --break-system-packages \
    -r /tmp/requirements.txt


# ==============================
# ROS2 Workspace
# ==============================

WORKDIR /ros2_ws/src


# object_detection ROS2 package 복사
COPY object_detection /ros2_ws/src/object_detection


# ==============================
# ROS2 Build
# ==============================

WORKDIR /ros2_ws

RUN /bin/bash -c \
    "source /opt/ros/jazzy/setup.bash && \
     colcon build --symlink-install"


# ==============================
# ROS2 환경 자동 source
# ==============================

RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc

RUN echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc


# ==============================
# 실행 위치
# ==============================

WORKDIR /ros2_ws


CMD ["/bin/bash"]