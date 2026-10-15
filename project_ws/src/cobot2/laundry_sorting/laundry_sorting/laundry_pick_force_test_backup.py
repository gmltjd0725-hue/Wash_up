#!/usr/bin/env python3

import time
import statistics
import rclpy

from onrobot_rg_msgs.srv import SetCommand


# =========================================================
# DOOSAN ROBOT 설정
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
# 실제 측정한 PICK 최저 안전 TCP Z
# =========================================================

PICK_BOTTOM_Z = 133.052


# =========================================================
# 하강 설정
#
# 접촉 전에는 힘제어/순응제어를 사용하지 않는다.
# 실제 movel로 아래쪽으로 이동한다.
# =========================================================

DESCENT_STEP = 5.0       # 한 번에 5mm
DESCENT_VEL = 60.0       # mm/s
DESCENT_ACC = 80.0


# =========================================================
# 빨래 접촉 판정
#
# 절대 Fz=3N이 아니라
# HOME 기준 Fz에서 3N 이상 변화했는지 검사
# =========================================================

CONTACT_DELTA_FORCE = 3.0

# movel 직후 순간적인 힘 변화는 접촉으로 보지 않는다.
FORCE_SETTLE_SEC = 0.20

# 실제 접촉은 연속 3회 확인되어야 인정
CONTACT_CONFIRM_COUNT = 3


# =========================================================
# 접촉 후 힘 / 순응제어
# =========================================================

FORCE_Z = 10.0

JIGGLE_MM = 0.5
JIGGLE_REPEAT = 2


# =========================================================
# 일반 이동
# =========================================================

JOINT_VEL = 30.0
JOINT_ACC = 30.0

LIFT_VEL = 50.0
LIFT_ACC = 50.0


# =========================================================
# RG2
# =========================================================

def rg2_command(node, client, command):

    if not client.wait_for_service(timeout_sec=3.0):
        raise RuntimeError(
            "/onrobot/sendCommand service unavailable"
        )

    req = SetCommand.Request()
    req.command = command

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
        raise RuntimeError(
            f"RG2 command failed: {result.message}"
        )

    time.sleep(1.0)


def rg2_open(node, client):

    print("\n[RG2] OPEN")
    rg2_command(node, client, "o")


def rg2_close(node, client):

    print("\n[RG2] CLOSE")
    rg2_command(node, client, "c")


# =========================================================
# Fz 안정값 읽기
# =========================================================

def read_stable_fz(get_tool_force, DR_BASE):

    values = []

    for _ in range(5):

        force = get_tool_force(
            DR_BASE
        )

        values.append(
            float(force[2])
        )

        time.sleep(0.02)

    # 순간 튀는 값 때문에 오판하지 않도록 median 사용
    return statistics.median(values)


# =========================================================
# MAIN
# =========================================================

