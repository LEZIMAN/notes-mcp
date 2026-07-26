package com.notesmcp.backend;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Spring Boot 启动类。
 * 在 Spring 容器启动前读取 settings.json 的 notesDir,
 * 注入系统属性供 application.yml 的 MCP stdio env 引用。
 */
@SpringBootApplication
public class NotesMcpBackendApplication {

    public static void main(String[] args) {
        // MCP 子进程需要 NOTES_DIR 环境变量来扫描笔记。
        // 在 Spring 启动前从 settings.json 读取,确保 stdio 连接创建时已就绪。
        String notesDir = readNotesDirFromSettings();
        System.setProperty("NOTES_DIR", notesDir);

        SpringApplication.run(NotesMcpBackendApplication.class, args);
    }

    /** 从 cwd 向上查找 settings.json(mvn run 的 cwd 是 web/backend,settings.json 在项目根)。 */
    private static Path findSettingsFile() {
        Path dir = Path.of("").toAbsolutePath();
        for (int i = 0; i < 6; i++) {
            Path candidate = dir.resolve("settings.json");
            if (Files.exists(candidate)) {
                return candidate;
            }
            dir = dir.getParent();
            if (dir == null) {
                break;
            }
        }
        return null;
    }

    private static String readNotesDirFromSettings() {
        Path settings = findSettingsFile();
        if (settings != null) {
            try {
                var json = new ObjectMapper().readTree(settings.toFile());
                if (json.has("notesDir")) {
                    String dir = json.get("notesDir").asText();
                    if (!dir.isBlank()) {
                        System.out.println("[notes-mcp] 从 " + settings + " 读取笔记目录: " + dir);
                        return dir;
                    }
                }
            } catch (Exception e) {
                System.out.println("[notes-mcp] 读取 settings.json 失败,使用默认: " + e.getMessage());
            }
        }
        return "d:/Learn/AI/AI笔记";  // 默认(笔记目录已改名 笔记→AI笔记)
    }
}
