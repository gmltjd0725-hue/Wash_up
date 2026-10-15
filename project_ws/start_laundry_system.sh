#!/usr/bin/env bash

source /opt/ros/jazzy/setup.bash
source ~/ws_cobot_pjt/ws_dsr/install/setup.bash
source ~/project_ws/install/setup.bash

# ============================================================
# DATABASE
# ============================================================

export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=laundry_db
export DB_USER=postgres

if [ -z "$DB_PASSWORD" ]; then
    read -s -p "DB_PASSWORD 입력: " DB_PASSWORD
    echo
    export DB_PASSWORD
fi

echo "[CHECK] DB 연결 확인..."

if ! PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -tAc "SELECT 1;" >/dev/null 2>&1
then
    echo "[ERROR] DB 연결 실패"
    exit 1
fi

echo "[OK] DB 연결 성공"


PIDS=()


node_exists()
{
    ros2 node list 2>/dev/null | grep -qx "$1"
}


start_node()
{
    LABEL="$1"
    NODE="$2"
    DELAY="$3"

    shift 3

    if node_exists "$NODE"; then
        echo "[SKIP] $LABEL 이미 실행 중"
        return
    fi

    echo
    echo "========================================"
    echo "[START] $LABEL"
    echo "========================================"

    setsid "$@" &
    PIDS+=("$!")

    sleep "$DELAY"
}


cleanup()
{
    trap - INT TERM EXIT

    echo
    echo "========================================"
    echo "[SYSTEM] 이번 스크립트가 실행한 노드 종료"
    echo "========================================"

    for PID in "${PIDS[@]}"; do
        kill -INT -- "-$PID" 2>/dev/null || true
    done

    sleep 1

    for PID in "${PIDS[@]}"; do
        kill -TERM -- "-$PID" 2>/dev/null || true
    done

    wait 2>/dev/null || true

    echo "[SYSTEM] 종료 완료"
}

trap cleanup INT TERM EXIT


# ============================================================
# 1. ROBOT BRINGUP
# ============================================================

if node_exists "/dsr01/controller_manager"; then

    echo "[SKIP] M0609 REAL BRINGUP 이미 실행 중"

else

    echo
    echo "========================================"
    echo "[START] 1. M0609 REAL BRINGUP"
    echo "========================================"

    setsid ros2 launch m0609_rg2_bringup bringup.launch.py \
        mode:=real \
        host:=192.168.1.100 \
        model:=m0609 &

    PIDS+=("$!")

    sleep 5

    echo
    echo "TP에서 제어권을 승인하세요."
    read -p "제어권 승인 완료 후 Enter: "

fi


# ============================================================
# 2. WEBCAM
# ============================================================

start_node \
"2. WEBCAM" \
"/webcam_publisher" \
3 \
ros2 run laundry_sorting webcam_publisher


# ============================================================
# 3. BIN COLOR
# ============================================================

start_node \
"3. BIN COLOR" \
"/bin_color_publisher" \
2 \
ros2 run laundry_sorting bin_color_publisher


# ============================================================
# 4. LAUNDRY DETECTION
# ============================================================

echo
echo "※ Laundry Detection 신규 실행 시 카메라 앞을 비워주세요."

start_node \
"4. LAUNDRY DETECTION" \
"/laundry_detection_publisher" \
3 \
ros2 run laundry_sorting laundry_detection_publisher


# ============================================================
# 5. CONTROLLER
# ============================================================

start_node \
"5. LAUNDRY CONTROLLER" \
"/laundry_controller" \
2 \
ros2 run laundry_sorting laundry_controller


# ============================================================
# 6. BIN OCR + COLOR REGISTER
# ============================================================

start_node \
"6. BIN OCR + COLOR REGISTER" \
"/bin_ocr_publisher" \
3 \
ros2 run laundry_sorting bin_ocr_publisher


# ============================================================
# 7. VOICE
# ============================================================

start_node \
"7. VOICE" \
"/voice_node" \
1 \
ros2 run voice_processing voice_node


# ============================================================
# 8. VIEWER - 선택사항
# ============================================================

if [ "$1" = "--viewer" ]; then

    start_node \
    "8. BIN OCR VIEWER" \
    "/bin_ocr_viewer" \
1 \
    ros2 run laundry_sorting bin_ocr_viewer

fi


echo
echo "========================================"
echo " LAUNDRY VLA SYSTEM READY"
echo "========================================"
echo
echo "호출어 : 야"
echo "명령어 : 밝은 빨래와 어두운 빨래를 구분해줘"
echo
echo "종료    : Ctrl+C"
echo

wait
