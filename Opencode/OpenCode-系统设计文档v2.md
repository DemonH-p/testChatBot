# 智能体应用系统设计文档

## 1. 文档概述

本文档为智能体应用的系统设计文档，详细描述了系统的API设计、数据库设计、模块接口定义、流程设计和安全实现等具体内容。本文档与架构设计文档配合使用，为开发团队提供完整的实施指导，确保各模块的设计细节清晰、接口规范统一、集成方式明确。

本文档基于100+对话场景case分析结果，针对多意图处理、打断场景、情感交互、MCP/SKILLs扩展等新增需求进行了系统设计层面的详细设计。文档涵盖了从用户请求到最终响应的完整链路，详细说明了每个环节的数据流转、处理逻辑和交互接口。

系统设计文档的目标读者包括后端开发工程师、前端开发工程师、测试工程师和运维工程师。文档内容涵盖了用户请求处理、多意图识别、打断管理、任务调度、响应融合等核心模块的详细设计。

## 2. API设计规范

### 2.1 设计原则

API设计遵循以下核心原则，以确保系统的可用性、可扩展性和易用性。首先是语义明确原则，每个API都有清晰的业务含义，命名规范统一，动词+名词的结构直观表达操作意图。其次是版本化管理原则，API采用URL路径版本控制方式，如/api/v1/，确保版本升级时向后兼容，允许平滑迁移。第三是安全性优先原则，所有涉及用户数据的API都需要身份认证，敏感操作需要额外授权验证。第四是幂等性设计原则，对于会产生副作用的操作（如修改数据），需要支持幂等处理，避免重复请求导致的数据不一致。

API响应采用统一的格式封装，包括状态码、消息体和元数据。成功响应返回200系列状态码，客户端错误返回400系列状态码，服务端错误返回500系列状态码。每个响应都包含request_id字段，用于问题排查和链路追踪。分页查询采用标准的offset+limit方式，并返回总记录数供客户端展示。

### 2.2 核心API定义

#### 2.2.1 对话API

对话API是系统的核心接口，负责处理用户的对话请求和流式响应。接口采用RESTful风格，支持同步和流式两种响应模式。

```
POST /api/v1/chat
```

请求参数包括：session_id为会话ID，用于关联上下文历史，如果为空则创建新会话；user_id为用户ID，必须提供用于身份验证；input为用户输入的文本内容；modality为输入类型，默认为text，可选值为text、image、mixed；images为图片URL列表，当modality为image或mixed时需要提供，每个图片为oss或cdn的访问URL；stream为布尔值，默认为true，表示开启流式输出；interrupt为布尔值，表示是否为打断请求，默认为false。

响应格式采用Server-Sent Events（SSE）方式，每个片段包含：segment为本次输出的文本片段；trace_id为请求追踪ID，用于关联日志和监控；segment_id为片段序号，从1开始递增；is_final为布尔值，表示是否为最后一个片段；model标识产生此片段的模型，可选值为talker、thinker、fusion；is_interrupt_marker为布尔值，表示是否为打断标记。

对于非流式请求，响应格式为：text为完整回答文本；intents为识别的意图列表，每个意图包含intent_type、entities、confidence；task_state为当前任务状态，用于支持打断恢复。

#### 2.2.2 会话管理API

会话管理API提供会话的创建、查询、更新和删除功能，支持多会话管理和会话历史查看。

```
POST /api/v1/sessions
```

创建会话请求包括：user_id为用户ID；title为会话标题，可选系统自动生成；metadata为扩展元数据，可存储客户端信息。

响应返回：session_id为新创建的会话ID；created_at为创建时间；title为会话标题。

```
GET /api/v1/sessions
```

查询用户所有会话，支持分页和过滤。查询参数包括：user_id为用户ID；page为页码，从1开始；page_size为每页数量；status为会话状态过滤，可选值为active、archived、interrupted。

响应返回：sessions为会话列表，每项包含session_id、title、status、created_at、last_message_at、task_state；total为总会话数；page为当前页码；page_size为每页数量。

```
GET /api/v1/sessions/{session_id}/resume
```

恢复会话请求，包括：session_id为会话ID；resume_task为布尔值，是否恢复之前中断的任务。

响应返回：session_id为恢复的会话ID；task_state为之前中断的任务状态；context为恢复的上下文内容。

#### 2.2.3 意图识别API

意图识别API提供意图识别能力，支持单意图和多意图识别。

```
POST /api/v1/intent/recognize
```

请求参数包括：user_id为用户ID；session_id为会话ID，用于获取上下文；input为用户输入文本；images为可选的图片列表；context为可选的额外上下文信息。

响应返回：intents为识别的意图列表，每个意图包含intent_id、intent_type（single/multiple）、entities、confidence、is_implicit（是否为隐含意图）；conflict_info为冲突信息，当检测到与当前任务的冲突时返回。

```
POST /api/v1/intent/clarify
```

请求确认澄清API，当意图不明确时进行主动询问和确认。

请求参数包括：session_id为会话ID；clarify_questions为需要澄清的问题列表。

响应返回：clarify_prompt为澄清提示语；options为选项列表（如果有）。

#### 2.2.4 工具调用API

工具调用API提供外部工具的注册、查询和调用功能，支持工具的动态管理和灵活扩展。

```
POST /api/v1/tools/call
```

