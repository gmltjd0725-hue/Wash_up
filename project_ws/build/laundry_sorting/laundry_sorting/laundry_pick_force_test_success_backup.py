#!/usr/bin/env python3

import time
import statistics
import rclpy

from onrobot_rg_msgs.srv import SetCommand


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
# 1차 빠른 하강
#
# 81.25mm까지는 5mm씩
# =========================================================

COARSE_DESCENT_STEP = 5.0
COARSE_DESCENT_VEL = 50.0
COARSE_DESCENT_ACC = 80.0


# =========================================================
# 푹신한 빨래 접촉 구간
#
# 81.25mm부터 1mm씩
# =========================================================

FINE_DESCENT_START_Z = 81.25

FINE_DESCENT_STEP = 1.0
FINE_DESCENT_VEL = 15.0
FINE_DESCENT_ACC = 30.0


# =========================================================
# SOFT CONTACT
#
# 81.25mm에서 Fz 기준값을 새로 잡는다.
#
# 이후 기준값보다 1N 이상 변화하면
# 빨래 접촉 의심.
#
# 같은 위치에서 다시 측정해서
# 계속 1N 이상이면 실제 접촉 인정.
# =========================================================

SOFT_CONTACT_DELTA = 1.0

FORCE_SAMPLE_COUNT = 5

CONTACT_SETTLE_SEC = 0.15
CONTACT_CONFIRM_SEC = 0.10


# =========================================================
# 강한 접촉 보호용
#
# 5mm 빠른 구간에서도 외력이 3N 이상이면
# 더 내려가지 않는다.
# =========================================================

HARD_CONTACT_FORCE = 3.0


# =========================================================
# HOME 상승
# =========================================================

LIFT_VEL = 50.0
LIFT_ACC = 50.0


# =========================================================
# RG2
# =========================================================

def rg2_command(node, client, command):

    if not client.wait_for_service(timeout_sec=3.0):

        raise RuntimeError(
            "/onrobot/sendCommand unavailable"
        )


    request = SetCommand.Request()

    request.command = command


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
            f"RG2 failed: {result.message}"
        )


    time.sleep(1.0)



def rg2_open(node, client):

    print("")
    print("[RG2] OPEN")

    rg2_command(
        node,
        client,
        "o"
    )



def rg2_close(node, client):

    print("")
    print("[RG2] CLOSE")

    rg2_command(
        node,
        client,
        "c"
    )


# =========================================================
# 안정된 Fz 읽기
# =========================================================

