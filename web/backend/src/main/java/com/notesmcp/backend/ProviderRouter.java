package com.notesmcp.backend;

import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.ollama.OllamaChatModel;
import org.springframework.ai.ollama.api.OllamaChatOptions;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

/**
 * 根据 settings.json 动态路由到对应的 ChatModel Provider。
 *
 * - ollama: 自动配置的 OllamaChatModel + 笔记检索工具
 * - openai/custom: 动态创建 OpenAiChatModel,apiKey/baseUrl 通过 options 注入
 */
@Service
public class ProviderRouter {

    private static final Logger log = LoggerFactory.getLogger(ProviderRouter.class);

    private final SettingsService settingsService;
    private final OllamaChatModel ollamaChatModel;
    private final ToolCallbackProvider toolCallbackProvider;

    private volatile OpenAiChatModel cachedOpenAiModel;
    private volatile String cachedKey = "";

    public ProviderRouter(SettingsService settingsService,
                          OllamaChatModel ollamaChatModel,
                          ToolCallbackProvider toolCallbackProvider) {
        this.settingsService = settingsService;
        this.ollamaChatModel = ollamaChatModel;
        this.toolCallbackProvider = toolCallbackProvider;
    }

    public String chat(List<Message> messages) {
        String provider = settingsService.getActiveProvider();
        SettingsData.ProviderConfig config = settingsService.getActiveConfig();
        String model = config.getSelectedModel();

        if (model == null || model.isBlank()) {
            return "⚠️ 当前 Provider「" + config.getName() + "」未选择模型。请打开设置 → 模型管理，选择一个可用模型。";
        }
        if (messages == null || messages.isEmpty()) {
            return "⚠️ 没有可发送的消息。";
        }
        log.info("chat: provider={}, model={}, 历史消息={} 条", provider, model, messages.size());

        try {
            if ("ollama".equals(provider)) {
                return ChatClient.builder(ollamaChatModel).build().prompt()
                        .messages(messages)
                        .options(OllamaChatOptions.builder().model(model))
                        .tools(toolCallbackProvider)
                        .call()
                        .content();
            } else {
                return ChatClient.builder(getOrCreateOpenAiModel(config)).build().prompt()
                        .messages(messages)
                        .options(OpenAiChatOptions.builder().model(model))
                        .tools(toolCallbackProvider)
                        .call()
                        .content();
            }
        } catch (Exception e) {
            log.error("对话失败: provider={}, error={}", provider, e.getMessage());
            return "❌ 对话失败：" + e.getMessage();
        }
    }

    /** 流式对话:逐 chunk 输出(打字机效果)。工具调用仍同步执行,最终回复流式。 */
    public Flux<String> chatStream(List<Message> messages) {
        String provider = settingsService.getActiveProvider();
        SettingsData.ProviderConfig config = settingsService.getActiveConfig();
        String model = config.getSelectedModel();
        if (model == null || model.isBlank()) {
            return Flux.just("⚠️ 当前 Provider「" + config.getName() + "」未选择模型。");
        }
        log.info("chatStream: provider={}, model={}, 历史消息={} 条", provider, model, messages.size());
        try {
            if ("ollama".equals(provider)) {
                return ChatClient.builder(ollamaChatModel).build().prompt()
                        .messages(messages)
                        .options(OllamaChatOptions.builder().model(model))
                        .tools(toolCallbackProvider)
                        .stream()
                        .content();
            }
            return ChatClient.builder(getOrCreateOpenAiModel(config)).build().prompt()
                    .messages(messages)
                    .options(OpenAiChatOptions.builder().model(model))
                    .tools(toolCallbackProvider)
                    .stream()
                    .content();
        } catch (Exception e) {
            log.error("流式对话失败: {}", e.getMessage());
            return Flux.just("❌ " + e.getMessage());
        }
    }

    private OpenAiChatModel getOrCreateOpenAiModel(SettingsData.ProviderConfig config) {
        String key = config.getBaseUrl() + "|" + config.getApiKey();
        if (cachedOpenAiModel != null && key.equals(cachedKey)) {
            return cachedOpenAiModel;
        }
        synchronized (this) {
            if (cachedOpenAiModel != null && key.equals(cachedKey)) {
                return cachedOpenAiModel;
            }
            log.info("创建 OpenAiChatModel: baseUrl={}", config.getBaseUrl());

            var defaultOptions = OpenAiChatOptions.builder()
                    .apiKey(config.getApiKey())
                    .baseUrl(config.getBaseUrl())
                    .build();

            cachedOpenAiModel = OpenAiChatModel.builder()
                    .options(defaultOptions)
                    .build();
            cachedKey = key;
            return cachedOpenAiModel;
        }
    }
}
