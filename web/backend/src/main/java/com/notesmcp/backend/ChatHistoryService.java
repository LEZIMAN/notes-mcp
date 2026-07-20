package com.notesmcp.backend;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.nio.file.Path;
import java.sql.*;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * SQLite 聊天记录持久化。
 *
 * 表:
 * - sessions: id, title, created_at, updated_at
 * - messages: id, session_id, role, content, created_at
 */
@Service
public class ChatHistoryService {

    private static final Logger log = LoggerFactory.getLogger(ChatHistoryService.class);
    private final String dbUrl;

    public ChatHistoryService(@Value("${notesmcp.chat.db:data/chat_history.db}") String dbPath) {
        // 与 settings.json 同目录
        Path settingsDir = Path.of("settings.json").getParent();
        if (settingsDir == null) settingsDir = Path.of("");
        this.dbUrl = "jdbc:sqlite:" + settingsDir.resolve(dbPath).toAbsolutePath();
    }

    @PostConstruct
    public void init() {
        try (var conn = connect(); var stmt = conn.createStatement()) {
            stmt.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '新对话',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """);
            stmt.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
                """);
            stmt.execute("PRAGMA foreign_keys = ON");
            log.info("聊天记录 SQLite 已就绪:{}", dbUrl);
        } catch (SQLException e) {
            log.error("初始化聊天记录数据库失败:{}", e.getMessage());
        }
    }

    // ===== Sessions =====

    public List<Map<String, Object>> listSessions() {
        var list = new ArrayList<Map<String, Object>>();
        try (var conn = connect();
             var stmt = conn.createStatement();
             var rs = stmt.executeQuery(
                     "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC")) {
            while (rs.next()) {
                var m = new LinkedHashMap<String, Object>();
                m.put("id", rs.getString("id"));
                m.put("title", rs.getString("title"));
                m.put("createdAt", rs.getLong("created_at"));
                m.put("updatedAt", rs.getLong("updated_at"));
                // 取最后一条消息预览
                m.put("preview", getLastPreview(conn, rs.getString("id")));
                list.add(m);
            }
        } catch (SQLException e) {
            log.error("列出会话失败:{}", e.getMessage());
        }
        return list;
    }

    public Map<String, Object> createSession() {
        String id = "sess-" + System.currentTimeMillis();
        long now = Instant.now().toEpochMilli();
        try (var conn = connect();
             var stmt = conn.prepareStatement(
                     "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)")) {
            stmt.setString(1, id);
            stmt.setString(2, "新对话");
            stmt.setLong(3, now);
            stmt.setLong(4, now);
            stmt.executeUpdate();
            var m = new LinkedHashMap<String, Object>();
            m.put("id", id);
            m.put("title", "新对话");
            m.put("createdAt", now);
            m.put("updatedAt", now);
            return m;
        } catch (SQLException e) {
            throw new RuntimeException("创建会话失败", e);
        }
    }

    public void deleteSession(String sessionId) {
        try (var conn = connect();
             var stmt = conn.prepareStatement("DELETE FROM sessions WHERE id = ?")) {
            stmt.setString(1, sessionId);
            stmt.executeUpdate();
        } catch (SQLException e) {
            log.error("删除会话失败:{}", e.getMessage());
        }
    }

    public List<Map<String, Object>> getMessages(String sessionId) {
        var list = new ArrayList<Map<String, Object>>();
        try (var conn = connect();
             var stmt = conn.prepareStatement(
                     "SELECT id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY id")) {
            stmt.setString(1, sessionId);
            var rs = stmt.executeQuery();
            while (rs.next()) {
                var m = new LinkedHashMap<String, Object>();
                m.put("role", rs.getString("role"));
                m.put("content", rs.getString("content"));
                m.put("createdAt", rs.getLong("created_at"));
                list.add(m);
            }
        } catch (SQLException e) {
            log.error("获取消息失败:{}", e.getMessage());
        }
        return list;
    }

    // ===== Messages =====

    public void saveMessage(String sessionId, String role, String content) {
        long now = Instant.now().toEpochMilli();
        try (var conn = connect()) {
            var stmt = conn.prepareStatement(
                    "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)");
            stmt.setString(1, sessionId);
            stmt.setString(2, role);
            stmt.setString(3, content);
            stmt.setLong(4, now);
            stmt.executeUpdate();

            // 更新 session 时间 + 自动标题(取第一条用户消息的前 30 字)
            var upd = conn.prepareStatement(
                    "UPDATE sessions SET updated_at = ?, title = CASE WHEN title = '新对话' THEN ? ELSE title END WHERE id = ?");
            upd.setLong(1, now);
            upd.setString(2, "user".equals(role) ? truncate(content, 30) : "新对话");
            upd.setString(3, sessionId);
            upd.executeUpdate();
        } catch (SQLException e) {
            log.error("保存消息失败:{}", e.getMessage());
        }
    }

    // ===== Helpers =====

    private Connection connect() throws SQLException {
        return DriverManager.getConnection(dbUrl);
    }

    private String getLastPreview(Connection conn, String sessionId) {
        try (var stmt = conn.prepareStatement(
                "SELECT content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 1")) {
            stmt.setString(1, sessionId);
            var rs = stmt.executeQuery();
            if (rs.next()) return truncate(rs.getString("content"), 50);
        } catch (SQLException ignored) {}
        return "";
    }

    private static String truncate(String s, int max) {
        if (s == null) return "";
        String cleaned = s.replace('\n', ' ').trim();
        return cleaned.length() > max ? cleaned.substring(0, max) + "..." : cleaned;
    }
}