def main(args=None):

    rclpy.init(args=args)

    node = rclpy.create_node(
        "laundry_pick_force_test",
        namespace=ROBOT_ID
    )

    DR_init.__dsr__node = node


    from DSR_ROBOT2 import (

        posj,

        movej,
        movel,
        move_periodic,

        set_ref_coord,

        task_compliance_ctrl,
        set_desired_force,

        release_force,
        release_compliance_ctrl,

        get_current_posx,
        get_tool_force,

        DR_BASE,
        DR_FC_MOD_REL,
        DR_MV_MOD_REL
    )


    HOME = posj(
        *HOME_JOINT
    )


    rg2_client = node.create_client(
        SetCommand,
        "/onrobot/sendCommand"
    )


    start_pos = None
    contact_pos = None

    contact_detected = False

    compliance_active = False
    force_active = False


    try:

        # =================================================
        # 1. HOME
        # =================================================

        print("\n========================================")
        print("[1] MOVE HOME")
        print("========================================")

        movej(
            HOME,
            v=JOINT_VEL,
            a=JOINT_ACC
        )


        # =================================================
        # 2. RG2 OPEN
        # =================================================

        print("\n========================================")
        print("[2] RG2 OPEN")
        print("========================================")

        rg2_open(
            node,
            rg2_client
        )


        # =================================================
        # 3. BASE 좌표계
        # =================================================

        set_ref_coord(
            DR_BASE
        )


        # =================================================
        # 4. HOME TCP 저장
        # =================================================

        start_pos, sol = get_current_posx(
            ref=DR_BASE
        )

        print(
            "\nHOME TCP =",
            start_pos
        )

        print(
            "HOME Z =",
            start_pos[2]
        )

        print(
            "PICK_BOTTOM_Z =",
            PICK_BOTTOM_Z
        )


        # =================================================
        # 5. HOME에서 힘 기준값 측정
        #
        # 아직 힘제어 OFF
        # 아직 순응제어 OFF
        # RG2 OPEN 상태
        # =================================================

        baseline_fz = read_stable_fz(
            get_tool_force,
            DR_BASE
        )

        print(
            "\nBASELINE Fz = %.2f N"
            % baseline_fz
        )


        # =================================================
        # 6. 빨래를 향해 빠르게 하강
        #
        # 중요:
        # 여기서는 힘제어 OFF
        # 순응제어 OFF
        # RG2 OPEN
        #
        # 위아래 깔짝거리지 않는다.
        # 계속 아래로만 내려간다.
        # =================================================

        print("\n========================================")
        print("[3] DESCEND TO LAUNDRY")
        print("RG2 = OPEN")
        print("FORCE CONTROL = OFF")
        print("COMPLIANCE = OFF")
        print("========================================")


        while rclpy.ok():

            current_pos, sol = get_current_posx(
                ref=DR_BASE
            )

            current_z = float(
                current_pos[2]
            )


            # ---------------------------------------------
            # 현재 안정 Fz 측정
            # ---------------------------------------------

            # ---------------------------------------------
            # 이동 직후의 관성/진동이 가라앉은 다음 측정
            # ---------------------------------------------

            time.sleep(FORCE_SETTLE_SEC)

            confirm_count = 0
            force_delta = 0.0
            current_fz = baseline_fz

            for _ in range(CONTACT_CONFIRM_COUNT):

                current_fz = read_stable_fz(
                    get_tool_force,
                    DR_BASE
                )

                force_delta = abs(
                    current_fz - baseline_fz
                )

                print(
                    "Z=%.2f mm | Fz=%.2f N | delta=%.2f N"
                    % (
                        current_z,
                        current_fz,
                        force_delta
                    )
                )

                if force_delta >= CONTACT_DELTA_FORCE:
                    confirm_count += 1
                else:
                    confirm_count = 0

                time.sleep(0.05)


            # =============================================
            # 실제 빨래 접촉
            #
            # 3N 이상 변화가 연속 3회일 때만 인정
            # =============================================

            if confirm_count >= CONTACT_CONFIRM_COUNT:

                contact_detected = True

                contact_pos, sol = get_current_posx(
                    ref=DR_BASE
                )

                print("")
                print("========================================")
                print("LAUNDRY CONTACT DETECTED")
                print("========================================")

                print(
                    "CONTACT Z =",
                    contact_pos[2]
                )

                print(
                    "FORCE DELTA =",
                    force_delta,
                    "N"
                )

                print("========================================")

                break


            # =============================================
            # 빨래 없음 / 최저 안전 높이
            # =============================================

            if current_z <= PICK_BOTTOM_Z:

                print("")
                print("========================================")
                print("NO LAUNDRY")
                print("PICK_BOTTOM_Z REACHED")
                print("========================================")

                break


            # =============================================
            # 다음 하강
            # =============================================

            remaining = (
                current_z
                - PICK_BOTTOM_Z
            )

            down_step = min(
                DESCENT_STEP,
                remaining
            )


            if down_step <= 0.0:
                break


            movel(
                [
                    0.0,
                    0.0,
                    -down_step,
                    0.0,
                    0.0,
                    0.0
                ],
                v=DESCENT_VEL,
                a=DESCENT_ACC,
                ref=DR_BASE,
                mod=DR_MV_MOD_REL
            )


        # =================================================
        # 7. 실제 접촉한 경우에만
        #    이제 힘/순응제어 시작
        # =================================================

        if contact_detected:

            print("\n========================================")
            print("[4] COMPLIANCE CONTROL ON")
            print("========================================")


            result = task_compliance_ctrl(
                stx=[
                    3000.0,
                    3000.0,
                    100.0,
                    200.0,
                    200.0,
                    200.0
                ]
            )


            if result != 0:
                raise RuntimeError(
                    "task_compliance_ctrl failed"
                )


            compliance_active = True


            # =================================================
            # 8. 접촉 위치에서 10N 힘제어
            # =================================================

            print("\n========================================")
            print("[5] FORCE CONTROL ON")
            print("TARGET FORCE =", FORCE_Z, "N")
            print("========================================")


            result = set_desired_force(

                fd=[
                    0.0,
                    0.0,
                    -FORCE_Z,
                    0.0,
                    0.0,
                    0.0
                ],

                dir=[
                    0,
                    0,
                    1,
                    0,
                    0,
                    0
                ],

                time=0.0,

                mod=DR_FC_MOD_REL
            )


            if result != 0:
                raise RuntimeError(
                    "set_desired_force failed"
                )


            force_active = True


            # 힘이 자리잡을 시간
            time.sleep(0.2)


            # =================================================
            # 9. 접촉한 위치에서만 깔짝깔짝
            #
            # 빨래 찾기 전에는 절대 깔짝거리지 않는다.
            # RG2는 계속 OPEN
            # =================================================

            print("\n========================================")
            print("[6] CONTACT JIGGLE")
            print("RG2 = OPEN")
            print("========================================")


            move_periodic(

                amp=[
                    0.0,
                    0.0,
                    JIGGLE_MM,
                    0.0,
                    0.0,
                    0.0
                ],

                period=0.4,

                atime=0.1,

                repeat=JIGGLE_REPEAT,

                ref=DR_BASE
            )


            time.sleep(0.2)


    finally:

        # =================================================
        # 힘/순응제어는 무조건 해제
        # =================================================

        if force_active:

            print("\n[7] FORCE CONTROL OFF")

            try:
                release_force()

            except Exception as e:
                print(
                    "release_force error:",
                    e
                )


        time.sleep(0.2)


        if compliance_active:

            print("[8] COMPLIANCE CONTROL OFF")

            try:
                release_compliance_ctrl()

            except Exception as e:
                print(
                    "release_compliance_ctrl error:",
                    e
                )


    # =====================================================
    # 10. 실제 접촉 성공한 경우에만 RG2 CLOSE
    # =====================================================

    if contact_detected:

        print("\n========================================")
        print("[9] RG2 CLOSE")
        print("========================================")

        rg2_close(
            node,
            rg2_client
        )


        # =================================================
        # 11. 빨래 들어올리기
        # =================================================

        print("\n========================================")
        print("[10] LIFT LAUNDRY")
        print("========================================")


        movel(
            start_pos,
            v=LIFT_VEL,
            a=LIFT_ACC,
            ref=DR_BASE
        )


        # =================================================
        # 12. HOME
        # =================================================

        print("\n========================================")
        print("[11] RETURN HOME")
        print("========================================")


        movej(
            HOME,
            v=JOINT_VEL,
            a=JOINT_ACC
        )


        print("")
        print("========================================")
        print("PICK SUCCESS")
        print("========================================")

        print(
            "Laundry Height Z =",
            contact_pos[2]
        )


    # =====================================================
    # 빨래 없음
    # =====================================================

    else:

        print("")
        print("========================================")
        print("PICK FAILED")
        print("NO LAUNDRY CONTACT")
        print("========================================")

        # RG2 CLOSE 안 함


        if start_pos is not None:

            print(
                "\nRETURN TO HOME HEIGHT"
            )

            movel(
                start_pos,
                v=LIFT_VEL,
                a=LIFT_ACC,
                ref=DR_BASE
            )


        movej(
            HOME,
            v=JOINT_VEL,
            a=JOINT_ACC
        )


    node.destroy_node()

    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
