function searchMembers() {
    const userid = document.getElementById('searchId').value;
    const username = document.getElementById('searchName').value;
    const emp_no = document.getElementById('searchEmpNo').value;

    fetch('/search_members', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({userid, username, emp_no})
    })
    .then(response => response.json())
    .then(data => {
        const tableBody = document.getElementById('memberTableBody');
        
        // 테이블 초기화
        tableBody.innerHTML = '';

        if (data.success) {
            console.log("검색 성공:", data.members); // 디버깅용 로그

            data.members.forEach((member, index) => {
                const row = `
                    <tr>
                        <td class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> ${index + 1}</td>
                        <td class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> ${member.userid}</td>
                        <td class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> ${member.emp_no}</td>
                        <td class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> ${member.username}</td>
                        <td class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> ${member.userEmail}</td>
                        <td class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> ${getUserLevelLabel(member.userLevel)}</td>
                        <td class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> ${new Date(member.created_at).toLocaleString()}</td>
                        <td class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> ${member.userLevel === 0 ? '미승인' : '승인'}</td>
                        <td class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> <!-- 관리 버튼 추가 --></td>
                    </tr>`;
                tableBody.innerHTML += row;
            });
        } else {
            const row = `<td colspan = "8" class="text-center px-6 py-4 whitespace-nowrap text-sm text-gray-900"> 등록된 회원이 없습니다.</td>`
            tableBody.innerHTML += row;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert(`오류가 발생했습니다: ${error.message}`);
    });
}

// 회원 레벨 텍스트 반환 함수
function getUserLevelLabel(userLevel) {
    switch (userLevel) {
        case 0: return '미승인 회원';
        case 1: return '일반회원';
        case 100: return '관리자';
        case 1000: return '최고 관리자';
        default: return '알 수 없음';
    }
}






function deleteMember(userid) {
    if (confirm(`${userid} 회원을 탈퇴처리 하시겠습니까?`)) {
        fetch('/delete_member', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userid: userid })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(data.message);
                    location.reload(); // 페이지 새로고침
                } else {
                    alert(data.message || '회원 삭제 실패');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('오류가 발생했습니다.');
            });
    }
}

// 승인 처리 함수
function approveMember(userid, username) {
    if (confirm(`${username} 회원을 승인하시겠습니까?`)) {
        fetch('/approve_member', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userid: userid })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(`${username} 회원이 승인되었습니다.`);
                    location.reload(); // 페이지 새로고침
                } else {
                    alert('회원 승인 실패');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('오류가 발생했습니다.');
            });
    }
}

// 거절 처리 함수
function refuseMember(userid, username) {
    if (confirm(`${username} 회원을 거절하시겠습니까?`)) {
        fetch('/refuse_member', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userid: userid })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(`${username} 회원이 거절되었습니다.`);
                    location.reload(); // 페이지 새로고침
                } else {
                    alert('회원 거절 실패');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('오류가 발생했습니다.');
            });
    }
}
function confirmChange(username, userid) {
    const confirmation = confirm(`${username} 회원을 일반회원으로 전환하시겠습니까?`);
    if (confirmation) {
        // AJAX 요청 또는 폼 전송을 통해 서버로 전송
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = "{{ url_for('update_user_level') }}";  // 적절한 URL로 설정

        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'userid';
        input.value = userid;
        form.appendChild(input);

        document.body.appendChild(form);
        form.submit();  // 폼 제출
    }
}

function openModal() {
    document.getElementById('confirmModal').classList.remove('hidden');
    loadMembers(); // 모달이 열릴 때 회원 데이터 로드
}

function closeModal() {
    document.getElementById('confirmModal').classList.add('hidden');
}

function loadMembers() {
    // 여기에 회원 데이터를 동적으로 로드하는 로직을 추가할 수 있습니다.
    // 예: AJAX 요청을 통해 서버에서 회원 데이터를 가져와 테이블에 추가
    const members = [
        { id: 'admin', emp_no: '122525', name: '최고관리자', email: 'admin@example.com', level: '최고관리자', lastLogin: '2024-02-20 14:30', },
        // 추가 회원 데이터
    ];

    const tbody = document.getElementById('memberTableBody');
    tbody.innerHTML = ''; // 기존 데이터 초기화

    members.forEach(member => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${member.id}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${member.emp_no}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${member.name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${member.email}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${member.level}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${member.lastLogin}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                    활성
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button class="text-custom hover:text-indigo-900 mr-3">추가</button>
               
            </td>
        `;
        tbody.appendChild(row);
    });
}


// 관리자 페이지네이션 변경
function changeAdminPage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('admin_page', page);  // 관리자 페이지만 변경
    window.location.search = urlParams.toString();
}

// 승인 대기 회원 페이지네이션 변경
function changePendingPage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('pending_page', page);  // 승인 대기 회원 페이지만 변경
    window.location.search = urlParams.toString();
}

// 전체 회원 페이지네이션 변경
function changeMemberPage(page) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('member_page', page);  // 전체 회원 페이지만 변경
    window.location.search = urlParams.toString();
}


document.addEventListener("DOMContentLoaded", function () {
    const urlParams = new URLSearchParams(window.location.search);
    const sectionType = urlParams.get('section'); // URL에 'section' 값이 있으면 가져옴
    if (sectionType) {
        showSection(sectionType);
    }
});

// ✅ 페이지 변경 함수 (AJAX로 새로고침 없이 데이터 갱신)
function changePage(page, type) {
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set(type + '_page', page);
    urlParams.set('section', type);

    fetch(`?${urlParams.toString()}`)
        .then(response => response.text())
        .then(data => {
            document.getElementById(type + '-section').innerHTML =
                new DOMParser().parseFromString(data, "text/html")
                    .getElementById(type + '-section').innerHTML;

            scrollToSection(type + '-section'); // 해당 섹션으로 스크롤 이동
        });
}

// ✅ 특정 섹션 보이기
function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(section => {
        section.style.display = 'none';
    });
    const section = document.getElementById(sectionId);
    if (section) {
        section.style.display = 'block';
    }
}

// ✅ 특정 섹션으로 스크롤 이동
function scrollToSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}