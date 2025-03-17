# app.py
from flask import Flask, render_template, redirect, url_for

app = Flask(__name__)

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/analysis')
def analysis():
    return render_template('analysis.html')

@app.route('/detail-analysis')
def detail_analysis():
    return render_template('detail-analysis.html')

@app.route('/prediction')
def prediction():
    return render_template('prediction.html')

@app.route('/mypage')
def mypage():
    return render_template('mypage.html')

@app.route('/system-management')
def system_management():
    return render_template('system-management.html')

@app.route('/criteria-setting')
def criteria_setting():
    return render_template('criteria-setting.html')

@app.route('/logout')
def logout():
    # 실제 로그아웃 로직 추가 가능 (세션 종료 등)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)