function syncRangeWithNumber(rangeId, numberId) {
        const range = document.querySelector(rangeId);
        const number = document.querySelector(numberId);
        range.addEventListener('input', function(e) {
            number.value = e.target.value;
        });
        number.addEventListener('input', function(e) {
            range.value = e.target.value;
        });
    }
    syncRangeWithNumber('#id-108', '#sensitivity-number');
    syncRangeWithNumber('#id-113', '#false-detection-number');

    const lineChart = echarts.init(document.getElementById('lineChart'));
    lineChart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['불량률'] },
        xAxis: { type: 'category', data: ['라인 A', '라인 B', '라인 C'] },
        yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
        series: [{
            name: '불량률',
            type: 'bar',
            data: [2.5, 1.9, 2.2],
            itemStyle: { color: '#e74c3c', borderRadius: [10, 10, 0, 0] }
        }]
    });

    window.addEventListener('resize', function() {
        lineChart.resize();
    });

    function openNotificationModal() {
        document.getElementById('notificationModal').classList.remove('hidden');
    }

    function closeNotificationModal() {
        document.getElementById('notificationModal').classList.add('hidden');
    }