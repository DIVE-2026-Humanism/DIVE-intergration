package com.dive.backend.policy.service;

import com.dive.backend.policy.domain.Policy;

import java.time.LocalDate;
import java.time.DateTimeException;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 원본 API의 문자열 신청기간에서 종료일을 보수적으로 해석한다. */
public final class PolicyApplicationPeriod {
    private static final Pattern DATE = Pattern.compile("(20\\d{2})[.\\-/년\\s]*(\\d{1,2})[.\\-/월\\s]*(\\d{1,2})");

    private PolicyApplicationPeriod() { }

    /**
     * 상시/미기재/종료일을 해석할 수 없는 값은 숨기지 않는다.
     * 기간에 날짜가 두 개 이상 있을 때 마지막 날짜만 종료일로 보고, 오늘 이전이면 마감으로 판단한다.
     */
    public static boolean isOpen(Policy policy) {
        return isOpen(policy.getAplyYmd(), LocalDate.now());
    }

    static boolean isOpen(String applicationPeriod, LocalDate today) {
        if (applicationPeriod == null || applicationPeriod.isBlank() || applicationPeriod.contains("상시")) return true;
        List<LocalDate> dates = dates(applicationPeriod);
        if (dates.size() < 2) return true;
        return !dates.get(dates.size() - 1).isBefore(today);
    }

    private static List<LocalDate> dates(String value) {
        List<LocalDate> result = new ArrayList<>();
        Matcher matcher = DATE.matcher(value);
        while (matcher.find()) {
            try {
                result.add(LocalDate.of(Integer.parseInt(matcher.group(1)), Integer.parseInt(matcher.group(2)), Integer.parseInt(matcher.group(3))));
            } catch (DateTimeException | NumberFormatException ignored) { }
        }
        return result;
    }
}
