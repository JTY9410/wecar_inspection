// 공통 JavaScript 함수 - 모바일 최적화

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
                showToast(response.message || '오류가 발생했습니다.', 'error');
                if (errorCallback) errorCallback(response);
            }
        },
        error: function(xhr, status, error) {
            console.error('AJAX Error:', error);
            showToast('요청 처리 중 오류가 발생했습니다.', 'error');
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

// 확인 다이얼로그 (모바일 친화적)
function confirmAction(message, callback) {
    if (window.confirm(message)) {
        callback();
    }
}

// Toast 메시지 표시 (모바일 최적화)
function showToast(message, type = 'info') {
    // 기존 toast 제거
    $('.toast-container').remove();
    
    const toastContainer = $('<div class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
    const toastId = 'toast-' + Date.now();
    
    const bgClass = {
        'success': 'bg-success',
        'error': 'bg-danger',
        'warning': 'bg-warning',
        'info': 'bg-info'
    }[type] || 'bg-info';
    
    const toast = $(`
        <div id="${toastId}" class="toast ${bgClass} text-white" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header ${bgClass} text-white border-0">
                <strong class="me-auto">
                    ${type === 'success' ? '<i class="bi bi-check-circle"></i>' : ''}
                    ${type === 'error' ? '<i class="bi bi-x-circle"></i>' : ''}
                    ${type === 'warning' ? '<i class="bi bi-exclamation-triangle"></i>' : ''}
                    ${type === 'info' ? '<i class="bi bi-info-circle"></i>' : ''}
                </strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `);
    
    toastContainer.append(toast);
    $('body').append(toastContainer);
    
    const bsToast = new bootstrap.Toast(toast[0], {
        autohide: true,
        delay: 3000
    });
    bsToast.show();
    
    toast.on('hidden.bs.toast', function() {
        toastContainer.remove();
    });
}

// 성공 메시지 표시
function showSuccess(message) {
    showToast(message, 'success');
}

// 오류 메시지 표시
function showError(message) {
    showToast(message, 'error');
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

// 모바일 터치 이벤트 처리
function setupTouchEvents() {
    // 스와이프 감지
    let touchStartX = 0;
    let touchEndX = 0;
    
    document.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });
    
    document.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
    }, { passive: true });
    
    function handleSwipe() {
        const swipeThreshold = 50;
        const diff = touchStartX - touchEndX;
        
        if (Math.abs(diff) > swipeThreshold) {
            // 스와이프 이벤트 발생
            $(document).trigger('swipe', [diff > 0 ? 'left' : 'right']);
        }
    }
}

// 모바일에서 입력 필드 포커스 시 줌 방지
function preventZoomOnFocus() {
    if (/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)) {
        const inputs = document.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            if (input.style.fontSize !== '16px') {
                input.style.fontSize = '16px';
            }
        });
    }
}

// 테이블 모바일 최적화
function optimizeTableForMobile() {
    if (window.innerWidth <= 768) {
        $('.table-wrapper').each(function() {
            const $wrapper = $(this);
            if (!$wrapper.data('scroll-init')) {
                $wrapper.data('scroll-init', true);
                // 스크롤 인디케이터 추가
                const $indicator = $('<div class="scroll-indicator"><i class="bi bi-arrow-left-right"></i> 좌우로 스크롤</div>');
                $wrapper.before($indicator);
                
                // 스크롤 시 인디케이터 숨기기
                let scrollTimeout;
                $wrapper.on('scroll', function() {
                    $indicator.fadeOut();
                    clearTimeout(scrollTimeout);
                    scrollTimeout = setTimeout(function() {
                        if ($wrapper.scrollLeft() === 0) {
                            $indicator.fadeIn();
                        }
                    }, 2000);
                });
            }
        });
    }
}

// 페이지 로드 시 초기화
$(document).ready(function() {
    // 날짜 입력 필드가 있으면 기본값 설정
    if ($('#start_date').length && $('#end_date').length) {
        setDefaultDateRange(7);
    }
    
    // 모바일 최적화
    setupTouchEvents();
    preventZoomOnFocus();
    optimizeTableForMobile();
    
    // 리사이즈 이벤트
    $(window).on('resize', function() {
        optimizeTableForMobile();
    });
    
    // 네비게이션 바 모바일 최적화
    $('.navbar-toggler').on('click', function() {
        $(this).toggleClass('active');
    });
    
    // 모바일에서 네비게이션 링크 클릭 시 자동 닫기
    $('.navbar-nav .nav-link').on('click', function() {
        if (window.innerWidth < 992) {
            $('.navbar-collapse').collapse('hide');
        }
    });
    
    // 부드러운 스크롤
    $('a[href^="#"]').on('click', function(e) {
        const target = $(this.getAttribute('href'));
        if (target.length) {
            e.preventDefault();
            $('html, body').animate({
                scrollTop: target.offset().top - 80
            }, 500);
        }
    });
    
    // 폼 제출 시 로딩 표시
    $('form').on('submit', function() {
        const $submitBtn = $(this).find('button[type="submit"]');
        if ($submitBtn.length) {
            toggleLoadingButton($submitBtn, true);
        }
    });
});

// PWA 설치 프롬프트 (선택적)
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    // 설치 버튼 표시 로직 추가 가능
});

// 오프라인 감지
window.addEventListener('online', function() {
    showToast('인터넷 연결이 복구되었습니다.', 'success');
});

window.addEventListener('offline', function() {
    showToast('인터넷 연결이 끊어졌습니다. 오프라인 모드로 전환됩니다.', 'warning');
});
