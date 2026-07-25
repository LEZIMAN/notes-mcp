package com.notesmcp.backend;

import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.List;
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

        // 保存用户消息(当前轮)
        history.saveMessage(sessionId, "user", request.message());

        // 取最近 10 条(含当前 user),转 Spring AI Message 注入 LLM → 多轮上下文
        var recent = history.getRecentMessages(sessionId, 10);
        List<Message> messages = new ArrayList<>();
        for (var m : recent) {
            String role = (String) m.get("role");
            String content = (String) m.get("content");
            messages.add("assistant".equals(role)
                    ? (Message) new AssistantMessage(content)
                    : new UserMessage(content));
        }

        // 调用 LLM(带历史上下文)
        String reply = router.chat(messages);

        // 保存 AI 回复
        history.saveMessage(sessionId, "assistant", reply);

        return Map.of("reply", reply, "sessionId", sessionId);
    }

    /**
     * POST /api/chat/stream — 流式对话(SSE 打字机效果)。
     * 返回 text/event-stream,逐 chunk 推送;带多轮历史 + 对话记录保存。
     */
    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> chatStream(@RequestBody ChatRequest request) {
        String sessionId = request.sessionId().isEmpty()
                ? (String) history.createSession().get("id")
                : request.sessionId();
        history.saveMessage(sessionId, "user", request.message());

        var recent = history.getRecentMessages(sessionId, 10);
        List<Message> messages = new ArrayList<>();
        for (var m : recent) {
            String role = (String) m.get("role");
            String content = (String) m.get("content");
            messages.add("assistant".equals(role)
                    ? (Message) new AssistantMessage(content)
                    : new UserMessage(content));
        }

        StringBuilder full = new StringBuilder();
        return router.chatStream(messages)
                .doOnNext(full::append)
                .doOnComplete(() -> history.saveMessage(sessionId, "assistant", full.toString()))
                .concatWith(Flux.just("[DONE]"));
    }
}
