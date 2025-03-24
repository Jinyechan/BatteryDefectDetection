const typeChart = echarts.init(document.getElementById('typeChart'));
    const dailyChart = echarts.init(document.getElementById('dailyChart'));

    typeChart.setOption({
        animation: false,
        tooltip: { trigger: 'item' },
        series: [{
            type: 'pie',
            radius: '70%',
            data: [
                { value: 264951, name: '표면 스크래치' },
                { value: 4000, name: '치수 불량' },
                { value: 650, name: '기타' }
            ],
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowOffsetX: 0,
                    shadowColor: 'rgba(0, 0, 0, 0.5)'
                }
            }
        }]
    });

    dailyChart.setOption({
        animation: false,
        xAxis: { type: 'category', data: ['10/1', '10/2', '10/3', '10/4', '10/5'] },
        yAxis: { type: 'value' },
        series: [{
            data: [650, 680, 690, 700, 650],
            type: 'bar',
            color: '#2196F3'
        }]
    });

    