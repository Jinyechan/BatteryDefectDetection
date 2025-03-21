function saveUserInfo() {
        alert('사용자 정보가 저장되었습니다.');
    }

    function saveSettings() {
        const notifTime = document.getElementById('notifTime').value;
        const notifType = document.getElementById('notifType').value;
        const pushNotif = document.getElementById('pushNotif').checked;

        localStorage.setItem('notifTime', notifTime);
        localStorage.setItem('notifType', notifType);
        localStorage.setItem('pushNotif', pushNotif);

        alert('알림 설정이 저장되었습니다.');
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.getElementById('notifTime').value = localStorage.getItem('notifTime') || '즉시';
        document.getElementById('notifType').value = localStorage.getItem('notifType') || 'all';
        document.getElementById('pushNotif').checked = localStorage.getItem('pushNotif') === 'true';
    });