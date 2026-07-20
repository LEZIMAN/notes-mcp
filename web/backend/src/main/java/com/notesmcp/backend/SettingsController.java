package com.notesmcp.backend;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Settings & 模型管理 REST API。
 *
 * GET  /api/settings         — 获取当前配置(密钥脱敏)
 * PUT  /api/settings         — 更新某个 provider 配置
 * POST /api/provider/select  — 切换 provider(body: {"provider":"ollama"})
 * GET  /api/models           — 获取当前 provider 可用模型列表
 * POST /api/models/select    — 选择模型(body: {"model":"qwen3:8b"})
 * POST /api/models/refresh   — 刷新模型列表
 */
@RestController
@RequestMapping("/api")
public class SettingsController {

    private static final Logger log = LoggerFactory.getLogger(SettingsController.class);
    private final SettingsService settingsService;

    public SettingsController(SettingsService settingsService) {
        this.settingsService = settingsService;
    }

    // ============ Settings ============

    /** GET /api/settings — 获取完整配置(密钥脱敏) */
    @GetMapping("/settings")
    public ResponseEntity<Map<String, Object>> getSettings() {
        return ResponseEntity.ok(settingsService.getSettings().toApiResponse());
    }

    /** PUT /api/settings — 更新配置(provider 配置或 notesDir) */
    @PutMapping("/settings")
    public ResponseEntity<Map<String, Object>> updateSettings(@RequestBody Map<String, Object> body) {
        // 更新 notesDir
        if (body.containsKey("notesDir") && !body.containsKey("provider")) {
            String notesDir = (String) body.get("notesDir");
            if (notesDir == null || notesDir.isBlank()) {
                return ResponseEntity.badRequest().body(Map.of("error", "notesDir 不能为空"));
            }
            settingsService.setNotesDir(notesDir);
            log.info("笔记目录已更新:{} (需重启后端生效)", notesDir);
            return ResponseEntity.ok(Map.of(
                    "message", "笔记目录已保存。修改笔记目录需重启后端才能生效",
                    "notesDir", notesDir,
                    "requiresRestart", true
            ));
        }

        // 更新 provider 配置
        String provider = (String) body.get("provider");
        if (provider == null || !List.of("ollama", "openai", "custom").contains(provider)) {
            return ResponseEntity.badRequest().body(Map.of("error", "provider 必须是 ollama/openai/custom"));
        }

        SettingsData.ProviderConfig config = new SettingsData.ProviderConfig(
                (String) body.getOrDefault("name", ""),
                (String) body.getOrDefault("baseUrl", ""),
                // 如果 apiKey 以 **** 开头(前端脱敏),保留原值
                resolveApiKey(provider, (String) body.getOrDefault("apiKey", "")),
                (String) body.getOrDefault("selectedModel", "")
        );
        settingsService.updateProvider(provider, config);
        log.info("Settings 已更新: provider={}", provider);
        return ResponseEntity.ok(Map.of("message", "配置已保存", "provider", provider));
    }

    /** POST /api/provider/select — 切换 provider */
    @PostMapping("/provider/select")
    public ResponseEntity<Map<String, Object>> selectProvider(@RequestBody Map<String, String> body) {
        String provider = body.get("provider");
        if (provider == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "缺少 provider 字段"));
        }
        settingsService.setActiveProvider(provider);
        return ResponseEntity.ok(Map.of(
                "activeProvider", provider,
                "message", "已切换为 " + provider
        ));
    }

    // ============ Models ============

    /** GET /api/models — 当前 provider 可用模型 + 当前选中 */
    @GetMapping("/models")
    public ResponseEntity<Map<String, Object>> listModels() {
        return ResponseEntity.ok(Map.of(
                "provider", settingsService.getActiveProvider(),
                "current", settingsService.getCurrentModel(),
                "models", settingsService.fetchModels()
        ));
    }

    /** POST /api/models/select — 切换模型 */
    @PostMapping("/models/select")
    public ResponseEntity<Map<String, Object>> selectModel(@RequestBody Map<String, String> body) {
        String model = body.get("model");
        if (model == null || model.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "缺少 model 字段"));
        }
        settingsService.setSelectedModel(model);
        return ResponseEntity.ok(Map.of("current", model, "message", "模型已切换"));
    }

    /** POST /api/models/refresh — 刷新模型列表(重新从 provider 拉取) */
    @PostMapping("/models/refresh")
    public ResponseEntity<Map<String, Object>> refreshModels() {
        var models = settingsService.fetchModels();
        return ResponseEntity.ok(Map.of(
                "provider", settingsService.getActiveProvider(),
                "current", settingsService.getCurrentModel(),
                "models", models
        ));
    }

    // ============ 内部 ============

    /** 如果前端传来脱敏值(****开头),保留已存储的真实 key */
    private String resolveApiKey(String provider, String incoming) {
        if (incoming.startsWith("****")) {
            return settingsService.getSettings().activeConfig().getApiKey();
        }
        return incoming;
    }
}
