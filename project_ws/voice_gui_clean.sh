#!/bin/bash

source /opt/ros/jazzy/setup.bash
source ~/project_ws/install/setup.bash

stdbuf -oL -eL \
ros2 launch laundry_sorting vl_system.launch.py gui:=true 2>&1 \
| grep --line-buffered -E \
"Webcam Publisher 시작|선택된 카메라|BIN OCR \+ COLOR Publisher 시작|BIN A/B \+ 실제 색상 검증 시작|BIN OCR \+ COLOR Viewer 시작|RULE:|BIN 등록: BIN_A|BIN 등록: BIN_B|BIN 확인 보강:|BIN_A REASON|BIN_B REASON|BIN_A / BIN_B 등록 완료|BIN OCR \+ COLOR 완료|Laundry Detection Publisher 시작|초기 배경 저장 중|배경 저장 완료|'야' 대기 중|STT 결과: 밝은 빨래|Intent: SORT_LAUNDRY|STATE ->|Classification =|Required BIN =|OCR Detected BINs =|BIN OCR Match =|Destination =|ERROR|Traceback|process has died"
