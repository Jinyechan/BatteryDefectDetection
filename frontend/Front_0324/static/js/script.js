let unreadCount = 0;
let unreadMessages = [];
let unreadNotificationVisible = false; // "N건 메시지"가 떠 있는 상태 여부
let lastReadTime = Date.now();
let stopAddingAlerts = false; // 개별 알림 추가 여부 차단
let unreadMessageTimer = null; // 1분 타이머

// 읽지 않은 메시지 개수 업데이트
function updateUnreadAnomalyCount() {
    const countElement = document.getElementById("unreadAnomalyCount");
    countElement.textContent = unreadCount > 0 ? unreadCount : "";
    countElement.classList.toggle("hidden", unreadCount === 0);
}

// "N건 메시지" 표시 (이후 개별 알림 멈춤)
function showUnreadMessageNotification() {
    console.log("[showUnreadMessageNotification] 실행됨");

    const container = document.getElementById("anomalyAlertContainer");
    let existingNotification = document.querySelector(".unread-message-notification");

    if (existingNotification) {
        unreadCount++;
        existingNotification.querySelector("span").textContent = `안 읽은 메시지 ${unreadCount}건이 있습니다.`;
        console.log(`[showUnreadMessageNotification] N 증가: ${unreadCount}`);
    } else {
        // 처음으로 "N건 메시지" 표시
        unreadCount = unreadMessages.length;
        container.innerHTML = `
            <div class="anomaly-alert unread-message-notification">
                <span>안 읽은 메시지 ${unreadCount}건이 있습니다.</span>
                <button class="confirm-btn" onclick="markUnreadMessagesAsRead()">확인</button>
            </div>
        `;
        unreadNotificationVisible = true;
        stopAddingAlerts = true; // 새로운 개별 알림 추가 중지
        console.log("[showUnreadMessageNotification] N건 메시지 최초 생성됨");

        // 기존 개별 이상 알림 제거
        document.querySelectorAll(".anomaly-alert:not(.unread-message-notification)").forEach(alert => alert.remove());
    }
}

// 1분 후 "N건 메시지"로 자동 전환
function scheduleUnreadMessageCheck() {
    console.log("[scheduleUnreadMessageCheck] 1분 후 N건 메시지 체크 시작");

    if (unreadMessageTimer) {
        clearTimeout(unreadMessageTimer);
    }

    unreadMessageTimer = setTimeout(() => {
        let elapsedTime = Date.now() - lastReadTime;
        console.log(`[scheduleUnreadMessageCheck] 경과 시간: ${elapsedTime / 1000}초`);

        if (elapsedTime >= 60000 && unreadMessages.length > 0 && !unreadNotificationVisible) {
            showUnreadMessageNotification();
        }
    }, 60000);
}

// 이상 알림 추가 (N건 메시지가 있으면 개별 알림 X, N만 증가)
function addAnomalyAlert(message) {
    console.log(`[addAnomalyAlert] 새로운 알림 추가: ${message}`);

    if (unreadNotificationVisible) {
        console.log("[addAnomalyAlert] N건 메시지 떠있는 상태 → 새로운 개별 알림 추가 안 함!");
        unreadMessages.push(message);
        unreadCount = unreadMessages.length;
        updateUnreadAnomalyCount();
        showUnreadMessageNotification(); // N 숫자만 증가
        return;
    }

    unreadMessages.push(message);
    unreadCount = unreadMessages.length;
    updateUnreadAnomalyCount();

    // 개별 이상 알림 표시
    const container = document.getElementById("anomalyAlertContainer");
    container.innerHTML = `
        <div class="anomaly-alert">
            <span>${message}</span>
            <button class="confirm-btn" onclick="markAnomalyAsRead(this, '${message}')">확인</button>
        </div>
    `;

    scheduleUnreadMessageCheck();
}

// "N건 메시지"에서 확인 버튼을 눌렀을 때 (다시 개별 알림 표시 가능)
function markUnreadMessagesAsRead() {
    console.log("[markUnreadMessagesAsRead] N건 메시지 확인됨 → 개별 알림 표시 가능");
    lastReadTime = Date.now();
    unreadNotificationVisible = false;
    unreadMessages = [];
    unreadCount = 0;
    stopAddingAlerts = false;
    updateUnreadAnomalyCount();

    document.getElementById("anomalyAlertContainer").innerHTML = "";
}

// 개별 이상 알림에서 확인 버튼을 눌렀을 때
function markAnomalyAsRead(button, message) {
    console.log(`[markAnomalyAsRead] 개별 알림 확인됨: ${message}`);
    button.parentElement.remove();
    lastReadTime = Date.now();
    unreadMessages = unreadMessages.filter(msg => msg !== message);
    unreadCount = unreadMessages.length;
    updateUnreadAnomalyCount();
}

// 5초마다 랜덤 메시지 생성 (테스트용)
setInterval(() => {
    let lines = ["A", "B", "C", "D"];
    let issues = ["불량 발생", "이상 동작 감지", "온도 이상 감지", "기계 오작동 감지", "압력 이상 감지"];

    let randomLine = lines[Math.floor(Math.random() * lines.length)];
    let randomIssue = issues[Math.floor(Math.random() * issues.length)];

    let randomMessage = `라인 ${randomLine}에서 ${randomIssue}!`;
    addAnomalyAlert(randomMessage);
}, 5000);
