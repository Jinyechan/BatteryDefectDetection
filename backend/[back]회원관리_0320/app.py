from flask import Flask, render_template, flash, request, redirect, url_for, session, jsonify
from models import DBManager
from argon2 import PasswordHasher

app = Flask(__name__)
app.secret_key = 'your_secret_key'

manager = DBManager()
ph = PasswordHasher()

# 관리자페이지 대시보드 - 메인화면 
@app.route('/')
def index():
    return render_template('index.html')

# 로그인 
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
        except Exception as e:
            return render_template('login.html', alert_message="비밀번호 검증 중 오류가 발생했습니다.", userid=userid)

        # 사용자 정보 가져오기
        user_info = manager.get_user_info(userid)

        # 회원가입 승인 대기 상태 체크
        if user_info['userLevel'] == 0:
            return render_template(
                'login.html',
                alert_message="회원가입 승인 대기중입니다. 회원가입 승인 후 이용이 가능합니다.",
                userid=userid
            )

        # 회원가입 거절 상태 체크
        if user_info['refusal'] == 1:
            return render_template(
                'login.html',
                alert_message="회원가입을 거절하였습니다. 사이트 이용을 원하실 경우 관리자에게 문의해주시기 바랍니다.",
                userid=userid
            )
        
        # 회원탈퇴 여부 체크
        if user_info['removed'] == 1:
            return render_template(
                'login.html',
                alert_message="탈퇴한 계정입니다. 회원가입 후 다시 이용바랍니다.",
                userid=userid
            )

        # 정상 로그인 처리 (승인 완료된 사용자)
        session['userid'] = user_info['userid']
        session['username'] = user_info['username']
        session['userLevel'] = user_info['userLevel']
        
        return redirect(url_for('index'))

    return render_template('login.html')


# 로그아웃 
@app.route('/logout')
def logout():
    session.clear()  # 모든 세션 정보 삭제
    flash("로그아웃되었습니다.")
    return redirect(url_for('login'))

# 회원가입
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

        # 핸드폰 번호 합치기 
        userPhone = phone1 + '-' + phone2 + '-' + phone3 
        # 이메일 합치기
        userEmail = email + '@' + domain
        
        if not username or not emp_no or not userid or not password or not phone1 or not phone2 or not phone3 or not email or not domain:
            return render_template('login.html', alert_message="모든 필드를 입력해 주세요.")

        # 평문 비밀번호를 insert_user에 전달 (insert_user 내부에서 한 번만 해싱)
        insert_success, error_message = manager.insert_user(username, emp_no, userid, password, userPhone, userEmail)
        if insert_success:
            return render_template('login.html', alert_message="회원가입이 성공적으로 완료되었습니다. 관리자의 승인 후 서비스 이용이 가능하십니다.")
        else:
            return render_template('login.html', alert_message=f"회원가입에 실패하였습니다. 다시 시도해 주세요: {error_message}")

    return render_template('login.html')

# ID 중복체크
@app.route('/check_id', methods=['POST'])
def check_id():
    data = request.json
    user_id = data.get('userId')

    # 데이터베이스에서 ID 확인 (DBManager에 해당 메서드 추가 필요)
    is_existing_user = manager.check_user_id_exists(user_id)

    if is_existing_user:  # 기존 사용자 ID 확인
        return jsonify({'available': False})  # 사용 중인 아이디
    else:
        return jsonify({'available': True})  # 사용 가능한 아이디

