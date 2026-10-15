#!/usr/bin/env python3

import sys
import time
import rclpy

from onrobot_rg_msgs.srv import SetCommand

from bin_positions.light_bin_a import BIN_A_DROP_JOINT
from bin_positions.dark_bin_b import BIN_B_DROP_JOINT


# =========================================================
# ROBOT
# =========================================================

ROBOT_ID = "dsr01"
ROBOT_MODEL = "m0609"

import DR_init

DR_init.__dsr__id = ROBOT_ID
DR_init.__dsr__model = ROBOT_MODEL


# =========================================================
# HOME
# =========================================================

HOME_JOINT = [
    4.082763,
    0.205531,
    89.906761,
   -0.007050,
    89.820404,
    2.095609
]


# =========================================================
# BIN 이동 속도
#
# 중간 깔짝 이동 없음.
# HOME -> BIN 한 번의 movej
# BIN  -> HOME 한 번의 movej
# =========================================================

BIN_MOVE_VEL = 50.0
BIN_MOVE_ACC = 50.0


# =========================================================
# RG2 OPEN
# =========================================================

def rg2_open(node, client):

    print("")
    print("[RG2] OPEN")

    if not client.wait_for_service(timeout_sec=3.0):

        raise RuntimeError(
            "/onrobot/sendCommand unavailable"
        )


    request = SetCommand.Request()

    request.command = "o"


    future = client.call_async(
        request
    )


    rclpy.spin_until_future_complete(
        node,
        future,
        timeout_sec=5.0
    )


    result = future.result()


    if result is None:

        raise RuntimeError(
            "RG2 response timeout"
        )


    if not result.success:

        raise RuntimeError(
            f"RG2 OPEN failed: {result.message}"
        )


    time.sleep(1.0)


# =========================================================
# MAIN
# =========================================================

def main():


    # -----------------------------------------------------
    # LIGHT / DARK 선택
    # -----------------------------------------------------

    if len(sys.argv) != 2:

        print("")
        print("사용법:")
        print("python3 bin_drop_test.py LIGHT")
        print("python3 bin_drop_test.py DARK")
        print("")

        return


    laundry_type = sys.argv[1].upper()


    if laundry_type == "LIGHT":

        target_joint = BIN_A_DROP_JOINT
        target_name = "LIGHT BIN_A"


    elif laundry_type == "DARK":

        target_joint = BIN_B_DROP_JOINT
        target_name = "DARK BIN_B"


    else:

        print("")
        print("ERROR: LIGHT 또는 DARK만 입력")
        print("")

        return


    # =====================================================
    # ROS
    # =====================================================

    rclpy.init()


    node = rclpy.create_node(
        "bin_drop_test",
        namespace=ROBOT_ID
    )


    DR_init.__dsr__node = node


    from DSR_ROBOT2 import (
        posj,
        movej
    )


    HOME = posj(
        *HOME_JOINT
    )


    BIN_TARGET = posj(
        *target_joint
    )


    rg2_client = node.create_client(
        SetCommand,
        "/onrobot/sendCommand"
    )


    try:


        # =================================================
        # 1. HOME
        # =================================================

        print("")
        print("========================================")
        print("[1] MOVE HOME")
        print("========================================")


        movej(
            HOME,
            v=BIN_MOVE_VEL,
            a=BIN_MOVE_ACC
        )


        # =================================================
        # 2. HOME -> BIN
        #
        # 중간 위치 없음
        # movej 한 번
        # =================================================

        print("")
        print("========================================")
        print("[2] MOVE TO", target_name)
        print("ONE MOVEJ")
        print("VEL =", BIN_MOVE_VEL)
        print("ACC =", BIN_MOVE_ACC)
        print("========================================")


        movej(
            BIN_TARGET,
            v=BIN_MOVE_VEL,
            a=BIN_MOVE_ACC
        )


        # =================================================
        # 3. RG2 OPEN
        #
        # 실제 빨래가 있으면 여기서 투하
        # =================================================

        print("")
        print("========================================")
        print("[3] RG2 OPEN")
        print("DROP ->", target_name)
        print("========================================")


        rg2_open(
            node,
            rg2_client
        )


        # =================================================
        # 4. BIN -> HOME
        #
        # 역시 movej 한 번
        # =================================================

        print("")
        print("========================================")
        print("[4] RETURN HOME")
        print("ONE MOVEJ")
        print("========================================")


        movej(
            HOME,
            v=BIN_MOVE_VEL,
            a=BIN_MOVE_ACC
        )


        print("")
        print("========================================")
        print("BIN DROP TEST SUCCESS")
        print(target_name)
        print("========================================")


    finally:

        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":

    main()
