package com.dive.backend.global.error;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

/**
 * 범용 보일러플레이트용 최소 에러코드 세트.
 * runApp(github.com/proteinJ/runApp)의 도메인 특화 코드(GroupRunning, Spot, Shop 등)는
 * 이 프로젝트에서 사용하는 도메인이 아니라서 제외했다.
 *
 * 새 프로젝트에서 도메인을 추가할 때는 그 도메인 접두사로 코드를 이어서 추가한다.
 * 예: PawWalk이라면 "// Dog (반려견 관련)" 섹션에 DOG_NOT_FOUND(HttpStatus.NOT_FOUND, "D001", ...) 식으로.
 */
@Getter
@RequiredArgsConstructor
public enum ErrorCode {
    // Common (공통)
    INVALID_INPUT_VALUE(HttpStatus.BAD_REQUEST, "CM001", "올바르지 않은 입력값입니다."),
    METHOD_NOT_ALLOWED(HttpStatus.METHOD_NOT_ALLOWED, "CM002", "잘못된 HTTP 메서드 호출입니다."),
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "CM003", "서버 내부 오류가 발생했습니다."),
    FILE_UPLOAD_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "CM004", "파일 업로드에 실패했습니다."),

    // Member (회원 관련 — 이메일/비밀번호 기반 인증 공통)
    EMAIL_DUPLICATION(HttpStatus.BAD_REQUEST, "M001", "이미 존재하는 이메일입니다."),
    INVALID_LOGIN_CREDENTIALS(HttpStatus.BAD_REQUEST, "M003", "이메일 또는 비밀번호가 일치하지 않습니다."),
    MEMBER_NOT_FOUND(HttpStatus.NOT_FOUND, "M004", "존재하지 않는 회원입니다."),
    INVALID_PASSWORD(HttpStatus.BAD_REQUEST, "M005", "비밀번호가 올바르지 않습니다."),

    // Auth (인증 관련)
    AUTHENTICATION_FAILED(HttpStatus.UNAUTHORIZED, "A001", "인증에 실패하였습니다."),
    TOKEN_EXPIRED(HttpStatus.UNAUTHORIZED, "A002", "토큰이 만료되었습니다."),
    INVALID_TOKEN(HttpStatus.UNAUTHORIZED, "A003", "유효하지 않은 토큰입니다."),
    REFRESH_TOKEN_NOT_FOUND(HttpStatus.UNAUTHORIZED, "A004", "존재하지 않거나 만료된 refresh token입니다."),
    ACCESS_DENIED(HttpStatus.FORBIDDEN, "A005", "접근 권한이 없습니다."),

    // Policy (정책 관련)
    POLICY_NOT_FOUND(HttpStatus.NOT_FOUND, "P001", "존재하지 않는 정책입니다."),

    // Gonggu (공구 관련)
    GONGGU_NOT_FOUND(HttpStatus.NOT_FOUND, "G001", "존재하지 않는 공구입니다."),
    GONGGU_NOT_RECRUITING(HttpStatus.BAD_REQUEST, "G002", "모집 중인 공구가 아닙니다."),
    GONGGU_ALREADY_PAID(HttpStatus.BAD_REQUEST, "G003", "이미 결제한 공구입니다."),
    GONGGU_PAYMENT_NOT_FOUND(HttpStatus.NOT_FOUND, "G004", "존재하지 않는 결제 내역입니다."),
    KAKAOPAY_NOT_CONFIGURED(HttpStatus.SERVICE_UNAVAILABLE, "G005", "카카오페이 결제 키가 설정되지 않았습니다."),
    // Recommendation (정책 추천)
    KCB_NOT_CONNECTED(HttpStatus.BAD_REQUEST, "R001", "KCB 신용정보 연동이 필요합니다."),
    AI_FEEDBACK_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "R003", "신용 점수 산정 AI 서버에 연결할 수 없습니다."),
    NO_ELIGIBLE_POLICY(HttpStatus.NOT_FOUND, "R004", "조건에 맞는 정책이 없습니다."),
    DIAGNOSIS_NOT_FOUND(HttpStatus.NOT_FOUND, "R005", "진단 이력이 존재하지 않습니다."),

    // Notification (알림)
    NOTIFICATION_NOT_FOUND(HttpStatus.NOT_FOUND, "N001", "존재하지 않는 알림입니다.");

    private final HttpStatus httpStatus;
    private final String code;
    private final String message;
}
