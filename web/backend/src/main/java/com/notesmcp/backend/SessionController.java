package com.notesmcp.backend;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 会话 CRUD REST API。
 */
@RestController
@RequestMapping("/api")
public class SessionController {

    private final ChatHistoryService history;

    public SessionController(ChatHistoryService history) {
        this.history = history;
    }

    /** GET /api/sessions — 列出所有会话 */
    @GetMapping("/sessions")
    public ResponseEntity<Object> listSessions() {
        return ResponseEntity.ok(Map.of("sessions", history.listSessions()));
    }

    /** POST /api/sessions — 新建会话 */
    @PostMapping("/sessions")
    public ResponseEntity<Object> createSession() {
        return ResponseEntity.ok(history.createSession());
    }

    /** GET /api/sessions/{id} — 获取会话消息 */
    @GetMapping("/sessions/{id}")
    public ResponseEntity<Object> getSession(@PathVariable String id) {
        var messages = history.getMessages(id);
        if (messages.isEmpty()) {
            // 可能是空会话,仍返回
        }
        return ResponseEntity.ok(Map.of("sessionId", id, "messages", messages));
    }

    /** DELETE /api/sessions/{id} — 删除会话 */
    @DeleteMapping("/sessions/{id}")
    public ResponseEntity<Object> deleteSession(@PathVariable String id) {
        history.deleteSession(id);
        return ResponseEntity.ok(Map.of("message", "已删除"));
    }
}
