package com.dive.backend.gonggu.repository;

import com.dive.backend.gonggu.domain.Gonggu;
import com.dive.backend.gonggu.domain.Status;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDateTime;
import java.util.List;

public interface GongguRepository extends JpaRepository<Gonggu, Long> {

    List<Gonggu> findAllByOrderByCreatedAtDesc();

    List<Gonggu> findAllByStatusAndEndDateBefore(Status status, LocalDateTime endDate);
}
