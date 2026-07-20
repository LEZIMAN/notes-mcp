package com.notesmcp.backend;

/**
 * /api/chat 请求体:{"message": "...", "sessionId": "sess-xxx"}。
 * sessionId 可选——不传则创建新会话。
 */
public record ChatRequest(String message, String sessionId) {
    public ChatRequest {
        if (sessionId == null) sessionId = "";
    }
}
