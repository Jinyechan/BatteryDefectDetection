from flask import Flask, render_template, flash, request, redirect, url_for, session, jsonify, Response, send_from_directory
from models import DBManager
from argon2 import PasswordHasher
import pandas as pd
import base64
from io import BytesIO
from PIL import Image
import numpy as np
import cv2
from tensorflow.keras.models import load_model
import os
from datetime import datetime
import time
import threading

app = Flask(__name__)
app.secret_key = 'your_secret_key'

@app.before_request
def auto_login_for_dev():
    if not session.get('userid'):
        session['userid'] = 'admin123'
        session['username'] = '김관리자'
        session['userLevel'] = 1000

manager = DBManager()
ph = PasswordHasher()

# ======================== 모델 로드 ========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH_MAIN = os.path.join(BASE_DIR, "static", "fine_tuned_unet_mobilenet_alpha08.h5")
MODEL_PATH_SECONDARY = os.path.join(BASE_DIR, "static", "model_final.h5")
model_main = load_model(MODEL_PATH_MAIN, compile=False)
model_secondary = load_model(MODEL_PATH_SECONDARY, compile=False)

# 프레임 저장 디렉토리 설정
FRAME_DIR = os.path.join(BASE_DIR, "static", "frames")
if not os.path.exists(FRAME_DIR):
    os.makedirs(FRAME_DIR)

# 기본 이미지 생성 (프레임 캡처 실패 시 사용)
DEFAULT_FRAME_PATH = os.path.join(FRAME_DIR, "default.jpg")
if not os.path.exists(DEFAULT_FRAME_PATH):
    default_frame = np.zeros((224, 224, 3), dtype=np.uint8)
    cv2.putText(default_frame, "No Stream", (50, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.imwrite(DEFAULT_FRAME_PATH, default_frame)

# 프레임 저장 리스트 (최근 4개 프레임)
frame_history = []
frame_lock = threading.Lock()

# ESP32Cam 스트림 URL
ESP32CAM_STREAM_URL = "http://10.0.66.13:81/stream"  # ESP32Cam IP

# 프레임 캡처 스레드
def capture_frames():
    while True:
        cap = cv2.VideoCapture(ESP32CAM_STREAM_URL)
        if not cap.isOpened():
            print(f"Failed to open stream: {ESP32CAM_STREAM_URL}")
            time.sleep(10)  # 10초 후 재시도
            continue

        success, frame = cap.read()
        if not success:
            print("Failed to capture frame")
            cap.release()
            time.sleep(2)  # 2초 후 재시도
            continue

        # 프레임 저장
        with frame_lock:
            # 최근 4개 프레임만 유지
            if len(frame_history) >= 4:
                frame_history.pop(0)
            frame_history.append(frame)

            # 프레임을 파일로 저장
            for i in range(len(frame_history)):
                frame_path = os.path.join(FRAME_DIR, f"frame_{i}.jpg")
                cv2.imwrite(frame_path, frame_history[i])
                if os.path.exists(frame_path):
                    print(f"Frame saved: {frame_path}")
                else:
                    print(f"Failed to save frame: {frame_path}")

        cap.release()
        time.sleep(1)  # 1초마다 프레임 캡처

# 프레임 캡처 스레드 시작
threading.Thread(target=capture_frames, daemon=True).start()

# 저장된 프레임 제공 엔드포인트
@app.route('/frame/<int:index>')
def get_frame(index):
    frame_path = os.path.join(FRAME_DIR, f"frame_{index}.jpg")
    if os.path.exists(frame_path):
        return send_from_directory(FRAME_DIR, f"frame_{index}.jpg")
    else:
        print(f"Frame not found: {frame_path}, returning default frame")
        return send_from_directory(FRAME_DIR, "default.jpg")

# 실시간 스트림 제공 (camera1용)
def generate_frames():
    while True:
        cap = cv2.VideoCapture(ESP32CAM_STREAM_URL)
        if not cap.isOpened():
            print(f"Failed to open stream: {ESP32CAM_STREAM_URL}")
            time.sleep(10)  # 10초 후 재시도
            continue

        success, frame = cap.read()
        if not success:
            print("Failed to capture frame")
            cap.release()
            time.sleep(2)  # 2초 후 재시도
            continue

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        cap.release()

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ======================== ESP32Cam 이미지 업로드 엔드포인트 ========================
@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image part in the request'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # 이미지 처리 (불량 검출 및 위치 시각화)
    score, overlay = predict_and_get_base64(file)

    # 데이터베이스에 결과 저장
    result = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'score': score,
        'overlay': overlay
    }
    manager.insert_defect_result(result)

    # 결과 반환
    return jsonify({'score': round(score, 1), 'overlay': overlay})

# ======================== 예측 함수 ========================
def predict_and_get_base64(image, use_secondary=False):
    model = model_secondary if use_secondary else model_main
    img = cv2.imdecode(np.frombuffer(image.read(), np.uint8), cv2.IMREAD_COLOR)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    original_size = img.shape[:2]

    img_resized = cv2.resize(img, (224, 224)).astype(np.float32) / 255.0
    pred_mask = model.predict(np.expand_dims(img_resized, axis=0))[0]
    pred_mask = (pred_mask > 0.5).astype(np.uint8)

    defect_ratio = np.sum(pred_mask) / (224 * 224)
    defect_score = min(defect_ratio * 10000, 100)

    pred_mask_resized = cv2.resize(pred_mask[:, :, 0], (original_size[1], original_size[0]), interpolation=cv2.INTER_NEAREST)
    overlay = img.copy()
    overlay[pred_mask_resized == 1] = [255, 0, 0]

    pil_img = Image.fromarray(overlay)
    buf = BytesIO()
    pil_img.save(buf, format='PNG')
    base64_str = base64.b64encode(buf.getvalue()).decode('utf-8')

    return defect_score, base64_str

# ======================== Flask 라우트들 ========================
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

@app.route('/batch-predict')
def batch_predict():
    if 'userid' not in session:
        return redirect(url_for('login'))

    image_dir = os.path.join(BASE_DIR, 'images')
    results = []
    for fname in os.listdir(image_dir):
        if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
            filepath = os.path.join(image_dir, fname)
            with open(filepath, 'rb') as f:
                score, overlay = predict_and_get_base64(f, use_secondary=True)
                results.append({
                    'filename': fname,
                    'score': round(score, 1),
                    'overlay': overlay
                })

    return render_template('batch_predict.html', results=results)

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

@app.route('/prediction', methods=['GET', 'POST'])
def prediction():
    if 'userid' not in session:
        return redirect(url_for('login'))

    results = []
    if request.method == 'POST':
        files = request.files.getlist("file")
        for file in files:
            if file:
                score, overlay = predict_and_get_base64(file)
                results.append({'score': round(score, 1), 'overlay': overlay})

    return render_template('prediction.html', results=results)

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
    total_pending_pages = (total_pending // per_page) + (1 if total_pending % per_page > 0 else 0)

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

# ======================== 차트용 데이터 API ========================
def load_data():
    df = pd.read_csv("your_processed_data.csv")
    return df

@app.route("/api/chart_data")
def chart_data():
    chart_type = request.args.get("type")
    period = request.args.get("period")

    df = load_data()

    if chart_type == "line":
        result = df.groupby("라인")[period].mean()
        return jsonify({
            "labels": result.index.tolist(),
            "values": result.values.tolist()
        })

    elif chart_type == "bar":
        result = df.groupby("날짜")[period].mean().sort_index()
        return jsonify({
            "labels": result.index.tolist(),
            "values": result.values.tolist()
        })

# ======================== 앱 실행 ========================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)