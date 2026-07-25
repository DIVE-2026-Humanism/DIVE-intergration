package com.dive.backend.global.file;

import com.dive.backend.global.error.BusinessException;
import com.dive.backend.global.error.ErrorCode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

/** 이미지를 로컬 디스크에 저장하고, DB에는 접근 가능한 URL만 저장하는 방식 */
@Component
public class FileStorageService {

    @Value("${file.upload-dir}")
    private String uploadDir;

    @Value("${file.base-url}")
    private String baseUrl;

    public String store(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            return null;
        }

        try {
            Path dir = Path.of(uploadDir);
            Files.createDirectories(dir);

            String storedName = UUID.randomUUID() + extractExtension(file.getOriginalFilename());
            Path target = dir.resolve(storedName);
            file.transferTo(target);

            return baseUrl + "/" + storedName;
        } catch (IOException e) {
            throw new BusinessException(ErrorCode.FILE_UPLOAD_FAILED);
        }
    }

    private String extractExtension(String originalFilename) {
        if (originalFilename == null || !originalFilename.contains(".")) {
            return "";
        }
        return originalFilename.substring(originalFilename.lastIndexOf("."));
    }
}
