// 슬라이더-숫자 동기화
    const sensitivitySlider = document.getElementById('sensitivitySlider');
    const sensitivityValue = document.getElementById('sensitivityValue');
    const falseSlider = document.getElementById('falseSlider');
    const falseValue = document.getElementById('falseValue');

    sensitivitySlider.oninput = () => sensitivityValue.value = sensitivitySlider.value;
    sensitivityValue.oninput = () => sensitivitySlider.value = sensitivityValue.value;
    falseSlider.oninput = () => falseValue.value = falseSlider.value;
    falseValue.oninput = () => falseSlider.value = falseValue.value;

    // 수정 모드 토글
    function toggleEditMode(enable) {
        const inputs = document.querySelectorAll('.criteria-item input:not([type="range"])');
        const applyBtn = document.querySelector('.criteria-btn-apply');
        const cancelBtn = document.querySelector('.criteria-btn-cancel');
        const editBtn = document.getElementById('editBtn');

        if (enable) {
            inputs.forEach(input => input.removeAttribute('readonly'));
            applyBtn.style.display = 'inline-block';
            cancelBtn.style.display = 'inline-block';
            editBtn.style.display = 'none';
        } else {
            inputs.forEach(input => input.setAttribute('readonly', true));
            applyBtn.style.display = 'none';
            cancelBtn.style.display = 'none';
            editBtn.style.display = 'inline-block';
        }
    }

    // 설정 저장
    function saveSettings() {
        if (confirm('변경 사항을 저장하시겠습니까?')) {
            toggleEditMode(false);
        }
    }