调用工具请求包括：tool_id为工具ID；params为工具参数，JSON对象格式；session_id为会话ID，用于关联调用记录；async为布尔值，默认为false，true表示异步调用。

同步响应返回：tool_id为调用的工具ID；result为工具返回结果；duration_ms为调用耗时；status为调用状态。

异步调用时，响应立即返回：task_id为任务ID，用于查询结果；status为pending。

```
GET /api/v1/tools/call/{task_id}
```

查询异步调用结果，响应包括：status为任务状态，可选值为pending、completed、failed；result为结果内容（completed时）；error为错误信息（failed时）；progress为进度百分比。

```
POST /api/v1/tools/register
```

工具注册API，用于MCP/SKILLs工具的动态注册。

请求参数包括：tool_id为工具ID；name为工具名称；description为工具描述；category为工具分类；param_schema为参数schema；api_endpoint为API端点；auth_config为认证配置；tool_type为工具类型，可选值为MCP、SKILLs、Native；sandbox_config为沙箱配置。

响应返回：tool_id为注册的工具ID；status为注册状态；security_review_status为安全审核状态。

### 2.3 WebSocket接口

除HTTP API外，系统还提供WebSocket连接方式，适用于需要实时双向通信的场景。WebSocket连接可以减少HTTP协议的开销，提升响应速度和用户体验。

```
WSS://domain/ws/chat
```

连接建立时需要提供认证令牌，格式为：wss://domain/ws/chat?token={jwt_token}&session_id={session_id}。

消息格式分为请求消息和响应消息两类。客户端发送的请求消息格式为：type为消息类型，可选值为chat、typing、heartbeat、interrupt；payload为消息内容；message_id为客户端消息ID。

服务端发送的响应消息格式为：type为消息类型，可选值为chunk、error、heartbeat、interrupt_ack、task_pause、task_resume；payload为消息内容；message_id为对应的客户端消息ID；model为产生此消息的模型来源；task_state为当前任务状态。

心跳机制方面，客户端需要每30秒发送一次心跳，服务端超过60秒未收到心跳则断开连接。心跳消息格式为：type为heartbeat；timestamp为客户端时间戳。

打断处理机制方面，客户端发送interrupt类型消息时，服务端立即停止当前输出，处理新输入，并返回interrupt_ack消息。如果有未完成的任务，服务端返回task_pause消息包含任务状态，客户端可以选择是否恢复任务。

## 3. 数据库设计

### 3.1 数据库选型

根据数据特点和访问模式，系统采用多数据库组合方案。关系型数据使用MySQL 8.0，存储用户信息、会话元数据、工具定义等结构化数据，MySQL具有良好的事务支持和成熟的生态。缓存和会话数据使用Redis Cluster，存储对话上下文、模型缓存、热点数据等，Redis提供高速的读写能力和丰富的数据结构。向量数据使用Milvus或Qdrant，存储对话嵌入向量，用于相似度检索和上下文召回。文件存储使用对象存储服务（如阿里云OSS或AWS S3），存储用户上传的图片、系统生成的媒体文件等。

### 3.2 表结构设计

#### 3.2.1 用户表

用户表存储用户的基本信息和认证数据，是系统的基础数据表之一。

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    email VARCHAR(100) UNIQUE COMMENT '邮箱',
    phone VARCHAR(20) UNIQUE COMMENT '手机号',
    avatar_url VARCHAR(500) COMMENT '头像URL',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '账号状态：1正常，2禁用',
    user_type TINYINT NOT NULL DEFAULT 1 COMMENT '用户类型：1普通用户，2VIP用户，3管理员',
    preferences JSON COMMENT '用户偏好设置',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at DATETIME COMMENT '最后登录时间',
    INDEX idx_username (username),
    INDEX idx_phone (phone),
    INDEX idx_email (email),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';
