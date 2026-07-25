package com.dive.backend.policy.domain;

import jakarta.persistence.*;
import lombok.*;

/**
 * 정책 유형(안정형/취약형) - 자체 분류 기준이 되는 소규모 참조 테이블.
 */
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "policy_type")
public class PolicyType {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(nullable = false, length = 20)
    private String name;

    @Column(length = 200)
    private String description;
}
