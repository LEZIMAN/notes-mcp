package com.notesmcp.backend;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 笔记相关的 REST 端点(直接调 notes-mcp 工具,不走 LLM)。
 *
 * 与 ChatController 分工:
 * - ChatController: POST /api/chat 走 ChatClient + LLM 智能回答
 * - NotesController: GET 端点直接调 MCP 工具,返回原始数据(省 token)
 *
 * 对应 MCP 能力:
 * - stats  → notes://stats resource
 * - topics → list_topics tool
 * - notes  → get_note tool
 * - search → search_notes tool
 */
@RestController
@RequestMapping("/api")
public class NotesController {

    private static final Logger log = LoggerFactory.getLogger(NotesController.class);

    private final McpToolService mcp;
    private final SettingsService settingsService;

    public NotesController(McpToolService mcp, SettingsService settingsService) {
        this.mcp = mcp;
        this.settingsService = settingsService;
    }

    /**
     * GET /api/stats
     * 知识库统计:笔记数、chunk 数、嵌入模型、笔记目录。
     */
    @GetMapping("/stats")
    public ResponseEntity<String> stats() {
        log.info("GET /api/stats");
        String json = mcp.readStats();
        return ResponseEntity.ok(json);
    }

    /**
     * GET /api/topics
     * 列出所有笔记标题(markdown H1),每行一条。
     */
    @GetMapping("/topics")
    public ResponseEntity<String> topics() {
        log.info("GET /api/topics");
        String text = mcp.listTopics();
        return ResponseEntity.ok(text);
    }

    /**
     * GET /api/notes/{title}
     * 按标题取整篇笔记原文(markdown)。
     */
    @GetMapping("/notes/{title}")
    public ResponseEntity<Map<String, Object>> noteByTitle(@PathVariable String title) {
        log.info("GET /api/notes/{}", title);
        String content = mcp.getNote(title);
        return ResponseEntity.ok(Map.of(
                "title", title,
                "content", content
        ));
    }

    /**
     * GET /api/search?q=xxx&top_k=5
     * 直接搜索笔记(不走 LLM),返回带出处的片段。
     */
    @GetMapping("/search")
    public ResponseEntity<Map<String, Object>> search(
            @RequestParam("q") String query,
            @RequestParam(value = "top_k", defaultValue = "5") int topK
    ) {
        log.info("GET /api/search q={} top_k={}", query, topK);
        String result = mcp.searchNotes(query, topK);
        return ResponseEntity.ok(Map.of(
                "query", query,
                "result", result
        ));
    }

    /**
     * GET /api/notes/tree
     * 扫描笔记目录,返回文件夹树结构(前端侧边栏树形展示用)。
     * 支持多层嵌套、文件夹优先排序。
     */
    @GetMapping("/notes/tree")
    public ResponseEntity<Map<String, Object>> fileTree() {
        String raw = settingsService.getNotesDir();
        List<Map<String, Object>> trees = new ArrayList<>();

        for (String dir : raw.split(";")) {
            String trimmed = dir.trim();
            if (trimmed.isEmpty()) continue;
            try {
                Path root = Path.of(trimmed);
                var rootNode = new FileTreeNode(
                        root.getFileName() != null ? root.getFileName().toString() : trimmed,
                        root.toAbsolutePath().toString(),
                        "folder"
                );
                rootNode.children = FileTreeNode.scan(root);
                trees.add(rootNode.toMap());
            } catch (IOException e) {
                log.warn("扫描目录失败:{} {}", trimmed, e.getMessage());
                trees.add(Map.of("name", trimmed, "path", trimmed,
                        "type", "folder", "children", List.of(),
                        "error", e.getMessage()));
            }
        }

        return ResponseEntity.ok(Map.of(
                "notesDir", raw,
                "trees", trees
        ));
    }
}