```

#### 3.2.2 会话表

会话表存储对话会话的元数据，每个用户可以拥有多个会话。

```sql
CREATE TABLE sessions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(36) NOT NULL UNIQUE COMMENT '会话UUID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    title VARCHAR(200) COMMENT '会话标题',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '会话状态：1进行中，2已完成，3已归档，4中断',
    model_config JSON COMMENT '模型配置',
    settings JSON COMMENT '用户设置',
    task_state JSON COMMENT '当前任务状态',
    context_snapshot TEXT COMMENT '上下文快照',
    message_count INT NOT NULL DEFAULT 0 COMMENT '消息数量',
    token_count INT NOT NULL DEFAULT 0 COMMENT 'token消耗',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_message_at DATETIME COMMENT '最后消息时间',
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_last_message_at (last_message_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话表';
```

#### 3.2.3 消息表

消息表存储会话中的每条消息，包括用户消息和AI回复。

```sql
CREATE TABLE messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    message_id VARCHAR(36) NOT NULL UNIQUE COMMENT '消息UUID',
    session_id BIGINT NOT NULL COMMENT '会话ID',
    role VARCHAR(20) NOT NULL COMMENT '角色：user、assistant、system',
    content_type VARCHAR(20) NOT NULL DEFAULT 'text' COMMENT '内容类型：text、image、mixed',
    content TEXT NOT NULL COMMENT '文本内容',
    media_urls JSON COMMENT '媒体URL列表',
    tool_calls JSON COMMENT '工具调用记录',
    model_source VARCHAR(50) COMMENT '来源模型：talker、thinker',
    intents JSON COMMENT '识别的意图列表',
    emotion VARCHAR(20) COMMENT '情感标签',
    tokens INT COMMENT '消耗token数',
    latency_ms INT COMMENT '响应延迟',
    feedback_score TINYINT COMMENT '用户评分：1-5',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_created_at (created_at),
    INDEX idx_role (role),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息表';
```

#### 3.2.4 意图表

意图表存储每次意图识别的结果，支持多意图场景。

```sql
CREATE TABLE intents (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    intent_id VARCHAR(36) NOT NULL UNIQUE COMMENT '意图UUID',
    session_id BIGINT NOT NULL COMMENT '会话ID',
    message_id VARCHAR(36) COMMENT '关联消息ID',
    intent_type VARCHAR(50) NOT NULL COMMENT '意图类型',
    intent_subtype VARCHAR(50) COMMENT '意图子类型',
    entities JSON COMMENT '实体列表',
    confidence FLOAT NOT NULL DEFAULT 0 COMMENT '置信度',
    is_implicit TINYINT DEFAULT 0 COMMENT '是否隐含意图',
    is_primary TINYINT DEFAULT 1 COMMENT '是否主意图',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '处理状态：pending、processing、completed、failed',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_intent_type (intent_type),
    INDEX idx_status (status),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='意图表';
```

#### 3.2.5 任务表

任务表存储复杂任务的执行状态，支持打断和恢复。

```sql
CREATE TABLE tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id VARCHAR(36) NOT NULL UNIQUE COMMENT '任务UUID',
    session_id BIGINT NOT NULL COMMENT '会话ID',
    task_type VARCHAR(50) NOT NULL COMMENT '任务类型',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态：pending、running、paused、completed、failed',
    progress INT DEFAULT 0 COMMENT '进度百分比',
    sub_tasks JSON COMMENT '子任务列表',
    current_step INT DEFAULT 0 COMMENT '当前步骤',
    context JSON COMMENT '任务上下文',
    result JSON COMMENT '任务结果',
    error_message TEXT COMMENT '错误信息',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME COMMENT '完成时间',
    INDEX idx_session_id (session_id),
    INDEX idx_status (status),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务表';
```

#### 3.2.6 工具表

工具表存储系统中可用的工具定义，支持插件化的工具管理。

```sql
CREATE TABLE tools (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tool_id VARCHAR(50) NOT NULL UNIQUE COMMENT '工具ID',
    name VARCHAR(100) NOT NULL COMMENT '工具名称',
    description TEXT NOT NULL COMMENT '工具描述',
    category VARCHAR(50) NOT NULL COMMENT '工具分类：weather、search、travel、custom',
    param_schema JSON NOT NULL COMMENT '参数schema',
    api_endpoint VARCHAR(500) NOT NULL COMMENT 'API端点',
    auth_config JSON COMMENT '认证配置',
    timeout_ms INT NOT NULL DEFAULT 5000 COMMENT '超时时间',
    retry_times TINYINT NOT NULL DEFAULT 2 COMMENT '重试次数',
    rate_limit JSON COMMENT '限流配置',
    enabled TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
    tool_type VARCHAR(20) NOT NULL DEFAULT 'native' COMMENT '工具类型：native、mcp、skill',
    sandbox_config JSON COMMENT '沙箱配置',
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0' COMMENT '版本号',
    security_status VARCHAR(20) DEFAULT 'approved' COMMENT '安全审核状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_enabled (enabled),
    INDEX idx_tool_type (tool_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工具表';
```

### 3.3 索引优化

数据库索引的设计需要平衡查询性能和写入开销。复合索引的创建遵循最左前缀原则，优先使用高频查询条件作为索引的前缀字段。对于范围查询（如时间范围）和模糊查询（如用户名模糊匹配），需要谨慎使用索引，必要时考虑使用全文索引。

会话表以user_id + last_message_at建立复合索引，支持按用户查询会话列表并按最后活跃时间排序的场景。消息表以session_id + created_at建立复合索引，支持按会话查询历史消息的场景。意图表以session_id + intent_type建立复合索引，支持按意图类型查询的场景。任务表以session_id + status建立复合索引，支持查询会话中特定状态任务的场景。

## 4. 模块接口设计

### 4.1 对话服务模块

对话服务模块是系统的核心模块，负责处理用户对话请求，协调各模型和工具的协作。该模块采用微服务架构，通过内部RPC或消息队列与其他模块通信。

#### 4.1.1 对话入口接口

对话入口是对外提供服务的统一入口，负责请求的校验、路由和响应封装。

```go
// 对话请求结构
type ChatRequest struct {
    SessionID   string   `json:"session_id"`
    UserID      string   `json:"user_id"`
    Input       string   `json:"input"`
    Modality    string   `json:"modality"`
    Images      []string `json:"images,omitempty"`
    Stream      bool     `json:"stream"`
    Interrupt   bool     `json:"interrupt"`
    Config      *ChatConfig `json:"config,omitempty"`
}

// 对话配置
type ChatConfig struct {
    TalkerModel   string  `json:"talker_model"`
    ThinkerModel  string  `json:"thinker_model"`
    Temperature   float64 `json:"temperature"`
    MaxTokens     int     `json:"max_tokens"`
    EnableThinker bool    `json:"enable_thinker"`
    EnableEmotion bool    `json:"enable_emotion"`
}

// 对话响应结构
type ChatResponse struct {
    Text        string       `json:"text"`
    Intents     []Intent    `json:"intents"`
    Tokens      int         `json:"tokens"`
    DurationMs  int         `json:"duration_ms"`
    Models      []string    `json:"models"`
    Segments    []Segment   `json:"segments,omitempty"`
    TaskState   *TaskState  `json:"task_state,omitempty"`
    Emotion     string      `json:"emotion"`
}

// 流式片段
type Segment struct {
    SegmentID    int     `json:"segment_id"`
    Text         string  `json:"text"`
    Model        string  `json:"model"`
    IsFinal      bool    `json:"is_final"`
    IntentID     string  `json:"intent_id,omitempty"`
}
```

对话入口的核心处理流程包括：第一步，验证请求参数，检查必填字段和格式；第二步，获取或创建会话上下文，加载历史消息和任务状态；第三步，调用意图识别服务，判断用户意图，包括单意图和多意图识别；第四步，根据意图类型选择处理路径，简单问答直接调用Talker，多意图分别处理后聚合，复杂任务触发任务调度；第五步，处理打断场景，如果Interrupt标志为true，暂停当前任务，处理新意图；第六步，组装响应并返回。

#### 4.1.2 上下文管理接口

上下文管理负责维护对话历史的存储和检索，支持多轮对话的上下文连续性。

```go
// 上下文管理接口
type ContextManager interface {
    // 获取会话上下文
    GetContext(sessionID string, maxMessages int) (*ConversationContext, error)
    
    // 保存消息到上下文
    AppendMessage(sessionID string, message *Message) error
    
    // 获取当前任务状态
    GetTaskState(sessionID string) (*TaskState, error)
    
    // 保存任务状态（支持打断恢复）
    SaveTaskState(sessionID string, state *TaskState) error
    
    // 清理过期上下文
    CleanupExpiredContexts() error
    
    // 压缩上下文
    CompressContext(sessionID string) error
}

// 会话上下文
type ConversationContext struct {
    SessionID     string
    UserID        string
    Messages      []Message
    Intents       []Intent
    TaskState     *TaskState
    SystemPrompt  string
    TokenCount    int
}

// 任务状态
type TaskState struct {
    TaskID       string      `json:"task_id"`
    TaskType     string      `json:"task_type"`
    Status       string      `json:"status"` // pending, running, paused, completed
    Progress     int         `json:"progress"`
    SubTasks     []SubTask   `json:"sub_tasks"`
    CurrentStep  int         `json:"current_step"`
    Context      map[string]interface{} `json:"context"`
    Result       string      `json:"result"`
}
```

### 4.2 意图识别模块

意图识别模块负责分析用户输入，判断用户的真实意图，为后续处理提供路由依据。

#### 4.2.1 意图识别接口

```go
// 意图识别请求
type IntentRequest struct {
    UserID   string   `json:"user_id"`
    SessionID string  `json:"session_id"`
    Input    string  `json:"input"`
    Images   []string `json:"images,omitempty"`
    Context  string   `json:"context"`
}

// 意图识别结果
type IntentResult struct {
    Intents      []Intent   `json:"intents"`
    Confidence   float64   `json:"confidence"`
    ConflictInfo *ConflictInfo `json:"conflict_info,omitempty"`
}

// 意图结构
type Intent struct {
    IntentID    string         `json:"intent_id"`
    Type        IntentType     `json:"type"`
    SubType     string         `json:"sub_type,omitempty"`
    Entities    []Entity       `json:"entities"`
    Confidence  float64        `json:"confidence"`
    IsImplicit  bool           `json:"is_implicit"`
    IsPrimary   bool           `json:"is_primary"`
}

// 冲突信息
type ConflictInfo struct {
    HasConflict    bool     `json:"has_conflict"`
    CurrentTaskID  string   `json:"current_task_id,omitempty"`
    ConflictType   string   `json:"conflict_type"` // pause, cancel, parallel
    Suggestion    string   `json:"suggestion"`
}

// 意图类型
type IntentType string

const (
    IntentQA          IntentType = "qa"          // 简单问答
    IntentToolCall    IntentType = "tool_call"   // 工具调用
    IntentMultiple    IntentType = "multiple"    // 多意图
    IntentComplexTask IntentType = "complex_task" // 复杂任务
    IntentChat        IntentType = "chat"        // 闲聊
    IntentEmotion     IntentType = "emotion"     // 情感表达
    IntentUnknown     IntentType = "unknown"     // 未知
)
```

意图识别的处理流程为：首先进行文本预处理，包括分词、实体抽取、关键词提取；然后结合上下文进行意图分类，使用模型判断用户意图类型（包括是否为多意图）；接着进行实体识别，从输入中提取关键信息；对于隐含意图，需要结合上下文推断用户潜在需求；最后根据意图类型和实体信息，确定后续处理路径，并检测是否与当前任务冲突。

#### 4.2.2 多意图处理接口

```go
// 多意图拆分请求
type MultiIntentRequest struct {
    SessionID string  `json:"session_id"`
    Input     string  `json:"input"`
    Context   string  `json:"context"`
}

// 多意图拆分结果
type MultiIntentResult struct {
    PrimaryIntent   *Intent  `json:"primary_intent"`
    SecondaryIntents []Intent `json:"secondary_intents"`
    AllIntents      []Intent `json:"all_intents"`
    ProcessingMode  string   `json:"processing_mode"` // sequential, parallel, priority
}

// 意图处理协调器
type IntentCoordinator interface {
    // 拆分多意图
    SplitIntents(req *MultiIntentRequest) (*MultiIntentResult, error)
    
    // 协调处理多个意图
    CoordinateProcessing(ctx context.Context, intents []Intent) ([]*ProcessingResult, error)
    
    // 聚合结果
    AggregateResults(results []*ProcessingResult) (*AggregatedResponse, error)
}
```

### 4.3 任务调度模块

任务调度模块负责管理复杂任务的执行，包括任务分解、调度执行、打断处理等。

#### 4.3.1 任务调度接口

```go
// 任务执行请求
type TaskExecuteRequest struct {
    SessionID string      `json:"session_id"`
    TaskType  string      `json:"task_type"`
    Input     string      `json:"input"`
    Entities  []Entity    `json:"entities"`
    Context   map[string]interface{} `json:"context"`
}

// 任务执行响应
type TaskExecuteResponse struct {
    TaskID     string                 `json:"task_id"`
    Status     string                 `json:"status"`
    Progress   int                    `json:"progress"`
    SubTasks   []SubTaskStatus        `json:"sub_tasks"`
    Result     map[string]interface{} `json:"result,omitempty"`
    Error      string                 `json:"error,omitempty"`
}

// 子任务状态
type SubTaskStatus struct {
    SubTaskID   string `json:"sub_task_id"`
    TaskType    string `json:"task_type"`
    Status      string `json:"status"` // pending, running, completed, failed
    Progress    int    `json:"progress"`
    Result      string `json:"result,omitempty"`
}

// 打断处理请求
type InterruptRequest struct {
    SessionID  string `json:"session_id"`
    NewInput   string `json:"new_input"`
    SaveState  bool   `json:"save_state"`
}

// 打断处理响应
type InterruptResponse struct {
    TaskState    *TaskState `json:"task_state"`
    CanResume    bool       `json:"can_resume"`
    ResumePrompt string     `json:"resume_prompt,omitempty"`
}
```

### 4.4 模型服务接口

#### 4.4.1 Talker模型接口

Talker模型负责快速生成初步回答，强调响应速度和对话流畅性。

```go
// Talker请求
type TalkerRequest struct {
    UserID       string    `json:"user_id"`
    SessionID    string    `json:"session_id"`
    History      []Message `json:"history"`
    Input        string    `json:"input"`
    SystemPrompt string    `json:"system_prompt"`
    Config       ModelConfig `json:"config"`
    EmotionContext string  `json:"emotion_context,omitempty"`
}

// Talker响应
type TalkerResponse struct {
    Text       string    `json:"text"`
    Tokens     int       `json:"tokens"`
    LatencyMs  int       `json:"latency_ms"`
    Segments   []string  `json:"segments"` // 流式片段
    Emotion    string    `json:"emotion"` // 识别的情感
}
```

Talker模型的设计重点是低延迟，采用了以下优化措施：模型量化，使用INT8或INT4量化，减少计算量和显存占用；KV缓存复用，对于相同前缀的请求，复用已计算的注意力缓存；投机解码，使用小模型预测多个token，大模型验证，加速生成过程；预热机制，服务启动时预加载模型，请求到来时立即处理。

Talker还需要具备情感理解能力，能够识别用户输入中的情绪倾向，并生成情感化的回复。

#### 4.4.2 Thinker模型接口

Thinker模型负责深度推理和复杂任务处理，强调回答质量和工具调用能力。

```go
// Thinker请求
type ThinkerRequest struct {
    UserID       string       `json:"user_id"`
    SessionID    string       `json:"session_id"`
    History      []Message    `json:"history"`
    Input        string       `json:"input"`
    Intents      []Intent     `json:"intents"`
    Tools        []ToolSchema `json:"tools"`
    Context      string       `json:"context"`
    Config       ModelConfig  `json:"config"`
}

// Thinker响应
type ThinkerResponse struct {
    Text          string          `json:"text"`
    Tokens        int             `json:"tokens"`
    LatencyMs     int             `json:"latency_ms"`
    ToolCalls     []PlannedToolCall `json:"tool_calls"`
    Supplement    string          `json:"supplement"` // 补充内容
    Refinements   []string        `json:"refinements"` // 修正内容
}

// 计划调用的工具
type PlannedToolCall struct {
    ToolID   string `json:"tool_id"`
    Params   map[string]interface{} `json:"params"`
    Sequence int    `json:"sequence"` // 执行顺序
    Async    bool   `json:"async"`   // 是否异步
}
```

Thinker模型的输入包含意图列表和工具列表，使模型能够理解用户的完整需求和可用的外部能力。模型输出包括最终回答、计划调用的工具列表和补充信息。

#### 4.4.3 响应融合接口

响应融合负责将Talker和Thinker的输出进行有机结合，形成最终响应。

```go
// 融合请求
type FusionRequest struct {
    SessionID      string          `json:"session_id"`
    TalkerOutput   *TalkerResponse `json:"talker_output"`
    ThinkerOutput  *ThinkerResponse `json:"thinker_output"`
    MultiIntentResults []*ProcessingResult `json:"multi_intent_results,omitempty"`
    Config         *FusionConfig   `json:"config"`
}

// 融合配置
type FusionConfig struct {
    Mode             string `json:"mode"` // append、insert、replace
    MaxSupplementLen int    `json:"max_supplement_len"`
    ConflictStrategy string `json:"conflict_strategy"` // ignore、correct、merge
    PreserveTalkerRhythm bool `json:"preserve_talker_rhythm"` // 保持Talker节奏
}

// 融合响应
type    Text     FusionResponse struct {
 string    `json:"text"`
    Segments []Segment `json:"segments"`
    Metadata Metadata  `json:"metadata"`
}
```

融合策略采用Talker为主、Thinker补充的原则。对于多意图场景，还需要整合多个意图的处理结果。融合模块需要处理以下情况：Talker生成的内容直接作为响应主体；Thinker生成的内容以补充形式追加；冲突修正使用温和方式过渡；多意图结果按优先级排序输出。

### 4.5 工具服务接口

#### 4.5.1 工具调度接口

工具调度负责管理和执行外部工具调用。

```go
// 工具调度请求
type ToolDispatchRequest struct {
    ToolID   string                 `json:"tool_id"`
    Params   map[string]interface{} `json:"params"`
    Context  map[string]interface{} `json:"context"`
}

// 工具调度响应
type ToolDispatchResponse struct {
    ToolID    string                 `json:"tool_id"`
    Result    map[string]interface{} `json:"result"`
    Error     string                 `json:"error,omitempty"`
    LatencyMs int                    `json:"latency_ms"`
}

// 批量工具调度
type BatchToolDispatchRequest struct {
    Calls []ToolDispatchRequest `json:"calls"`
    Mode  string                `json:"mode"` // sequential、parallel
}

type BatchToolDispatchResponse struct {
    Results []ToolDispatchResponse `json:"results"`
    TotalMs int                    `json:"total_ms"`
}
```

工具调度支持同步和异步两种模式。同步模式适用于快速响应的工具调用，如天气查询、简单搜索等，等待工具返回后继续处理。异步模式适用于耗时较长的操作，如批量数据获取、复杂计算等，立即返回任务ID，客户端通过轮询或回调获取结果。

#### 4.5.2 MCP/SKILLs管理接口

MCP/SKILLs管理接口支持工具的动态注册和执行。

```go
// 工具注册请求
type ToolRegisterRequest struct {
    ToolID        string                 `json:"tool_id"`
    Name          string                 `json:"name"`
    Description   string                 `json:"description"`
    Category      string                 `json:"category"`
    ParamSchema   map[string]interface{} `json:"param_schema"`
    APIEndpoint   string                 `json:"api_endpoint"`
    AuthConfig    map[string]interface{} `json:"auth_config"`
    ToolType      string                 `json:"tool_type"` // mcp、skill
    SandboxConfig map[string]interface{} `json:"sandbox_config"`
}

// 工具执行请求
type ToolExecuteRequest struct {
    ToolID   string                 `json:"tool_id"`
    Params   map[string]interface{} `json:"params"`
    Timeout  int                    `json:"timeout"`
    Sandbox  bool                  `json:"sandbox"`
}
```

## 5. 流程设计

### 5.1 简单问答流程

简单问答是最高频的使用场景，用户提出问题，系统直接回答，不需要调用外部工具。流程设计重点是快速响应和流畅体验。

第一步，用户输入问题并发送请求。客户端对输入进行预处理，包括敏感词过滤、长度限制等。请求包含session_id、user_id、input等必要信息。

第二步，服务端接收请求并进行验证。验证内容包括：用户身份合法性、会话是否存在规范。验证通过后，进入意图识别环节。

第三步，意图识别模块分析用户输入。对于简单问答场景，意图识别判断为IntentQA类型，不需要触发工具调用。

第四步，Talker模型生成回答。系统将对话历史和用户输入拼接为prompt，调用Talker模型进行推理。Talker生成回答后，立即开始流式输出。

第五步，响应返回客户端。服务端将生成的文本通过SSE或WebSocket推送给客户端。客户端逐段显示响应内容，营造流畅的交互体验。

整个流程的端到端延迟目标为TTFT小于1秒，总响应时间小于1.5秒。

### 5.2 工具调用流程

工具调用场景需要外部能力支持，如天气查询、信息搜索等。流程设计需要平衡响应速度和回答质量。

第一步，用户提出需要查询的问题，如"北京今天天气怎么样"。客户端发送请求，包含用户输入和会话上下文。

第二步，意图识别判断为工具调用类型。系统分析用户意图，识别出需要查询天气的实体（城市：北京）和工具类型（天气查询）。

第三步，Talker先行响应。在Thinker进行深度推理的同时，Talker生成初步响应，如"让我帮你查一下北京的天气"。这个响应立即返回给用户，让用户感知到请求已被处理。

第四步，Thinker执行工具调用。Thinker分析用户需求，生成工具调用参数，调用天气查询工具。工具返回实时天气数据。

第五步，Thinker生成详细回答。基于工具返回的数据，Thinker生成包含详细信息（如温度、湿度、空气质量等）的回答。

第六步，响应融合。融合模块将Talker的初步响应和Thinker的详细回答进行合并，形成完整的响应流式返回给用户。

整个流程的目标是1秒内开始响应，3秒内完成完整响应。

### 5.3 多意图处理流程

多意图场景需要识别并处理用户单次输入中的多个需求。

第一步，用户输入包含多个需求，例如"北京天气怎么样？顺便帮我查下上海的机票"。系统进行多意图识别，拆分出两个独立意图：意图A查询北京天气，意图B查询上海机票。

第二步，意图协调器判断处理模式。由于两个意图不冲突，可以并行处理。

第三步，并行执行各意图的处理。对于天气查询意图，走工具调用流程；对于机票查询意图，走工具调用流程。

第四步，结果聚合。将两个意图的处理结果整合为统一回答，按照合理的顺序和格式输出。

第五步，响应返回。整合后的响应通过流式方式返回给用户。

### 5.4 打断处理流程

打断场景需要优雅处理用户在对话过程中的新需求。

第一步，用户正在等待Thinker的深度回答，或者Talker正在流式输出。

第二步，用户发送新的输入，例如"先停一下，帮我查查天气"。系统检测到新的用户输入。

第三步，打断判断。系统分析新意图与当前任务的冲突关系。由于天气查询与当前任务（假设是机票查询）不冲突，系统决定并行处理。

第四步，处理新意图。对于天气查询意图，立即执行工具调用，返回天气信息。

第五步，继续原任务。原任务继续在后台执行，完成后与天气结果合并。

第六步，恢复提示。如果原任务被暂停，系统提示用户是否继续，例如"之前的机票查询还在进行中，是否继续？"

如果新意图与当前任务冲突（例如用户查询一个完全无关的话题），系统暂停当前任务，保存任务状态，处理新任务，完成后询问用户是否恢复原任务。

### 5.5 复杂任务流程

复杂任务场景涉及多步骤推理、多工具调用，如行程规划、多目的地查询等。

第一步，用户提出复杂需求，如"帮我规划一个北京到上海的三日游"。系统识别为复杂任务类型。

第二步，Thinker进行任务规划。分析用户需求，将大任务分解为多个子任务，如景点推荐、交通安排、酒店预订等。

第三步，任务调度执行。根据任务依赖关系，并行执行独立的子任务。如同时查询北京和上海两地的天气、同时获取两地的景点信息等。

第四步，结果汇总和整合。Thinker汇总各子任务的执行结果，进行综合分析和整合。

第五步，生成完整回答。基于汇总结果，Thinker生成包含详细安排的行程规划。

第六步，响应返回。融合后的响应以流式方式返回给用户，用户可以逐步看到完整的行程安排。

### 5.6 情感交互流程

情感交互场景需要识别用户情绪并给予恰当回应。

第一步，用户输入带有情绪色彩，例如"我太难了"或"今天真开心"。

第二步，情感分析模块识别用户情绪倾向。分类包括积极情绪、消极情绪、中性情绪等。

第三步，Talker生成情感化回复。根据识别的情绪，生成相应的情感回应。例如识别到消极情绪时，给予安慰和建议。

第四步，响应返回。情感化的回复通过流式方式返回给用户。

## 6. 错误处理设计

### 6.1 错误分类

系统错误分为以下几类：客户端错误（4xx）包括参数错误、认证失败、权限不足、资源不存在等；服务端错误（5xx）包括服务不可用、内部异常、超时等；业务错误包括配额超限、内容违规、会话过期、多意图冲突等。

每种错误都有对应的错误码和错误消息，便于客户端进行针对性处理。错误响应格式统一为：code为错误码；message为错误描述；details为详细信息（可选）；request_id为请求追踪ID。

### 6.2 降级策略

当核心功能不可用时，系统需要提供降级服务，保证基本可用性。

模型降级方面，当主要模型不可用时，自动切换到备用模型。Talker模型不可用时，使用较小的轻量模型替代；Thinker模型不可用时，仅使用Talker生成回答，跳过深度推理环节。

工具降级方面，当外部工具不可用时，返回预设的默认响应或缓存的历史数据。天气查询不可用时，返回"暂时无法获取天气信息，建议您稍后重试"；搜索不可用时，返回"搜索服务暂时不可用"。

服务降级方面，当非核心服务不可用时，关闭相关功能，保证核心对话功能正常。暂时关闭用户反馈、消息历史等功能。

### 6.3 重试机制

对于临时性故障，系统实现自动重试机制。重试策略包括：立即重试一次，用于处理网络瞬时抖动；延迟重试，用于处理临时过载，延迟时间指数增长；放弃重试，超过最大重试次数后放弃，返回错误信息。

重试时需要保证接口的幂等性，避免重复操作导致的数据不一致。对于写操作，使用唯一ID进行幂等校验；对于读操作，重试是安全的。

### 6.4 熔断保护

当某个服务的失败率超过阈值时，触发熔断，后续请求直接返回降级响应，避免压垮下游服务。

熔断器有三个状态：关闭状态正常调用；打开状态直接返回降级响应；半开状态尝试放行少量请求探测恢复。熔断器的配置参数包括：失败率阈值（默认50%）、熔断时长（默认30秒）、最小请求数（默认10）。

## 7. 安全设计

### 7.1 认证授权

用户认证采用JWT令牌方案。登录成功后，服务端生成包含用户ID和权限信息的JWT令牌，返回给客户端。客户端在后续请求中携带令牌，服务端验证令牌有效性后处理请求。

令牌分为访问令牌和刷新令牌两种。访问令牌有效期较短（默认1小时），用于API访问验证；刷新令牌有效期较长（默认7天），用于获取新的访问令牌。刷新机制确保用户无需频繁登录，同时控制令牌泄露的风险。

权限控制采用RBAC模型。系统定义角色（如普通用户、VIP用户、管理员），每个角色拥有不同的权限。API访问时验证用户角色是否具有相应权限。

### 7.2 MCP/SKILLs安全

MCP/SKILLs扩展模块需要额外的安全控制。

沙箱隔离方面，第三方工具在隔离环境中执行，限制文件、网络、进程等系统资源访问。执行超时限制每次工具调用的最大执行时间。资源限制限制工具调用可以使用的CPU、内存等资源。

调用审计方面，记录所有工具调用的详细信息，包括调用者、参数、结果、执行时长等。异常调用告警对于异常的调用行为进行实时告警。

权限审批方面，新工具接入需要经过安全审批流程。审批内容包括工具的合法性、API的安全性、数据处理的合规性等。

### 7.3 数据安全

数据传输使用TLS 1.3加密，确保数据在传输过程中不被窃取。API网关强制HTTPS，HTTP请求自动重定向到HTTPS。

数据存储采用AES-256加密，密钥使用KMS服务管理。敏感字段（如密码、手机号）在存储时加密，查询时解密。日志中不记录敏感信息。

数据访问遵循最小权限原则。数据库账号按服务分配，只授予必要的表权限。跨服务访问通过API网关统一管理，不允许直接访问数据库。

### 7.4 内容安全

用户输入和AI输出都需要进行内容安全检查。检查维度包括：敏感词过滤，检测并屏蔽违规内容；政治敏感检测，识别并处理敏感话题；暴力色情检测，识别并过滤不当内容；广告信息检测，识别并处理广告内容。

内容安全检查采用多层级策略：规则匹配用于快速检测已知违规内容；机器学习模型用于识别新型违规内容；人工审核用于处理AI判断不确定的内容。

## 8. 监控与运维

### 8.1 监控指标

系统监控覆盖以下维度：基础设施监控包括CPU、内存、磁盘、网络等资源使用情况；应用监控包括QPS、响应时间、错误率等业务指标；模型监控包括推理延迟、token消耗、缓存命中率、多意图识别准确率等AI特有指标；业务监控包括DAU、会话数、对话轮数、意图识别成功率、打断处理成功率等产品指标。

核心指标的告警阈值设置为：P99响应时间超过2秒告警；错误率超过1%告警；工具调用失败率超过5%告警；GPU利用率超过90%持续5分钟告警；多意图遗漏率超过10%告警。

### 8.2 日志设计

日志采用结构化JSON格式，便于解析和检索。日志内容包括：时间戳、日志级别、请求ID、用户ID、服务名称、操作名称、耗时、结果等。

日志级别使用规范为：ERROR用于记录错误和异常，影响系统正常运行；WARN用于记录警告，可能存在问题但不影响功能；INFO用于记录关键业务事件，如用户登录、对话开始、意图识别、多意图处理等；DEBUG用于记录调试信息，仅在开发环境启用。

对于MCP/SKILLs调用，需要记录详细的调用日志，包括工具名称、调用参数、执行结果、执行时长、异常信息等。

### 8.3 链路追踪

分布式追踪使用OpenTelemetry规范，实现全链路追踪。每个请求生成唯一的Trace ID，在服务间传递。追踪记录请求经过的每个服务节点、调用耗时、关键事件等信息。

追踪数据发送到Jaeger或Zipkin进行存储和展示。通过追踪系统，可以直观地查看请求的完整调用链路，定位性能瓶颈和故障点。

对于多意图场景，链路追踪需要记录每个意图的处理过程，包括意图拆分、并行处理、结果聚合等。对于打断场景，链路追踪需要记录打断发生时的任务状态，便于问题排查。

## 9. 总结

本文档详细描述了智能体应用的系统设计内容，包括API规范、数据库设计、模块接口、流程设计和安全实现等。系统设计遵循高可用、高性能、可扩展的原则，确保能够满足产品需求中定义的各项指标。

本次修订重点增强了以下方面的设计：多意图识别和处理机制，支持单次输入中的多个需求；打断处理机制，支持用户在对话过程中随时发起新需求；任务调度机制，支持复杂任务的分解、执行和恢复；MCP/SKILLs扩展机制，支持工具的动态注册和安全执行；情感交互机制，支持情感识别和情感化回复。

API设计采用RESTful风格，支持HTTP和WebSocket两种协议，提供统一的响应格式和错误处理。数据库采用多数据库组合方案，MySQL存储结构化数据，Redis提供高速缓存，Milvus存储向量数据。模块接口定义清晰，职责边界明确，便于独立开发和集成测试。

流程设计覆盖了简单问答、工具调用、多意图处理、打断场景、复杂任务、情感交互等典型场景，每个流程都明确了处理步骤和性能目标。错误处理和降级策略确保系统在异常情况下仍能提供服务。安全设计从认证授权、MCP安全、数据安全、内容安全等多个维度保障系统安全。

本系统设计文档与架构设计文档配合使用，为开发团队提供完整的实施指导。在后续的开发过程中，可以根据实际情况对设计进行调整和优化。