# 비밀번호 찾기   
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
            # 사용자 정보를 기반으로 비밀번호 재설정 페이지로 리디렉션
            return redirect(url_for('reset_password', userid=userid))  # userid를 URL에 포함
        else:
            return render_template('lost_password.html', alert_message="사용자 정보를 찾을 수 없습니다.")
    
    return render_template('lost_password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    userid = request.args.get('userid')  # 🔹 URL에서 userid 가져오기
    if request.method == 'POST':
        # 🔹 POST 요청 시 form에서 userid 가져오기 (우선 적용)
        userid = request.form.get('userid', userid)  # POST 값이 없으면 기존 URL 값 사용

        if not userid:
            return render_template('lost_password.html', alert_message="비정상적인 접근입니다. 다시 시도해 주세요.")

        new_password = request.form.get('new_password').strip()
        re_new_password = request.form.get('re_new_password').strip()

        if not new_password:
            return render_template('reset_password.html', userid=userid, alert_message="새 비밀번호를 입력해 주세요.")

        if new_password != re_new_password:
            return render_template('reset_password.html', userid=userid, alert_message="비밀번호가 일치하지 않습니다.")

        # 비밀번호 해싱
        hashed_password = ph.hash(new_password)

        # 비밀번호 업데이트
        if manager.update_password(userid, hashed_password):
            return render_template('login.html', alert_message="비밀번호가 성공적으로 변경되었습니다.")
        else:
            return render_template('reset_password.html', userid=userid, alert_message="비밀번호 업데이트 중 오류가 발생했습니다.")

    return render_template('reset_password.html', userid=userid)

# 마이페이지 - 회원정보 가져오기
@app.route('/mypage', methods=['GET'])
def view_mypage():
    if 'userid' not in session:
        flash("로그인 후 접근해 주세요.")
        return redirect(url_for('login'))

    user_id = session['userid']
    mydata = manager.get_member_mypage(user_id)
    return render_template('member/mypage.html', mydata=mydata)

# 마이페이지 - 회원정보 수정 
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

    # 세션 값 업데이트
    if update_success:
        user_info = manager.get_user_info(user_id)  # 업데이트된 사용자 정보를 가져옵니다.
        session['username'] = user_info['username']
        session['userLevel'] = user_info['userLevel']  # 새로운 userLevel로 세션 업데이트
        mydata = manager.get_member_mypage(user_id)  # 최신 회원정보 가져오기
        return render_template('member/mypage.html', alert_message="회원정보가 성공적으로 수정되었습니다.", mydata=mydata)
    else:
        mydata = manager.get_member_mypage(user_id)
        return render_template('member/mypage.html', alert_message="회원정보 수정 중 오류가 발생했습니다.", mydata=mydata)

# 마이페이지 - 회원정보 수정 -  회원 탈퇴 기능
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

# 회원 관리 페이지
@app.route('/member_manage')
def member_manage():
    per_page = 3  # 한 페이지당 항목 수

    # 관리자 페이지네이션
    admin_page = request.args.get('admin_page', 1, type=int)
    all_admins = manager.get_admins()
    total_admins = len(all_admins)
    admin_start_idx = (admin_page - 1) * per_page
    admin_end_idx = min(admin_start_idx + per_page, total_admins)
    paginated_admins = all_admins[admin_start_idx:admin_end_idx]
    total_admin_pages = (total_admins // per_page) + (1 if total_admins % per_page > 0 else 0)

    # 승인 대기 회원 페이지네이션
    pending_page = request.args.get('pending_page', 1, type=int)
    all_pending_members = manager.get_pending_members()
    total_pending = len(all_pending_members)
    pending_start_idx = (pending_page - 1) * per_page
    pending_end_idx = min(pending_start_idx + per_page, total_pending)
    paginated_pending = all_pending_members[pending_start_idx:pending_end_idx]
    total_pending_pages = (total_pending // per_page) + (1 if total_pending % per_page > 0 else 0)

    # 전체 회원 페이지네이션
    member_page = request.args.get('member_page', 1, type=int)
    all_members = manager.get_all_members()
    total_members = len(all_members)
    member_start_idx = (member_page - 1) * per_page
    member_end_idx = min(member_start_idx + per_page, total_members)
    paginated_members = all_members[member_start_idx:member_end_idx]
    total_member_pages = (total_members // per_page) + (1 if total_members % per_page > 0 else 0)

    return render_template(
        'member/member_manage.html', 
        per_page = per_page,

        
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

# 관리자 회원 제외
@app.route('/update_user_level', methods=['POST'])
def update_user_level():
    if 'userid' not in session:
        return redirect(url_for('login'))

    user_id = request.form.get('userid')

    # userLevel을 1로 업데이트
    success = manager.update_user_level(user_id, 1)  # DBManager에 해당 메서드 필요

    if success:
        # 회원의 이름을 가져오기
        user_info = manager.get_user_info(user_id)  # 해당 메서드 추가 필요
        flash(f"{user_info['username']} 회원이 일반회원으로 전환되었습니다.")
    else:
        flash("회원 전환 중 오류가 발생했습니다.")

    return redirect(url_for('member_manage'))  # 관리자 관리 페이지로 리디렉션

# 회원 가입 승인
@app.route('/approve_member', methods=['POST'])
def approve_member():
    data = request.json
    userid = data.get('userid')

    # 회원 정보 가져오기 (회원명 포함)
    user_info = manager.get_user_info(userid)
    if not user_info:
        return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없습니다.'}), 404

    # 회원 승인 처리
    success = manager.update_user_level(userid, 1)  # userLevel을 1로 변경
    if success:
        flash(f"{user_info['username']} 회원을 승인하였습니다.", "success")
        return jsonify({'success': True})
    else:
        return jsonify({'success': False}), 400

# 회원 가입 거절
@app.route('/refuse_member', methods=['POST'])
def refuse_member():
    data = request.json
    userid = data.get('userid')

    # 회원 정보 가져오기 (회원명 포함)
    user_info = manager.get_user_info(userid)
    if not user_info:
        return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없습니다.'}), 404

    # 회원 거절 처리
    success = manager.refuse_member(userid)  # refusal 값을 1로 변경
    if success:
        flash(f"{user_info['username']} 회원을 거절하였습니다.", "error")
        return jsonify({'success': True})
    else:
        return jsonify({'success': False}), 400

# 회원정보 수정
@app.route('/edit_member/<userid>', methods=['GET'])
def edit_member(userid):
    if 'userid' not in session:
        return redirect(url_for('login'))

    # 회원 정보 가져오기
    member_data = manager.get_member_mypage(userid)
    if not member_data:
        flash("해당 회원 정보를 찾을 수 없습니다.", "error")
        return redirect(url_for('member_manage'))

    return render_template('member/mypage.html', mydata=member_data)

# 회원 탈퇴 
@app.route('/delete_member', methods=['POST'])
def delete_member():
    data = request.json
    userid = data.get('userid')

    success = manager.withdraw_member(userid)  # 회원 탈퇴 처리 메서드 호출

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
        # DBManager의 search_members 메서드 호출
        results = manager.search_members(userid=userid, username=username, emp_no=emp_no)

        if results is not None and len(results) > 0:
            return jsonify({'success': True, 'members': results})
        elif results is not None and len(results) == 0:
            return jsonify({'success': False})
        else:
            return jsonify({'success': False})

    except Exception as e:
        print(f"검색 중 오류 발생: {str(e)}")  # 디버깅용 로그
        return jsonify({'success': False, 'message': f'검색 중 오류: {str(e)}'})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)