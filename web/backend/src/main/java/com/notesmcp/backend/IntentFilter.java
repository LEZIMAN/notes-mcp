package com.notesmcp.backend;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.ollama.OllamaChatModel;
import org.springframework.ai.ollama.api.OllamaChatOptions;
import org.springframework.stereotype.Service;

/**
 * 意图过滤层:用本地 qwen3:8b(关 thinking)快速判断 query 是否与知识库无关。
 *
 * 为什么单独一层:
 * - rerank 只管排序,判不了"该不该回答"——无关 query(红烧肉/天气)仍走完整流程浪费 token
 * - 本层在主流程前拦截 irrelevant,省主模型调用(云端场景省钱)
 *
 * 为什么恒用 qwen3:8b + disableThinking:
 * - 意图层永远走本地(免费),不随主 provider 变(多模型 think 控制难,这里统一)
 * - disableThinking 关推理(0.6s),分类任务不需要思考(踩坑 #25:/no_think 无效,必须 API 层)
 *
 * 只判 normal vs irrelevant;ambiguous(术语堆砌)归 normal 走主模型兜底(小模型分不清)。
 * 详见 docs/意图过滤选型报告.md。
 */
@Service
public class IntentFilter {

    private static final Logger log = LoggerFactory.getLogger(IntentFilter.class);

    private static final String PROMPT =
            "知识库是AI/编程/机器学习/LLM/Agent 的学习笔记。判断用户查询意图,只输出一个英文词:" +
            "normal(只要涉及 AI/编程/机器学习/大模型/算法/计算机 的概念、术语、名词、问题——" +
            "哪怕简短或几个词并列——都算正常对话) " +
            "irrelevant(明确只问日常生活领域:菜谱做法/天气/体育赛事/股市行情/娱乐八卦/医疗咨询等)。" +
            "查询:";

    private final OllamaChatModel ollamaChatModel;

    public IntentFilter(OllamaChatModel ollamaChatModel) {
        this.ollamaChatModel = ollamaChatModel;
    }

    /**
     * 判断 query 是否与知识库无关(应拒答)。
     * @return true=无关(拦截至此);false=正常/歧义(走主流程)
     */
    public boolean isIrrelevant(String query) {
        try {
            String result = ChatClient.builder(ollamaChatModel).build().prompt()
                    .user(PROMPT + query)
                    .options(OllamaChatOptions.builder()
                            .model("qwen3:8b")
                            .disableThinking())
                    .call()
                    .content();
            boolean irrelevant = result != null && result.trim().toLowerCase().contains("irrelevant");
            log.info("意图过滤: query={}→{}", query, irrelevant ? "irrelevant(拦截)" : "normal(放行)");
            return irrelevant;
        } catch (Exception e) {
            log.warn("意图过滤失败,放行(走主模型): {}", e.getMessage());
            return false;  // 失败放行,不阻塞主流程
        }
    }
}
