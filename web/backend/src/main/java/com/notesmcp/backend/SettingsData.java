package com.notesmcp.backend;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * settings.json 的数据结构。
 *
 * 文件位于项目根,手工编辑或通过 API 修改,记录所有 provider 配置。
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class SettingsData {

    /** 笔记目录路径(分号分隔多目录,与 Python .env NOTES_DIR 等价) */
    @JsonProperty("notesDir")
    private String notesDir = "d:/Learn/AI/笔记";

    /** 当前使用的 provider: "ollama" | "openai" | "custom" */
    @JsonProperty("activeProvider")
    private String activeProvider = "ollama";

    /** Ollama 本地配置 */
    @JsonProperty("ollama")
    private ProviderConfig ollama = new ProviderConfig(
            "Ollama 本地",
            "http://127.0.0.1:11434",
            "",
            "qwen3:8b"
    );

    /** OpenAI 配置 */
    @JsonProperty("openai")
    private ProviderConfig openai = new ProviderConfig(
            "OpenAI",
            "https://api.openai.com/v1",
            "",
            "gpt-4o-mini"
    );

    /** 自定义 OpenAI 兼容端点(DeepSeek / Groq / vLLM / LM Studio 等) */
    @JsonProperty("custom")
    private ProviderConfig custom = new ProviderConfig(
            "自定义",
            "",
            "",
            ""
    );

    // ---- getters / setters ----

    public String getNotesDir() { return notesDir; }
    public void setNotesDir(String v) { this.notesDir = v; }

    public String getActiveProvider() { return activeProvider; }
    public void setActiveProvider(String v) { this.activeProvider = v; }

    public ProviderConfig getOllama() { return ollama; }
    public void setOllama(ProviderConfig v) { this.ollama = v; }

    public ProviderConfig getOpenai() { return openai; }
    public void setOpenai(ProviderConfig v) { this.openai = v; }

    public ProviderConfig getCustom() { return custom; }
    public void setCustom(ProviderConfig v) { this.custom = v; }

    /** 取当前活跃的 provider 配置 */
    public ProviderConfig activeConfig() {
        return switch (activeProvider) {
            case "openai" -> openai;
            case "custom" -> custom;
            default -> ollama;
        };
    }

    // ---- 序列化为 API 返回(隐藏敏感字段) ----

    public Map<String, Object> toApiResponse() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("notesDir", notesDir);
        map.put("activeProvider", activeProvider);
        map.put("ollama", maskConfig(ollama));
        map.put("openai", maskConfig(openai));
        map.put("custom", maskConfig(custom));
        return map;
    }

    private static Map<String, Object> maskConfig(ProviderConfig c) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("name", c.getName());
        m.put("baseUrl", c.getBaseUrl());
        // API key 脱敏：只显示后 4 位
        String key = c.getApiKey();
        if (key != null && key.length() > 4) {
            m.put("apiKey", "****" + key.substring(key.length() - 4));
        } else {
            m.put("apiKey", key == null || key.isEmpty() ? "" : "****");
        }
        m.put("selectedModel", c.getSelectedModel());
        m.put("hasKey", key != null && !key.isBlank());
        return m;
    }

    // ---- ProviderConfig ----

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class ProviderConfig {
        @JsonProperty("name")
        private String name;

        @JsonProperty("baseUrl")
        private String baseUrl;

        @JsonProperty("apiKey")
        private String apiKey;

        @JsonProperty("selectedModel")
        private String selectedModel;

        public ProviderConfig() {}

        public ProviderConfig(String name, String baseUrl, String apiKey, String selectedModel) {
            this.name = name;
            this.baseUrl = baseUrl;
            this.apiKey = apiKey;
            this.selectedModel = selectedModel;
        }

        public String getName() { return name; }
        public void setName(String v) { this.name = v; }

        public String getBaseUrl() { return baseUrl; }
        public void setBaseUrl(String v) { this.baseUrl = v; }

        public String getApiKey() { return apiKey; }
        public void setApiKey(String v) { this.apiKey = v; }

        public String getSelectedModel() { return selectedModel; }
        public void setSelectedModel(String v) { this.selectedModel = v; }
    }
}
