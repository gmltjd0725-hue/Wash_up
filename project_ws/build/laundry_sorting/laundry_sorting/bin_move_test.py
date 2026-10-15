#!/usr/bin/env python3

import sys
import time
import rclpy

from onrobot_rg_msgs.srv import SetCommand


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
# =========================================================

BIN_MOVE_VEL = 50.0
BIN_MOVE_ACC = 50.0


# =========================================================
# RG2
# =========================================================

def rg2_open(node, client):

    if not client.wait_for_service(timeout_sec=3.0):
        raise RuntimeError("/onrobot/sendCommand unavailable")

    req = SetCommand.Request()
    req.command = "o"

    future = client.call_async(req)

    rclpy.spin_until_future_complete(
        node,
        future,
        timeout_sec=5.0
    )

    result = future.result()

    if result is None:
        raise RuntimeError("RG2 response timeout")

    if not result.success:
        raise RuntimeError(result.message)

    time.sleep(1.0)


# =========================================================
# MAIN
# =========================================================

def main(args=None):

    if len(sys.argv) < 2:

        print("")
        print("사용법:")
        print("ros2 run laundry_sorting bin_move_test LIGHT")
        print("ros2 run laundry_sorting bin_move_test DARK")
        print("")

        return


    laundry_type = sys.argv[1].upper()


    rclpy.init(args=args)


    node = rclpy.create_node(
        "bin_move_test",
        namespace=ROBOT_ID
    )


    DR_init.__dsr__node = node


    from DSR_ROBOT2 import (
        posj,
        movej
    )


    from laundry_sorting.bin_positions.light_bin_a import (
        BIN_A_DROP_JOINT
    )

    from laundry_sorting.bin_positions.dark_bin_b import (
        BIN_B_DROP_JOINT
    )


    HOME = posj(*HOME_JOINT)


    if laundry_type == "LIGHT":

        target_name = "LIGHT BIN_A"
        target_joint = BIN_A_DROP_JOINT


    elif laundry_type == "DARK":

        target_name = "DARK BIN_B"
        target_joint = BIN_B_DROP_JOINT


    else:

        print("ERROR: LIGHT 또는 DARK만 입력")

        node.destroy_node()
        rclpy.shutdown()

        return


    TARGET = posj(
        *target_joint
    )


    rg2_client = node.create_client(
        SetCommand,
        "/onrobot/sendCommand"
    )


    # =====================================================
    # 1. HOME
    # =====================================================

    print("")
    print("========================================")
    print("[1] MOVE HOME")
    print("========================================")


    movej(
        HOME,
        v=BIN_MOVE_VEL,
        a=BIN_MOVE_ACC
    )


    # =====================================================
    # 2. BIN으로 한 번에 이동
    # =====================================================

    print("")
    print("========================================")
    print("[2] MOVE TO", target_name)
    print("========================================")


    movej(
        TARGET,
        v=BIN_MOVE_VEL,
        a=BIN_MOVE_ACC
    )


    # =====================================================
    # 3. RG2 OPEN
    # =====================================================

    print("")
    print("========================================")
    print("[3] RG2 OPEN")
    print("========================================")


    rg2_open(
        node,
        rg2_client
    )


    # =====================================================
    # 4. HOME으로 한 번에 복귀
    # =====================================================

    print("")
    print("========================================")
    print("[4] RETURN HOME")
    print("========================================")


    movej(
        HOME,
        v=BIN_MOVE_VEL,
        a=BIN_MOVE_ACC
    )


    print("")
    print("========================================")
    print("BIN MOVE TEST SUCCESS")
    print("TYPE =", laundry_type)
    print("========================================")


    node.destroy_node()

    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
