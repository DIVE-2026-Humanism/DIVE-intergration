package com.dive.backend.recommendation.domain;

public enum PolicyType {
    VULNERABLE("취약형"),
    STABLE("안정형");

    private final String label;

    PolicyType(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }
}
