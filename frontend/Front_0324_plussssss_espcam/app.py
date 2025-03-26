from flask import Flask, render_template, flash, request, redirect, url_for, session, jsonify, Response, send_from_directory
from flask_mysqldb import MySQL
from models import DBManager
from argon2 import PasswordHasher
import pandas as pd
import base64
from io import BytesIO
import io
from PIL import Image
import numpy as np
import cv2
from keras.models import load_model
import os
import time
import socket
from ultralytics import YOLO
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL 설정 (로컬 환경)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '1234'
app.config['MYSQL_DB'] = 'battery_defect_detection'

mysql = MySQL(app)

# YOLO 모델 로드
model_yolo = YOLO('best.pt')

# CNN 및 U-Net 모델 로드 (현재 사용하지 않음)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH_MAIN = os.path.join(BASE_DIR, "static", "fine_tuned_unet_mobilenet_alpha08.h5")
MODEL_PATH_SECONDARY = os.path.join(BASE_DIR, "static", "model_final.h5")
# model_main = load_model(MODEL_PATH_MAIN, compile=False)  # U-Net
# model_secondary = load_model(MODEL_PATH_SECONDARY, compile=False)  # CNN

# 이미지 저장 디렉토리 설정
IMAGE_SAVE_PATH = 'static/images/'
if not os.path.exists(IMAGE_SAVE_PATH):
    os.makedirs(IMAGE_SAVE_PATH)

# 스크롤 상태 저장
scroll_state = {"action": "resume"}

@app.before_request
def auto_login_for_dev():
    if not session.get('userid'):
        session['userid'] = 'admin123'
        session['username'] = '김관리자'
        session['userLevel'] = 1000

manager = DBManager()
ph = PasswordHasher()

# ESP32Cam 스트림 URL
ESP32CAM_STREAM_URL = "http://10.0.66.13:81/stream"

