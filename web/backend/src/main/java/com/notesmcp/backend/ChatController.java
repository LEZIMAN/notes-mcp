package com.notesmcp.backend;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 对话 REST 端点:前端 POST /api/chat,自动创建/关联会话并保存消息。
 */
@RestController
@RequestMapping("/api")
public class ChatController {

    private final ProviderRouter router;
    private final ChatHistoryService history;

    public ChatController(ProviderRouter router, ChatHistoryService history) {
        this.router = router;
        this.history = history;
    }

    /**
     * POST /api/chat
     * body: {"message": "...", "sessionId": "sess-xxx(可选)"}
     * 返回 {"reply": "...", "sessionId": "..."}
     */
    @PostMapping("/chat")
    public Map<String, Object> chat(@RequestBody ChatRequest request) {
        // 带 sessionId 则复用,否则新建
        String sessionId = request.sessionId();
        if (sessionId.isEmpty()) {
            sessionId = (String) history.createSession().get("id");
        }

        // 保存用户消息
        history.saveMessage(sessionId, "user", request.message());

        // 调用 LLM
        String reply = router.chat(request.message());

        // 保存 AI 回复
        history.saveMessage(sessionId, "assistant", reply);

        return Map.of("reply", reply, "sessionId", sessionId);
    }
}
