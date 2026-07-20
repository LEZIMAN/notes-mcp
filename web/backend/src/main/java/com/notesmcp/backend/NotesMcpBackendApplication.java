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

    private static final Path SETTINGS_PATH = Path.of("settings.json");

    public static void main(String[] args) {
        // MCP 子进程需要 NOTES_DIR 环境变量来扫描笔记。
        // 在 Spring 启动前从 settings.json 读取,确保 stdio 连接创建时已就绪。
        String notesDir = readNotesDirFromSettings();
        System.setProperty("NOTES_DIR", notesDir);

        SpringApplication.run(NotesMcpBackendApplication.class, args);
    }

    private static String readNotesDirFromSettings() {
        try {
            if (Files.exists(SETTINGS_PATH)) {
                var json = new ObjectMapper().readTree(SETTINGS_PATH.toFile());
                if (json.has("notesDir")) {
                    String dir = json.get("notesDir").asText();
                    if (!dir.isBlank()) {
                        System.out.println("[notes-mcp] 从 settings.json 读取笔记目录: " + dir);
                        return dir;
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("[notes-mcp] 读取 settings.json 失败,使用默认笔记目录: " + e.getMessage());
        }
        return "d:/Learn/AI/笔记";
    }
}