def read_fz(get_tool_force, DR_BASE):

    values = []


    for _ in range(FORCE_SAMPLE_COUNT):

        force = get_tool_force(
            DR_BASE
        )


        values.append(
            float(force[2])
        )


        time.sleep(
            0.02
        )


    return statistics.median(
        values
    )


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

        set_ref_coord,

        get_current_posx,
        get_tool_force,

        check_force_condition,

        DR_AXIS_Z,
        DR_BASE,
        DR_MV_MOD_REL

    )


    HOME = posj(
        *HOME_JOINT
    )


    rg2_client = node.create_client(
        SetCommand,
        "/onrobot/sendCommand"
    )


    contact_detected = False

    contact_pos = None

    fine_baseline_fz = None


    # =====================================================
    # 1. HOME
    # =====================================================

    print("")
    print("========================================")
    print("[1] MOVE HOME")
    print("========================================")


    movej(
        HOME,
        v=30,
        a=30
    )


    # =====================================================
    # 2. RG2 OPEN
    # =====================================================

    print("")
    print("========================================")
    print("[2] RG2 OPEN")
    print("========================================")


    rg2_open(
        node,
        rg2_client
    )


    # =====================================================
    # 3. BASE
    # =====================================================

    set_ref_coord(
        DR_BASE
    )


    # =====================================================
    # 4. HOME TCP 저장
    # =====================================================

    start_pos, sol = get_current_posx(
        ref=DR_BASE
    )


    print("")
    print(
        "HOME TCP =",
        start_pos
    )


    print(
        "HOME Z = %.2f mm"
        % float(start_pos[2])
    )


    # =====================================================
    # 5. SEARCH
    # =====================================================

    print("")
    print("========================================")
    print("[3] SEARCH LAUNDRY")
    print("")
    print("Z > 81.25 mm")
    print("  -> 5mm DESCENT")
    print("")
    print("Z <= 81.25 mm")
    print("  -> 1mm SOFT DESCENT")
    print("  -> Fz SOFT CONTACT")
    print("")
    print("RG2 = OPEN")
    print("========================================")


    while rclpy.ok():


        current_pos, sol = get_current_posx(
            ref=DR_BASE
        )


        current_z = float(
            current_pos[2]
        )


        # =================================================
        # A. 빠른 접근 구간
        #
        # 81.25mm까지 5mm씩
        # =================================================

        if current_z > FINE_DESCENT_START_Z:


            # ---------------------------------------------
            # 81.25를 지나쳐 버리지 않도록
            # 마지막 이동량만 자동 조절
            # ---------------------------------------------

            distance_to_fine = (
                current_z
                - FINE_DESCENT_START_Z
            )


            down_step = min(
                COARSE_DESCENT_STEP,
                distance_to_fine
            )


            print("")
            print(
                "[COARSE] Current Z = %.2f mm"
                % current_z
            )


            print(
                "[COARSE] DOWN      = %.2f mm"
                % down_step
            )


            movel(
                [
                    0.0,
                    0.0,
                    -down_step,
                    0.0,
                    0.0,
                    0.0
                ],
                v=COARSE_DESCENT_VEL,
                a=COARSE_DESCENT_ACC,
                ref=DR_BASE,
                mod=DR_MV_MOD_REL
            )


            time.sleep(
                CONTACT_SETTLE_SEC
            )


            current_pos, sol = get_current_posx(
                ref=DR_BASE
            )


            current_z = float(
                current_pos[2]
            )


            print(
                "[COARSE] After Z   = %.2f mm"
                % current_z
            )


            # ---------------------------------------------
            # 빠른 구간에서도 강한 접촉이 발생하면
            # 추가 하강하지 않는다.
            # ---------------------------------------------

            hard_contact = check_force_condition(
                DR_AXIS_Z,
                min=HARD_CONTACT_FORCE,
                ref=DR_BASE
            )


            if hard_contact == 0:


                contact_detected = True


                contact_pos = current_pos


                print("")
                print("========================================")
                print("CONTACT DETECTED DURING COARSE DESCENT")
                print("STOP DESCENT")
                print(
                    "CONTACT Z = %.2f mm"
                    % current_z
                )
                print("========================================")


                break


            continue


        # =================================================
        # B. SOFT CONTACT 구간
        #
        # 81.25mm 이하
        # 1mm씩 천천히
        # =================================================


        # ---------------------------------------------
        # 81.25mm에 처음 들어왔을 때
        # 이 위치의 Fz를 새 기준값으로 저장
        # ---------------------------------------------

        if fine_baseline_fz is None:


            time.sleep(
                0.2
            )


            fine_baseline_fz = read_fz(
                get_tool_force,
                DR_BASE
            )


            print("")
            print("========================================")
            print("FINE DESCENT START")
            print(
                "START Z = %.2f mm"
                % current_z
            )
            print(
                "FINE BASELINE Fz = %.2f N"
                % fine_baseline_fz
            )
            print("STEP = 1.00 mm")
            print("========================================")


        # ---------------------------------------------
        # 1mm 하강
        # ---------------------------------------------

        print("")
        print(
            "[FINE] Current Z = %.2f mm"
            % current_z
        )


        print(
            "[FINE] DOWN      = %.2f mm"
            % FINE_DESCENT_STEP
        )


        movel(
            [
                0.0,
                0.0,
                -FINE_DESCENT_STEP,
                0.0,
                0.0,
                0.0
            ],
            v=FINE_DESCENT_VEL,
            a=FINE_DESCENT_ACC,
            ref=DR_BASE,
            mod=DR_MV_MOD_REL
        )


        # ---------------------------------------------
        # 이동 후 안정화
        # ---------------------------------------------

        time.sleep(
            CONTACT_SETTLE_SEC
        )


        current_pos, sol = get_current_posx(
            ref=DR_BASE
        )


        current_z = float(
            current_pos[2]
        )


        # ---------------------------------------------
        # 현재 Fz
        # ---------------------------------------------

        current_fz = read_fz(
            get_tool_force,
            DR_BASE
        )


        force_delta = abs(
            current_fz
            - fine_baseline_fz
        )


        print(
            "[FINE] After Z   = %.2f mm"
            % current_z
        )


        print(
            "[FINE] Fz        = %.2f N"
            % current_fz
        )


        print(
            "[FINE] Delta     = %.2f N"
            % force_delta
        )


        # =================================================
        # 접촉 의심
        # =================================================

        if force_delta >= SOFT_CONTACT_DELTA:


            print("")
            print(
                "[FINE] SOFT CONTACT CANDIDATE"
            )


            # ---------------------------------------------
            # 더 내려가지 않고
            # 같은 위치에서 다시 한번 확인
            # ---------------------------------------------

            time.sleep(
                CONTACT_CONFIRM_SEC
            )


            confirm_fz = read_fz(
                get_tool_force,
                DR_BASE
            )


            confirm_delta = abs(
                confirm_fz
                - fine_baseline_fz
            )


            print(
                "[FINE] CONFIRM Fz    = %.2f N"
                % confirm_fz
            )


            print(
                "[FINE] CONFIRM Delta = %.2f N"
                % confirm_delta
            )


            # =================================================
            # 실제 빨래 접촉 확정
            # =================================================

            if confirm_delta >= SOFT_CONTACT_DELTA:


                contact_detected = True


                contact_pos, sol = get_current_posx(
                    ref=DR_BASE
                )


                print("")
                print("========================================")
                print("LAUNDRY CONTACT DETECTED")
                print("STOP DESCENT")
                print(
                    "Laundry Z = %.2f mm"
                    % float(contact_pos[2])
                )
                print(
                    "Force Delta = %.2f N"
                    % confirm_delta
                )
                print("========================================")


                break


            else:


                print(
                    "[FINE] FALSE CONTACT -> CONTINUE"
                )


    # =====================================================
    # 6. 접촉 후 RG2 CLOSE
    # =====================================================

    if contact_detected:


        print("")
        print("========================================")
        print("[4] RG2 CLOSE")
        print("========================================")


        rg2_close(
            node,
            rg2_client
        )


        time.sleep(
            0.5
        )


        # =================================================
        # 7. 빨래를 들고 HOME TCP 상승
        # =================================================

        print("")
        print("========================================")
        print("[5] LIFT TO HOME")
        print("========================================")


        movel(
            start_pos,
            v=LIFT_VEL,
            a=LIFT_ACC,
            ref=DR_BASE
        )


        # =================================================
        # 8. 정확한 HOME
        # =================================================

        print("")
        print("========================================")
        print("[6] RETURN HOME")
        print("========================================")


        movej(
            HOME,
            v=30,
            a=30
        )


        print("")
        print("========================================")
        print("PICK SUCCESS")
        print("========================================")


        print(
            "Laundry Contact Z = %.2f mm"
            % float(contact_pos[2])
        )


        print(
            "RG2 = CLOSED"
        )


        print(
            "ROBOT = HOME"
        )


    node.destroy_node()


    if rclpy.ok():

        rclpy.shutdown()



if __name__ == "__main__":

    main()
