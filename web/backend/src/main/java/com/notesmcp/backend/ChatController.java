package com.notesmcp.backend;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 对话 REST 端点:前端 POST /api/chat,后端用 qwen3 + notes-mcp 工具回答。
 *
 * 关键:ChatClient + ToolCallbackProvider 实现 ReAct 式工具调用。
 * - ChatClient:Spring AI 的对话客户端(底层是 OllamaChatModel → qwen3)。
 * - ToolCallbackProvider:MCP client 连 notes-mcp 后,自动把 server 的 tools
 *   (search_notes / get_note / ...)注册进来。.tools() 一调,ToolCallingAdvisor
 *   自动跑「LLM 决定调哪个工具 → 调用 → 观察 → 再推理」的循环(等价 agent.py)。
 */
@RestController                  // 标记为 REST 控制器(返回 JSON,非页面)
@RequestMapping("/api")          // 类内所有端点前缀 /api
public class ChatController {

    private final ChatClient chatClient;
    private final ToolCallbackProvider toolCallbackProvider;

    // 构造器注入(Spring 自动注入两个 bean;均为 Spring AI starter 自动配置):
    //   - ChatClient.Builder:ollama starter 配置的(指向 qwen3)。
    //   - ToolCallbackProvider:mcp-client starter 连上 notes-mcp 后提供。
    public ChatController(ChatClient.Builder chatClientBuilder,
                          ToolCallbackProvider toolCallbackProvider) {
        this.chatClient = chatClientBuilder.build();
        this.toolCallbackProvider = toolCallbackProvider;
    }

    /**
     * POST /api/chat  body: {"message": "..."}
     * 用 qwen3 + notes-mcp 工具回答,返回 {"reply": "..."}。
     */
    @PostMapping("/chat")
    public ChatResponse chat(@RequestBody ChatRequest request) {
        String reply = chatClient.prompt()       // 起一个对话 prompt
                .user(request.message())          // 用户消息
                .tools(toolCallbackProvider)      // 挂上 notes-mcp 的所有工具
                .call()                           // 触发(含工具调用循环)
                .content();                       // 取最终文本
        return new ChatResponse(reply);
    }
}
