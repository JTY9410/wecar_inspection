// 공통 JavaScript 함수

// AJAX 요청 공통 함수
function ajaxRequest(url, method, data, successCallback, errorCallback) {
    $.ajax({
        url: url,
        method: method,
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(response) {
            if (response.success) {
                if (successCallback) successCallback(response);
            } else {
                alert(response.message || '오류가 발생했습니다.');
                if (errorCallback) errorCallback(response);
            }
        },
        error: function(xhr, status, error) {
            alert('서버 오류가 발생했습니다.');
            if (errorCallback) errorCallback({error: error});
        }
    });
}

// 날짜 포맷팅
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR') + ' ' + date.toLocaleTimeString('ko-KR', {hour: '2-digit', minute: '2-digit'});
}

// 확인 다이얼로그
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// 성공 메시지 표시
function showSuccess(message) {
    alert(message);
}

// 에러 메시지 표시
function showError(message) {
    alert(message);
}

// 테이블 행 편집 모드 전환
function toggleEditMode(row) {
    $(row).find('input, select, textarea').prop('disabled', function(i, val) {
        return !val;
    });
    $(row).toggleClass('editing');
}

// 폼 데이터 수집
function collectFormData(formSelector) {
    const data = {};
    $(formSelector).find('input, select, textarea').each(function() {
        const name = $(this).attr('name');
        if (name) {
            data[name] = $(this).val();
        }
    });
    return data;
}





