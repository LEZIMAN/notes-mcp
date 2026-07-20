package com.notesmcp.backend;

/**
 * /api/chat 请求体:{"message": "用笔记解释 RAG"}。
 * record 是 Java 的不可变数据类(自动生成构造器/访问器/equals),适合做 DTO。
 */
public record ChatRequest(String message) {
}
