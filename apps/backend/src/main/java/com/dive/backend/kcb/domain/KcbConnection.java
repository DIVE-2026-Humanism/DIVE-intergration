package com.dive.backend.kcb.domain;

import com.dive.backend.member.domain.Member;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import java.time.LocalDateTime;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Table(name = "kcb_connection")
public class KcbConnection {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "member_id", nullable = false) private Member member;
    @Column(nullable = false, columnDefinition = "TEXT") private String kcbRecordJson;
    @Column(columnDefinition = "TEXT") private String aiResponseJson;
    private Double compositeStabilityScore;
    private String economicType;
    private String economicTypeName;
    private String majorClass;
    private Double typeConfidence;
    @Column(nullable = false) private boolean dummy;
    @CreationTimestamp @Column(nullable = false, updatable = false) private LocalDateTime createdAt;

    public void updateAiAnalysis(String responseJson, double score, String type, String typeName,
                                 String classification, double confidence) {
        this.aiResponseJson = responseJson;
        this.compositeStabilityScore = score;
        this.economicType = type;
        this.economicTypeName = typeName;
        this.majorClass = classification;
        this.typeConfidence = confidence;
    }
}
