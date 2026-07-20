package com.notesmcp.backend;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * 笔记目录的文件树结构，前端树形展示用。
 */
public class FileTreeNode {
    public String name;        // 文件/文件夹名
    public String path;        // 绝对路径
    public String type;        // "folder" | "file"
    public String title;       // .md 文件的 H1 标题(仅文件有)
    public List<FileTreeNode> children;

    public FileTreeNode() {}

    public FileTreeNode(String name, String path, String type) {
        this.name = name;
        this.path = path;
        this.type = type;
        if ("folder".equals(type)) {
            this.children = new ArrayList<>();
        }
    }

    /** 扫描一个笔记根目录，返回该目录下的文件树 */
    public static List<FileTreeNode> scan(Path rootDir) throws IOException {
        List<FileTreeNode> result = new ArrayList<>();
        if (!Files.isDirectory(rootDir)) return result;

        try (var stream = Files.list(rootDir)) {
            List<Path> entries = stream.sorted(
                    Comparator.comparing(p -> !Files.isDirectory(p))  // 文件夹优先
            ).toList();

            for (Path entry : entries) {
                String name = entry.getFileName().toString();
                // 跳过隐藏文件和排除的目录
                if (name.startsWith(".") || isExcluded(name)) continue;

                if (Files.isDirectory(entry)) {
                    var folder = new FileTreeNode(name, entry.toString(), "folder");
                    folder.children = scan(entry);  // 递归
                    result.add(folder);
                } else if (name.endsWith(".md")) {
                    var file = new FileTreeNode(name, entry.toString(), "file");
                    file.title = readH1(entry);
                    result.add(file);
                }
            }
        }
        return result;
    }

    private static boolean isExcluded(String name) {
        return switch (name) {
            case "venv", ".venv", "node_modules", ".git",
                 "__pycache__", ".pytest_cache", ".mypy_cache",
                 ".ruff_cache", "data", "dist" -> true;
            default -> false;
        };
    }

    /** 读取 .md 文件的第一行 # 标题 */
    private static String readH1(Path mdPath) {
        try {
            String firstLine = Files.newBufferedReader(mdPath).readLine();
            if (firstLine != null) {
                return firstLine.replaceFirst("^#+\s*", "").trim();
            }
        } catch (IOException ignored) {}
        return mdPath.getFileName().toString().replace(".md", "");
    }

    /** 转为 API 返回的 Map 结构 */
    @SuppressWarnings("unchecked")
    public Map<String, Object> toMap() {
        Map<String, Object> map = new java.util.LinkedHashMap<>();
        map.put("name", name);
        map.put("path", path);
        map.put("type", type);
        if (title != null) map.put("title", title);
        if (children != null) {
            map.put("children", children.stream().map(FileTreeNode::toMap).toList());
        }
        return map;
    }
}