# 이미지 관리: 최대 10개만 유지
def manage_images():
    image_files = [f for f in os.listdir(IMAGE_SAVE_PATH) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if len(image_files) > 10:
        image_files.sort(key=lambda x: os.path.getmtime(os.path.join(IMAGE_SAVE_PATH, x)))
        for old_file in image_files[:-10]:
            os.remove(os.path.join(IMAGE_SAVE_PATH, old_file))
            print(f"삭제된 이미지: {old_file}")

# 최신 이미지 경로 반환
@app.route('/latest_image', methods=['GET'])
def latest_image():
    try:
        image_dir = IMAGE_SAVE_PATH
        image_files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if not image_files:
            return jsonify({"error": "static/images/ 폴더에 이미지가 없습니다."}), 404

        latest_image = max(image_files, key=lambda x: os.path.getmtime(os.path.join(image_dir, x)))
        return jsonify({"image_path": f"/static/images/{latest_image}"}), 200
    except Exception as e:
        print("최신 이미지 가져오기 에러:", str(e))
        return jsonify({"error": str(e)}), 500

# 간단한 이미지 처리로 불량 검출 (녹색/적색/갈색 영역 감지)
def detect_defect_by_color(image):
    img = cv2.imdecode(np.frombuffer(image.read(), np.uint8), cv2.IMREAD_COLOR)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # 녹색/적색(녹) 영역 감지
    lower_red = np.array([0, 120, 70])
    upper_red = np.array([10, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red, upper_red)
    
    lower_red2 = np.array([170, 120, 70])
    upper_red2 = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    
    # 갈색(녹) 영역 감지
    lower_brown = np.array([10, 100, 20])
    upper_brown = np.array([20, 255, 200])
    mask3 = cv2.inRange(hsv, lower_brown, upper_brown)
    
    mask = mask1 + mask2 + mask3
    defect_ratio = np.sum(mask) / (img.shape[0] * img.shape[1])
    is_defective = defect_ratio > 0.01  # 임계값을 0.02에서 0.01로 낮춤
    defect_prob = defect_ratio * 100
    print(f"색상 기반 불량 검출 - is_defective: {is_defective}, defect_prob: {defect_prob}")
    return is_defective, defect_prob, mask

# 불량 위치 시각화 (색상 기반)
def visualize_defect(image, mask):
    img = cv2.imdecode(np.frombuffer(image.read(), np.uint8), cv2.IMREAD_COLOR)
    overlay = img.copy()
    overlay[mask > 0] = [0, 0, 255]  # 불량 부분을 빨간색으로 오버레이

    pil_img = Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    buf = BytesIO()
    pil_img.save(buf, format='JPEG')
    base64_str = base64.b64encode(buf.getvalue()).decode('utf-8')

    return base64_str, overlay

# 이미지 처리 함수 (YOLO → 색상 기반 불량 검출)
def process_image(image_data):
    try:
        image_data = base64.b64decode(image_data)
    except Exception as e:
        print(f"Base64 디코딩 에러: {str(e)}")
        return None

    image = Image.open(io.BytesIO(image_data))
    image_np = np.array(image)
    image_cv = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

    results = model_yolo(image_cv)
    detected = False
    confidence = 0.0
    x1, y1, x2, y2 = 0, 0, 0, 0
    for result in results:
        for box in result.boxes:
            if box.cls == 0:
                detected = True
                confidence = float(box.conf)
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                break
        if detected:
            break

    print(f"YOLO 출력 - detected: {detected}, confidence: {confidence}, bbox: ({x1}, {y1}, {x2}, {y2})")

    is_defective = False
    defect_prob = 0.0
    defect_score = 0.0
    overlay = image_cv
    base64_str = ""

    if detected and confidence > 0.5:
        # 바운딩 박스 확장
        width = x2 - x1
        height = y2 - y1
        x1 = max(0, x1 - int(width * 0.25))
        y1 = max(0, y1 - int(height * 0.25))
        x2 = min(image_cv.shape[1], x2 + int(width * 0.25))
        y2 = min(image_cv.shape[0], y2 + int(height * 0.25))

        cv2.rectangle(image_cv, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"Battery: {confidence:.2f}"
        cv2.putText(image_cv, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        _, buffer = cv2.imencode('.jpg', image_cv[y1:y2, x1:x2])
        img_io = BytesIO(buffer)
        
        # 다중 스케일 분석
        scales = [1.0, 1.5, 2.0]
        is_defective_list = []
        defect_prob_list = []
        masks = []

        for scale in scales:
            scaled_x1 = max(0, x1 - int(width * (scale - 1) / 2))
            scaled_y1 = max(0, y1 - int(height * (scale - 1) / 2))
            scaled_x2 = min(image_cv.shape[1], x2 + int(width * (scale - 1) / 2))
            scaled_y2 = min(image_cv.shape[0], y2 + int(height * (scale - 1) / 2))

            _, scaled_buffer = cv2.imencode('.jpg', image_cv[scaled_y1:scaled_y2, scaled_x1:scaled_x2])
            scaled_img_io = BytesIO(scaled_buffer)

            # 색상 기반 불량 검출
            scaled_img_io.seek(0)
            is_defective_color, defect_prob_color, mask = detect_defect_by_color(scaled_img_io)

            is_defective_list.append(is_defective_color)
            defect_prob_list.append(defect_prob_color)
            masks.append(mask)

        # 결과 조합
        is_defective = any(is_defective_list)
        defect_prob = max(defect_prob_list)
        best_mask = masks[defect_prob_list.index(defect_prob)]

        if is_defective:
            defect_score = defect_prob  # 색상 기반 점수 사용
            img_io.seek(0)
            base64_str, overlay = visualize_defect(img_io, best_mask)

    faulty_score = int(defect_prob) if is_defective else 0
    print(f"통합 점수 - faulty_score: {faulty_score}")

    return {
        "detected": bool(detected),
        "confidence": float(confidence),
        "is_defective": bool(is_defective),
        "defect_prob": float(defect_prob),
        "defect_score": float(defect_score),
        "faulty_score": int(faulty_score),
        "image": overlay,
        "base64_str": base64_str
    }

# /capture 엔드포인트 정의
@app.route('/capture', methods=['GET'])
def capture():
    try:
        print(f"Attempting to connect to: {ESP32CAM_STREAM_URL}")
        # IP 접근성 테스트
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('10.0.66.13', 81))
            if result == 0:
                print("ESP32-CAM IP reachable")
            else:
                print(f"ESP32-CAM IP unreachable, error code: {result}")
            sock.close()
        except Exception as e:
            print(f"IP reachability test failed: {str(e)}")

        # 스트림 연결 재시도
        max_retries = 5
        for attempt in range(max_retries):
            cap = cv2.VideoCapture(ESP32CAM_STREAM_URL)
            if cap.isOpened():
                print("Stream opened successfully")
                break
            print(f"Retry {attempt + 1}/{max_retries} - Failed to open stream")
            time.sleep(2)
        else:
            print("Failed to open stream after all retries")
            return jsonify({"error": "Stream Unavailable"}), 500

        print("Capturing frame from ESP32CAM_STREAM_URL")
        success, frame = cap.read()
        if not success:
            cap.release()
            print("Failed to capture frame from ESP32CAM_STREAM_URL")
            return jsonify({"error": "Capture Failed"}), 500

        _, buffer = cv2.imencode('.jpg', frame)
        image_data = base64.b64encode(buffer).decode('utf-8')
        print("Processing captured image")
        result = process_image(image_data)
        if result is None:
            cap.release()
            print("Failed to process image in process_image")
            return jsonify({"error": "Processing Failed"}), 500

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_filename = f"battery_{timestamp}.jpg"
        image_path = os.path.join(IMAGE_SAVE_PATH, image_filename)
        cv2.imwrite(image_path, result["image"])
        manage_images()

        cap.release()

        # JSON 응답으로 불량 여부와 시각화 데이터 포함
        _, buffer = cv2.imencode('.jpg', result["image"])
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        response_data = {
            "detected": result["detected"],
            "confidence": result["confidence"],
            "is_defective": result["is_defective"],
            "defect_prob": result["defect_prob"],
            "defect_score": result["defect_score"],
            "faulty_score": result["faulty_score"],
            "image_base64": image_base64,
            "base64_str": result["base64_str"] if result["is_defective"] else "",
            "line_id": 1,
            "log_date": datetime.now().strftime('%Y.%m.%d %H:%M:%S'),
            "image_path": image_filename
        }
        return jsonify(response_data), 200

    except Exception as e:
        print("Capture error:", str(e))
        return jsonify({"error": str(e)}), 500

# ESP32-CAM에서 이미지 수신 및 처리
@app.route('/detect', methods=['POST'])
def detect_battery():
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({"error": "이미지가 없습니다."}), 400

        result = process_image(data['image'])
        if result is None:
            return jsonify({"error": "이미지 처리 실패"}), 500

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_filename = f"battery_{timestamp}.jpg"
        image_path = os.path.join(IMAGE_SAVE_PATH, image_filename)
        cv2.imwrite(image_path, result["image"])
        manage_images()

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO faulty_log (lineIdx, faultyScore, faultyImage, logDate, removed)
            VALUES (%s, %s, %s, %s, %s)
        """, (1, result["faulty_score"], image_filename, datetime.now(), 0))
        mysql.connection.commit()
        cursor.close()

        if result["detected"] and result["confidence"] > 0.5:
            scroll_state['action'] = 'pause'
        else:
            scroll_state['action'] = 'resume'

        return jsonify({
            "detected": result["detected"],
            "confidence": result["confidence"],
            "is_defective": result["is_defective"],
            "defect_prob": result["defect_prob"],
            "defect_score": result["defect_score"],
            "faulty_score": result["faulty_score"],
            "image_path": image_filename,
            "scroll_action": scroll_state['action']
        }), 200
    except Exception as e:
        print("에러 발생:", str(e))
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

# 스크롤 제어
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

# YOLO 모델 테스트 엔드포인트
@app.route('/test_yolo', methods=['GET'])
def test_yolo():
    try:
        image_dir = IMAGE_SAVE_PATH
        image_files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if not image_files:
            return jsonify({"error": "static/images/ 폴더에 이미지가 없습니다."}), 404

        image_path = os.path.join(image_dir, image_files[0])
        print(f"테스트 이미지 경로: {image_path}")

        image_cv = cv2.imread(image_path)
        if image_cv is None:
            return jsonify({"error": "이미지를 로드할 수 없습니다."}), 400

        results = model_yolo(image_cv)
        detected = False
        confidence = 0.0
        for result in results:
            for box in result.boxes:
                if box.cls == 0:
                    detected = True
                    confidence = float(box.conf)
                    break
            if detected:
                break

        return jsonify({
            "detected": detected,
            "confidence": confidence,
            "image_file": image_files[0],
            "message": "YOLO 모델 테스트 완료"
        }), 200
    except Exception as e:
        print("테스트 중 에러 발생:", str(e))
        return jsonify({"error": str(e)}), 500

# Flask 라우트들
@app.route('/')
def index():
    if 'userid' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'userid' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/analysis')
def analysis():
    if 'userid' not in session:
        return redirect(url_for('login'))
    return render_template('analysis.html')

@app.route('/detail-analysis')
def detail_analysis():
    if 'userid' not in session:
        return redirect(url_for('login'))
    return render_template('detail-analysis.html')

@app.route('/monitoring')
def monitoring():
    if 'userid' not in session:
        return redirect(url_for('login'))
    return render_template('monitoring.html')

@app.route('/system-management')
def system_management():
    if 'userid' not in session:
        return redirect(url_for('login'))
    return render_template('system-management.html')

@app.route('/criteria-setting')
def criteria_setting():
    if 'userid' not in session:
        return redirect(url_for('login'))
    return render_template('criteria-setting.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        userid = request.form.get('userid')
        password = request.form.get('password').strip()

        stored_hashed_password = manager.get_user_password_hash(userid)
        if not stored_hashed_password:
            return render_template('login.html', alert_message="등록된 회원이 없습니다.", userid=userid)

        try:
            if not manager.ph.verify(stored_hashed_password, password):
                return render_template('login.html', alert_message="비밀번호가 틀렸습니다.", userid=userid)
        except Exception:
            return render_template('login.html', alert_message="비밀번호 검증 중 오류가 발생했습니다.", userid=userid)

        user_info = manager.get_user_info(userid)

        if user_info['userLevel'] == 0:
            return render_template('login.html', alert_message="회원가입 승인 대기중입니다.", userid=userid)
        if user_info['refusal'] == 1:
            return render_template('login.html', alert_message="회원가입이 거절되었습니다.", userid=userid)
        if user_info['removed'] == 1:
            return render_template('login.html', alert_message="탈퇴한 계정입니다.", userid=userid)

        session['userid'] = user_info['userid']
        session['username'] = user_info['username']
        session['userLevel'] = user_info['userLevel']

        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("로그아웃되었습니다.")
    return redirect(url_for('login'))

@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'POST':
        username = request.form.get('username')
        emp_no = request.form.get('emp_no')
        userid = request.form.get('userid')
        phone1 = request.form.get('phone1')
        phone2 = request.form.get('phone2')
        phone3 = request.form.get('phone3')
        email = request.form.get('email')
        domain = request.form.get('domain')
        password = request.form.get('password')

        userPhone = phone1 + '-' + phone2 + '-' + phone3 
        userEmail = email + '@' + domain
        if not username or not emp_no or not userid or not password or not phone1 or not phone2 or not phone3 or not email or not domain:
            return render_template('login.html', alert_message="모든 필드를 입력해 주세요.")

        insert_success, error_message = manager.insert_user(username, emp_no, userid, password, userPhone, userEmail)
        if insert_success:
            return render_template('login.html', alert_message="회원가입이 성공적으로 완료되었습니다. 관리자의 승인 후 이용 가능합니다.")
        else:
            return render_template('login.html', alert_message=f"회원가입에 실패하였습니다. 다시 시도해 주세요: {error_message}")

    return render_template('login.html')

@app.route('/check_id', methods=['POST'])
def check_id():
    data = request.json
    user_id = data.get('userId')
    is_existing_user = manager.check_user_id_exists(user_id)
    return jsonify({'available': not is_existing_user})

@app.route('/find_password', methods=['POST', 'GET'])
def find_password():
    if request.method == 'POST':
        username = request.form.get('username')
        userid = request.form.get('userid')
        phone1 = request.form.get('phone1')
        phone2 = request.form.get('phone2')
        phone3 = request.form.get('phone3')
        userPhone = f"{phone1}-{phone2}-{phone3}"

        if not username or not userid or not phone1 or not phone2 or not phone3:
            return render_template('lost_password.html', alert_message="모든 필드를 입력해 주세요.")

        user = manager.find_user(username, userid, userPhone)
        if user:
            return redirect(url_for('reset_password', userid=userid))
        else:
            return render_template('lost_password.html', alert_message="사용자 정보를 찾을 수 없습니다.")

    return render_template('lost_password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    userid = request.args.get('userid')
    if request.method == 'POST':
        userid = request.form.get('userid', userid)
        new_password = request.form.get('new_password').strip()
        re_new_password = request.form.get('re_new_password').strip()

        if not new_password:
            return render_template('reset_password.html', userid=userid, alert_message="새 비밀번호를 입력해 주세요.")
        if new_password != re_new_password:
            return render_template('reset_password.html', userid=userid, alert_message="비밀번호가 일치하지 않습니다.")

        hashed_password = ph.hash(new_password)
        if manager.update_password(userid, hashed_password):
            return render_template('login.html', alert_message="비밀번호가 성공적으로 변경되었습니다.")
        else:
            return render_template('reset_password.html', userid=userid, alert_message="비밀번호 업데이트 중 오류가 발생했습니다.")
    return render_template('reset_password.html', userid=userid)

@app.route('/mypage', methods=['GET'])
def mypage():
    if 'userid' not in session:
        flash("로그인 후 접근해 주세요.")
        return redirect(url_for('login'))

    user_id = session['userid']
    mydata = manager.get_member_mypage(user_id)
    return render_template('member/mypage.html', mydata=mydata)

@app.route('/update_member', methods=['POST'])
def update_member():
    if 'userid' not in session:
        return redirect(url_for('login'))

    user_id = request.form.get('userid', '').strip()
    emp_no = request.form.get('emp_no', '').strip()
    phone1 = request.form.get('phone1', '').strip()
    phone2 = request.form.get('phone2', '').strip()
    phone3 = request.form.get('phone3', '').strip()
    email1 = request.form.get('email1', '').strip()
    email2 = request.form.get('email2', '').strip()
    password = request.form.get('password', '').strip()
    confirmPassword = request.form.get('confirmPassword', '').strip()
    new_level = request.form.get('userLevel', None)

    userEmail = f"{email1}@{email2}" if email1 and email2 else None
    userPhone = f"{phone1}-{phone2}-{phone3}" if phone1 and phone2 and phone3 else None

    if not emp_no or not phone1 or not phone2 or not phone3 or not email1 or not email2:
        mydata = manager.get_member_mypage(user_id)
        return render_template('member/mypage.html', alert_message="모든 필드를 입력해 주세요.", mydata=mydata)

    if password and confirmPassword:
        if password != confirmPassword:
            mydata = manager.get_member_mypage(user_id)
            return render_template('member/mypage.html', alert_message="비밀번호가 일치하지 않습니다.", mydata=mydata)
        hashed_password = ph.hash(password)
    else:
        hashed_password = None

    update_success = manager.update_member_info(user_id, emp_no, hashed_password, userPhone, userEmail, new_level)

    if update_success:
        user_info = manager.get_user_info(user_id)
        session['username'] = user_info['username']
        session['userLevel'] = user_info['userLevel']
        mydata = manager.get_member_mypage(user_id)
        return render_template('member/mypage.html', alert_message="회원정보가 성공적으로 수정되었습니다.", mydata=mydata)
    else:
        mydata = manager.get_member_mypage(user_id)
        return render_template('member/mypage.html', alert_message="회원정보 수정 중 오류가 발생했습니다.", mydata=mydata)

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'userid' not in session:
        return redirect(url_for('login'))

    user_id = session['userid']
    user_level = session.get('userLevel', 0)

    withdraw_success = manager.withdraw_member(user_id)

    if withdraw_success:
        if user_level < 100:
            session.pop('userid', None)
            return render_template('login.html', alert_message="회원 탈퇴가 완료되었습니다.")
        else:
            return render_template('admin_dashboard.html', alert_message="회원 탈퇴가 완료되었습니다.")
    else:
        mydata = manager.get_member_mypage(user_id)
        return render_template('member/mypage.html', alert_message="회원 탈퇴 중 오류가 발생했습니다.", mydata=mydata)

@app.route('/member_manage')
def member_manage():
    per_page = 3

    admin_page = request.args.get('admin_page', 1, type=int)
    all_admins = manager.get_admins()
    total_admins = len(all_admins)
    admin_start_idx = (admin_page - 1) * per_page
    admin_end_idx = min(admin_start_idx + per_page, total_admins)
    paginated_admins = all_admins[admin_start_idx:admin_end_idx]
    total_admin_pages = (total_admins // per_page) + (1 if total_admins % per_page > 0 else 0)

    pending_page = request.args.get('pending_page', 1, type=int)
    all_pending_members = manager.get_pending_members()
    total_pending = len(all_pending_members)
    pending_start_idx = (pending_page - 1) * per_page
    pending_end_idx = min(pending_start_idx + per_page, total_pending)
    paginated_pending = all_pending_members[pending_start_idx:pending_end_idx]
    total_pending_pages = (total_pending // per_page) + (1 if total_admins % per_page > 0 else 0)

    member_page = request.args.get('member_page', 1, type=int)
    all_members = manager.get_all_members()
    total_members = len(all_members)
    member_start_idx = (member_page - 1) * per_page
    member_end_idx = min(member_start_idx + per_page, total_members)
    paginated_members = all_members[member_start_idx:member_end_idx]
    total_member_pages = (total_members // per_page) + (1 if total_members % per_page > 0 else 0)

    return render_template(
        'member/member_manage.html',
        per_page=per_page,
        admins=paginated_admins,
        admin_current_page=admin_page,
        total_admins=total_admins,
        admin_total_pages=total_admin_pages,
        pending_members=paginated_pending,
        pending_current_page=pending_page,
        total_pending=total_pending,
        pending_total_pages=total_pending_pages,
        pending_start_idx=pending_start_idx,
        pending_end_idx=pending_end_idx,
        all_members=paginated_members,
        member_current_page=member_page,
        total_members=total_members,
        member_total_pages=total_member_pages,
        member_start_idx=member_start_idx,
        member_end_idx=member_end_idx
    )

@app.route('/approve_member', methods=['POST'])
def approve_member():
    data = request.json
    userid = data.get('userid')
    user_info = manager.get_user_info(userid)
    if not user_info:
        return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없습니다.'}), 404

    success = manager.update_user_level(userid, 1)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False}), 400

@app.route('/refuse_member', methods=['POST'])
def refuse_member():
    data = request.json
    userid = data.get('userid')
    user_info = manager.get_user_info(userid)
    if not user_info:
        return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없습니다.'}), 404

    success = manager.refuse_member(userid)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False}), 400
  
@app.route('/edit_member/<userid>', methods=['GET'])
def edit_member(userid):
    if 'userid' not in session or session.get('userLevel') < 100:
        return redirect(url_for('login'))

    member_data = manager.get_member_mypage(userid)
    if not member_data:
        flash("해당 회원 정보를 찾을 수 없습니다.", "error")
        return redirect(url_for('member_manage'))

    return render_template('member/mypage.html', mydata=member_data)

@app.route('/delete_member', methods=['POST'])
def delete_member():
    data = request.json
    userid = data.get('userid')
    success = manager.withdraw_member(userid)
    if success:
        return jsonify({'success': True, 'message': f"{userid} 회원이 탈퇴처리 되었습니다."})
    else:
        return jsonify({'success': False, 'message': "회원 삭제 실패"})

@app.route('/search_members', methods=['POST'])
def search_members():
    data = request.json
    userid = data.get('userid', '').strip()
    username = data.get('username', '').strip()
    emp_no = data.get('emp_no', '').strip()

    try:
        results = manager.search_members(userid=userid, username=username, emp_no=emp_no)

        if results is not None and len(results) > 0:
            return jsonify({'success': True, 'members': results})
        elif results is not None and len(results) == 0:
            return jsonify({'success': False})
        else:
            return jsonify({'success': False})
    except Exception as e:
        print(f"검색 중 오류 발생: {str(e)}")
        return jsonify({'success': False, 'message': f'검색 중 오류: {str(e)}'})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)