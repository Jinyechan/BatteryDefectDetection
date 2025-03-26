from flask import Flask, request, jsonify, render_template
from flask_mysqldb import MySQL
from ultralytics import YOLO
import cv2
import numpy as np
from PIL import Image
import io
import base64
import os
from datetime import datetime

app = Flask(__name__)

# MySQL 설정 (로컬 환경)
app.config['MYSQL_HOST'] = 'localhost'  # 로컬 MySQL
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'battery_defect_detection'

mysql = MySQL(app)

# YOLO 모델 로드
model = YOLO('best.pt')

# 이미지 저장 디렉토리 설정
IMAGE_SAVE_PATH = 'static/images/'
if not os.path.exists(IMAGE_SAVE_PATH):
    os.makedirs(IMAGE_SAVE_PATH)

# 스크롤 상태 저장 (간단하게 전역 변수로 관리, 나중에 DB로 확장 가능)
scroll_state = {"action": "resume"}  # 기본: 스크롤 재개 상태

# 기존 app.py의 라우트들 (예: /monitoring, /login 등)이 있다고 가정
# 여기에 추가

# ESP32-CAM에서 이미지 수신 및 YOLO 처리
@app.route('/detect', methods=['POST'])
def detect_battery():
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({"error": "이미지가 없습니다."}), 400

        # Base64 이미지 디코딩
        base64_image = data['image']
        image_data = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_data))
        
        # PIL 이미지를 OpenCV 형식으로 변환
        image_np = np.array(image)
        image_cv = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

        # YOLO 모델로 건전지 인식
        results = model(image_cv)
        detected = False
        confidence = 0.0
        for result in results:
            for box in result.boxes:
                if box.cls == 0:  # 클래스 0이 건전지
                    detected = True
                    confidence = float(box.conf)
                    break
            if detected:
                break

        # 이미지 파일로 저장
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_filename = f"battery_{timestamp}.jpg"
        image_path = os.path.join(IMAGE_SAVE_PATH, image_filename)
        cv2.imwrite(image_path, image_cv)

        # 불량 점수 계산
        faulty_score = int(confidence * 100)

        # DB에 저장
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO faulty_log (lineIdx, faultyScore, faultyImage, logDate, removed)
            VALUES (%s, %s, %s, %s, %s)
        """, (1, faulty_score, image_filename, datetime.now(), 0))
        mysql.connection.commit()
        cursor.close()

        # 스크롤 상태 업데이트
        if detected and confidence > 0.5:
            scroll_state['action'] = 'pause'
        else:
            scroll_state['action'] = 'resume'

        return jsonify({
            "detected": detected,
            "confidence": confidence,
            "faulty_score": faulty_score,
            "image_path": image_filename,
            "scroll_action": scroll_state['action']
        }), 200

    except Exception as e:
        print("에러 발생:", str(e))  # 에러 메시지 출력 추가
        return jsonify({"error": str(e)}), 500

# 웹사이트에서 결과 조회 (HTTP 폴링용)
@app.route('/result', methods=['GET'])
def get_result():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT faultyIdx, lineIdx, faultyScore, faultyImage, logDate
            FROM faulty_log
            WHERE removed = 0
            ORDER BY logDate DESC
            LIMIT 1
        """)
        result = cursor.fetchone()
        cursor.close()

        if result:
            return jsonify({
                "faulty_id": result[0],
                "line_id": result[1],
                "faulty_score": result[2],
                "image_path": result[3],
                "log_date": result[4].strftime('%Y.%m.%d %H:%M:%S'),
                "scroll_action": scroll_state['action']
            }), 200
        else:
            return jsonify({"error": "데이터 없음"}), 404

    except Exception as e:
        print("에러 발생:", str(e))
        return jsonify({"error": str(e)}), 500

# 스크롤 제어 (웹사이트에서 호출)
@app.route('/scroll/control', methods=['POST'])
def scroll_control():
    try:
        data = request.get_json()
        if not data or 'action' not in data:
            return jsonify({"error": "액션이 없습니다."}), 400

        action = data['action']
        if action not in ['pause', 'resume']:
            return jsonify({"error": "잘못된 액션입니다."}), 400

        scroll_state['action'] = action
        return jsonify({"status": "success", "action": scroll_state['action']}), 200

    except Exception as e:
        print("에러 발생:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)