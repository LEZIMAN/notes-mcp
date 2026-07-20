package com.notesmcp.backend;

import io.modelcontextprotocol.client.McpSyncClient;
import io.modelcontextprotocol.spec.McpSchema.CallToolRequest;
import io.modelcontextprotocol.spec.McpSchema.CallToolResult;
import io.modelcontextprotocol.spec.McpSchema.Content;
import io.modelcontextprotocol.spec.McpSchema.ReadResourceRequest;
import io.modelcontextprotocol.spec.McpSchema.ReadResourceResult;
import io.modelcontextprotocol.spec.McpSchema.ResourceContents;
import io.modelcontextprotocol.spec.McpSchema.TextContent;
import io.modelcontextprotocol.spec.McpSchema.TextResourceContents;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 封装对 notes-mcp server 的直接 MCP 调用(不走 LLM)。
 *
 * Spring AI MCP client auto-config 把所有 stdio 连接的 McpSyncClient
 * 以 List 形式注入;本项目只有一个 notes-mcp 连接,取第一个即可。
 */
@Service
public class McpToolService {

    private static final Logger log = LoggerFactory.getLogger(McpToolService.class);

    private final McpSyncClient mcpClient;

    public McpToolService(List<McpSyncClient> mcpClients) {
        if (mcpClients.isEmpty()) {
            throw new IllegalStateException("没有可用的 MCP 客户端——检查 application.yml 的 MCP 连接配置");
        }
        this.mcpClient = mcpClients.get(0);
        log.info("McpToolService 已绑定 MCP 客户端:{}", mcpClient.getServerInfo());
    }

    /**
     * 调用 notes-mcp 的 search_notes 工具。
     */
    public String searchNotes(String query, int topK) {
        var request = new CallToolRequest("search_notes",
                Map.of("query", query, "top_k", topK));
        return callTool(request);
    }

    /**
     * 调用 notes-mcp 的 get_note 工具(按标题取整篇笔记)。
     */
    public String getNote(String title) {
        var request = new CallToolRequest("get_note", Map.of("title", title));
        return callTool(request);
    }

    /**
     * 调用 notes-mcp 的 list_topics 工具。
     */
    public String listTopics() {
        var request = new CallToolRequest("list_topics", Map.of());
        return callTool(request);
    }

    /**
     * 读取 notes://stats 资源(知识库统计)。
     */
    public String readStats() {
        var request = new ReadResourceRequest("notes://stats");
        var result = mcpClient.readResource(request);
        return extractResourceText(result);
    }

    // ---- 内部工具方法 ----

    /**
     * 调 MCP tool,从 CallToolResult 里提取第一个 text content。
     */
    private String callTool(CallToolRequest request) {
        try {
            CallToolResult result = mcpClient.callTool(request);
            return extractToolText(result);
        } catch (Exception e) {
            log.error("MCP tool 调用失败:{}", request.name(), e);
            throw new RuntimeException("MCP 工具调用失败: " + request.name(), e);
        }
    }

    /**
     * 从 CallToolResult 提取文本(取第一个 TextContent)。
     */
    private String extractToolText(CallToolResult result) {
        List<Content> contents = result.content();
        if (contents == null || contents.isEmpty()) {
            return "";
        }
        for (Content c : contents) {
            if (c instanceof TextContent tc) {
                return tc.text();
            }
        }
        return "";
    }

    /**
     * 从 ReadResourceResult 提取文本(取第一个 TextResourceContents)。
     */
    private String extractResourceText(ReadResourceResult result) {
        List<ResourceContents> contents = result.contents();
        if (contents == null || contents.isEmpty()) {
            return "{}";
        }
        for (ResourceContents rc : contents) {
            if (rc instanceof TextResourceContents trc) {
                return trc.text();
            }
        }
        return "{}";
    }
}
