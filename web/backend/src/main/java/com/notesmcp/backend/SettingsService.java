package com.notesmcp.backend;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

/**
 * 管理 settings.json 的读写 + 模型列表拉取。
 *
 * 支持三种 provider:
 * - ollama: 本地模型,通过 Ollama REST API 获取模型列表
 * - openai: OpenAI API,通过 /v1/models 获取模型列表
 * - custom: 自定义 OpenAI 兼容端点(DeepSeek/Groq/vLLM 等)
 */
@Service
public class SettingsService {

    private static final Logger log = LoggerFactory.getLogger(SettingsService.class);
    private static final ObjectMapper JSON = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);

    private final Path settingsPath;
    private volatile SettingsData settings;

    public SettingsService(@Value("${notesmcp.settings.path:settings.json}") String path) {
        this.settingsPath = Path.of(path);
    }

    @PostConstruct
    public void load() {
        if (Files.exists(settingsPath)) {
            try {
                settings = JSON.readValue(settingsPath.toFile(), SettingsData.class);
                log.info("已加载 settings:{} activeProvider={}",
                        settingsPath.toAbsolutePath(), settings.getActiveProvider());
            } catch (IOException e) {
                log.warn("settings.json 读取失败,使用默认:{}", e.getMessage());
                settings = new SettingsData();
            }
        } else {
            settings = new SettingsData();
            save(); // 首次创建默认文件
            log.info("已创建默认 settings.json:{}", settingsPath.toAbsolutePath());
        }
    }

    /** 持久化到磁盘 */
    public synchronized void save() {
        try {
            JSON.writeValue(settingsPath.toFile(), settings);
        } catch (IOException e) {
            log.error("写入 settings.json 失败:{}", e.getMessage());
        }
    }

    // ---- 当前配置访问 ----

    public SettingsData getSettings() { return settings; }

    public String getActiveProvider() { return settings.getActiveProvider(); }

    public String getNotesDir() { return settings.getNotesDir(); }

    public void setNotesDir(String dir) { settings.setNotesDir(dir); save(); }

    public SettingsData.ProviderConfig getActiveConfig() {
        return settings.activeConfig();
    }

    public String getCurrentModel() {
        return getActiveConfig().getSelectedModel();
    }

    // ---- 切换 provider / 模型 ----

    public void setActiveProvider(String provider) {
        if (!List.of("ollama", "openai", "custom").contains(provider)) {
            throw new IllegalArgumentException("不支持的 provider: " + provider);
        }
        settings.setActiveProvider(provider);
        save();
        log.info("Provider 已切换:{}", provider);
    }

    public void setSelectedModel(String model) {
        getActiveConfig().setSelectedModel(model);
        save();
        log.info("模型已切换:{}", model);
    }

    // ---- 更新 provider 配置 ----

    public void updateProvider(String provider, SettingsData.ProviderConfig config) {
        switch (provider) {
            case "ollama" -> settings.setOllama(config);
            case "openai" -> settings.setOpenai(config);
            case "custom" -> settings.setCustom(config);
            default -> throw new IllegalArgumentException("不支持的 provider: " + provider);
        }
        save();
    }

    // ---- 拉取可用模型列表 ----

    public List<Map<String, Object>> fetchModels() {
        return switch (settings.getActiveProvider()) {
            case "openai", "custom" -> fetchOpenAiModels(getActiveConfig());
            default -> fetchOllamaModels(getActiveConfig());
        };
    }

    // -- Ollama --
    private List<Map<String, Object>> fetchOllamaModels(SettingsData.ProviderConfig config) {
        try {
            var client = org.springframework.web.client.RestClient.create(config.getBaseUrl());
            @SuppressWarnings("unchecked")
            var resp = client.get().uri("/api/tags").retrieve().body(Map.class);
            if (resp == null || !resp.containsKey("models")) return List.of();
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> models = (List<Map<String, Object>>) resp.get("models");
            return models.stream()
                    .map(m -> Map.<String, Object>of(
                            "name", m.getOrDefault("name", "unknown"),
                            "size", formatSize((Number) m.getOrDefault("size", 0))))
                    .toList();
        } catch (Exception e) {
            log.warn("Ollama 模型列表获取失败:{}", e.getMessage());
            return List.of();
        }
    }

    // -- OpenAI / Custom --
    private List<Map<String, Object>> fetchOpenAiModels(SettingsData.ProviderConfig config) {
        try {
            var client = org.springframework.web.client.RestClient.builder()
                    .defaultHeader("Authorization", "Bearer " + config.getApiKey())
                    .build();
            @SuppressWarnings("unchecked")
            var resp = client.get()
                    .uri(config.getBaseUrl() + "/models")
                    .retrieve()
                    .body(Map.class);
            if (resp == null || !resp.containsKey("data")) return List.of();
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> data = (List<Map<String, Object>>) resp.get("data");
            return data.stream()
                    .map(m -> Map.<String, Object>of(
                            "name", m.getOrDefault("id", "unknown"),
                            "ownedBy", m.getOrDefault("owned_by", "")))
                    .toList();
        } catch (Exception e) {
            log.warn("OpenAI 模型列表获取失败:{}", e.getMessage());
            return List.of();
        }
    }

    private static String formatSize(Number bytes) {
        long b = bytes.longValue();
        if (b > 1_000_000_000) return String.format("%.1f GB", b / 1_000_000_000.0);
        if (b > 1_000_000) return String.format("%.0f MB", b / 1_000_000.0);
        return b + " B";
    }
}
