// 로그아웃 기능
function logout() {
    if (confirm('로그아웃 하시겠습니까?')) {
        window.location.href = '/logout';
    }
}

// 사이드바 메뉴 클릭 시 페이지 이동
document.querySelectorAll('.nav-item > a').forEach(item => {
    item.addEventListener('click', function (e) {
        e.preventDefault();
        const targetPage = this.href.split('/').pop();
        window.location.href = targetPage;
    });
});

// 알림 토글
function toggleNotification() {
    const dropdown = document.querySelector('.notification-dropdown');
    dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
}

// 파일명 표시
function showFileName() {
    const fileInput = document.getElementById('file-upload');
    const fileName = document.getElementById('fileName');
    if (fileInput.files.length > 0) {
        fileName.textContent = fileInput.files[0].name;
    } else {
        fileName.textContent = '선택된 파일 없음';
    }
}

// 탭 전환
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(content => {
        content.style.display = 'none';
    });
    document.getElementById(tabId).style.display = 'block';
    
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
}

// 폼 초기화
function resetForm() {
    document.querySelectorAll('input[type="text"], textarea').forEach(input => {
        input.value = '';
    });
    document.querySelectorAll('input[type="radio"]').forEach(radio => {
        radio.checked = false;
    });
    document.getElementById('fileName').textContent = '선택된 파일 없음';
}

// 요청 제출
function submitRequest() {
    // 입력값 가져오기
    const checkType = document.querySelector('input[name="checkType"]:checked')?.value || '';
    const userName = document.getElementById('userName').value;
    const emailId = document.getElementById('emailId').value;
    const emailDomain = document.getElementById('emailDomain').value;
    const emailExt = document.getElementById('emailExt').value;
    const subject = document.getElementById('subject').value;
    
    // 간단한 유효성 검사
    if (!checkType || !userName || !emailId || !emailDomain || !subject) {
        alert('필수 항목을 모두 입력해주세요.');
        return;
    }
    
    // 현재 날짜 생성
    const today = new Date();
    const dateString = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    
    // 테이블에 새 행 추가
    const table = document.getElementById('requestHistoryTable').getElementsByTagName('tbody')[0];
    const newRow = table.insertRow(0);
    
    const cell1 = newRow.insertCell(0);
    const cell2 = newRow.insertCell(1);
    const cell3 = newRow.insertCell(2);
    
    cell1.innerHTML = dateString;
    cell2.innerHTML = subject;
    cell3.innerHTML = '<span class="status-bad">처리중</span>';
    
    // 폼 초기화
    resetForm();
    
    // 점검 요청 내역 탭으로 전환
    showTab('history');
    
    alert('점검 요청이 성공적으로 제출되었습니다.');
}

// 서브메뉴 토글 기능
document.querySelectorAll('.submenu-toggle').forEach(toggle => {
    toggle.addEventListener('click', function(e) {
        e.preventDefault();
        const submenu = this.parentElement.nextElementSibling;
        submenu.classList.toggle('closed');
        this.classList.toggle('fa-chevron-down');
        this.classList.toggle('fa-chevron-right');
    });
});

// 상세 페이지 이동 함수
function goToDetailPage(type, date, scoreSeverity) {
    window.location.href = `{{ url_for('detail_analysis') }}?type=${type}&date=${date}&scoreSeverity=${scoreSeverity}`;
}