package com.notesmcp.backend;

/**
 * /api/chat 响应体:{"reply": "RAG 是..."}。
 */
public record ChatResponse(String reply) {
}
