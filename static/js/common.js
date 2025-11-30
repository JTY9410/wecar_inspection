// 공통 JavaScript 함수

// AJAX 요청 헬퍼
function ajaxRequest(url, method, data, successCallback, errorCallback) {
    const options = {
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
            console.error('AJAX Error:', error);
            alert('요청 처리 중 오류가 발생했습니다.');
            if (errorCallback) errorCallback({error: error});
        }
    };
    
    if (method === 'GET') {
        options.data = data;
        options.contentType = 'application/x-www-form-urlencoded';
    }
    
    $.ajax(options);
}

// 날짜 포맷팅
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('ko-KR');
}

function formatDateTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleString('ko-KR');
}

// 테이블 행 편집 모드 토글
function toggleEditMode(rowId, editBtn, saveBtn, cancelBtn) {
    const row = $(`#row-${rowId}`);
    const isEditing = row.hasClass('editing');
    
    if (isEditing) {
        row.removeClass('editing');
        row.find('input, select, textarea').prop('disabled', true);
        editBtn.show();
        saveBtn.hide();
        if (cancelBtn) cancelBtn.hide();
    } else {
        row.addClass('editing');
        row.find('input, select, textarea').prop('disabled', false);
        editBtn.hide();
        saveBtn.show();
        if (cancelBtn) cancelBtn.show();
    }
}

// 폼 데이터 수집
function collectFormData(formSelector) {
    const data = {};
    $(formSelector).find('input, select, textarea').each(function() {
        const $el = $(this);
        const name = $el.attr('name');
        if (name) {
            if ($el.attr('type') === 'checkbox') {
                data[name] = $el.is(':checked');
            } else {
                data[name] = $el.val();
            }
        }
    });
    return data;
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

// 오류 메시지 표시
function showError(message) {
    alert(message);
}

// 로딩 버튼 토글
function toggleLoadingButton(button, isLoading, originalText) {
    if (isLoading) {
        button.prop('disabled', true);
        button.data('original-text', originalText || button.html());
        button.html('<span class="spinner-border spinner-border-sm"></span> 처리 중...');
    } else {
        button.prop('disabled', false);
        button.html(button.data('original-text') || originalText);
    }
}

// URL 파라미터 가져오기
function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

// 날짜 범위 기본값 설정
function setDefaultDateRange(days = 7) {
    const today = new Date();
    const startDate = new Date(today);
    startDate.setDate(today.getDate() - days);
    
    const formatDate = (date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };
    
    if (!$('#start_date').val()) {
        $('#start_date').val(formatDate(startDate));
    }
    if (!$('#end_date').val()) {
        $('#end_date').val(formatDate(today));
    }
}

// 페이지 로드 시 날짜 범위 설정
$(document).ready(function() {
    // 날짜 입력 필드가 있으면 기본값 설정
    if ($('#start_date').length && $('#end_date').length) {
        setDefaultDateRange(7);
    }
});


