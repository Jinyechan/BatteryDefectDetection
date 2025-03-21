// 예측 불량률 추이 차트
    const trendCtx = document.getElementById('trendChart').getContext('2d');
    new Chart(trendCtx, {
        type: 'line',
        data: {
            labels: ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00'],
            datasets: [{
                label: '예측 불량률',
                data: [1.1, 1.5, 1.8, 2.0, 1.6, 2.5],
                borderColor: '#4dabf7',
                backgroundColor: 'rgba(77, 171, 247, 0.1)',
                tension: 0.4,
                fill: true
            }, {
                label: '실제 불량률',
                data: [1.0, 1.4, 1.9, 1.8, 1.7, 2.3],
                borderColor: '#82c91e',
                backgroundColor: 'transparent',
                tension: 0.4,
                borderDash: [5, 5]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 3,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            }
        }
    });

    // 불량 유형별 예측 차트
    const typeCtx = document.getElementById('typeChart').getContext('2d');
    new Chart(typeCtx, {
        type: 'doughnut',
        data: {
            labels: ['오염', '오염+손상'],
            datasets: [{
                data: [60, 40],
                backgroundColor: ['#5c7cfa', '#82c91e'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'right'
                }
            }
        }
    });