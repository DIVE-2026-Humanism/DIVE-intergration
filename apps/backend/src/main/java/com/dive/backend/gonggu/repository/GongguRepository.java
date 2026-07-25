package com.dive.backend.gonggu.repository;

import com.dive.backend.gonggu.domain.Gonggu;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface GongguRepository extends JpaRepository<Gonggu, Long> {

    List<Gonggu> findAllByOrderByCreatedAtDesc();
}
