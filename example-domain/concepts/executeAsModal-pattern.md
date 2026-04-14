---
title: "executeAsModal 模式"
type: concept
domain: adobe-uxp
source: "https://developer.adobe.com/photoshop/uxp/2022/ps_reference/media/executeasmodal/"
summary: "Photoshop UXP 插件中所有修改文档状态的操作必须包裹在 executeAsModal 中执行，这是防止并发操作破坏文档状态的核心机制。理解其设计原因和正确用法是 UXP 开发的基础。"
related: ["[[batchPlay]]", "[[uxp-plugin-lifecycle]]"]
created: 2026-04-14
updated: 2026-04-14
confidence: high
---

# executeAsModal 模式

## 为什么需要 executeAsModal？

### 历史背景

Photoshop 是一个单线程应用，其内部状态（文档、图层、历史记录等）在任意时刻只能被一个操作安全地修改。在 ExtendScript 时代，脚本是同步执行的，天然不存在并发问题。

但 UXP 插件运行在独立的 JavaScript 引擎中，支持异步操作（async/await、Promise）。这意味着：

- 多个插件可能同时尝试修改同一文档
- 单个插件内部的异步操作可能在 PS 状态不一致时继续执行
- 用户操作（如手动编辑）可能与插件操作交错发生

`executeAsModal` 的本质是**向 Photoshop 申请一个排他性的操作锁**。在回调函数执行期间：

1. PS 的 UI 进入"模态"状态（用户无法手动操作）
2. 其他插件的 PS API 调用会被排队等待
3. 当前插件独占对文档状态的修改权

### 设计哲学

```
用户操作 ──┐
           ├──► Photoshop 状态机 ◄── 只允许一个操作者
插件 A ────┘
插件 B ────► 等待队列
```

这与数据库的事务锁机制类似：`executeAsModal` 相当于 `BEGIN TRANSACTION`，回调结束相当于 `COMMIT`。

---

## 基本用法

### 正确用法 ✅

```javascript
const { app } = require("photoshop");

async function createNewLayer() {
  // 必须用 await 等待 executeAsModal 完成
  await app.activeDocument.executeAsModal(async (executionContext) => {
    // 所有 PS 操作都在这个回调内执行
    const layer = await app.activeDocument.createLayer({
      name: "新图层",
      kind: "pixel"
    });
    console.log("图层创建成功:", layer.name);
  }, {
    commandName: "创建新图层"  // 显示在 PS 进度条和历史记录中
  });
}
```

### 错误用法 ❌

```javascript
const { app } = require("photoshop");

// 错误：在 executeAsModal 外直接调用 PS API
async function wrongWay() {
  // ❌ 这会抛出错误："This method can only be called inside executeAsModal"
  const layer = await app.activeDocument.createLayer({ name: "图层" });
}

// 错误：忘记 await
async function forgotAwait() {
  // ❌ 不等待完成就继续执行，可能导致状态不一致
  app.activeDocument.executeAsModal(async () => {
    await someOperation();
  }, { commandName: "操作" });
  
  // 这里 executeAsModal 可能还没完成
  console.log("这里执行时机不确定");
}
```

---

## commandName 参数

`commandName` 是 `executeAsModal` 第二个参数对象中的必填字段（强烈建议填写）。

### 作用

1. **历史记录面板**：操作完成后，PS 历史记录中显示的名称
2. **进度条标题**：长时间操作时，PS 进度条显示的文字
3. **调试辅助**：出错时日志中可以看到是哪个命令失败

```javascript
await app.activeDocument.executeAsModal(async (executionContext) => {
  // ... 操作
}, {
  commandName: "批量调整图层透明度"  // 用户友好的中文名称
});
```

### 历史记录合并

如果你的操作逻辑上是一个整体，应该用同一个 `commandName`，这样 PS 历史记录中只会出现一条记录，用户可以一次性撤销整个操作。

---

## progressCallback 进度回调

对于耗时操作，可以通过 `executionContext` 报告进度：

```javascript
await app.activeDocument.executeAsModal(async (executionContext) => {
  const layers = app.activeDocument.layers;
  const total = layers.length;
  
  for (let i = 0; i < total; i++) {
    const layer = layers[i];
    
    // 报告进度（0.0 到 1.0）
    executionContext.reportProgress({
      value: i / total,
      commandName: `处理图层 ${i + 1}/${total}: ${layer.name}`
    });
    
    // 检查用户是否取消了操作
    if (executionContext.isCancelled) {
      console.log("用户取消了操作");
      break;
    }
    
    // 执行实际操作
    await processLayer(layer);
  }
}, {
  commandName: "批量处理所有图层"
});
```

### isCancelled 检查

长时间操作中应定期检查 `executionContext.isCancelled`，让用户可以中断操作：

```javascript
await app.activeDocument.executeAsModal(async (executionContext) => {
  for (const item of largeList) {
    if (executionContext.isCancelled) {
      // 清理已做的操作（可选）
      break;
    }
    await processItem(item);
  }
}, { commandName: "大批量操作" });
```

---

## 错误处理模式

### 基本 try/catch

```javascript
async function safeOperation() {
  try {
    await app.activeDocument.executeAsModal(async (executionContext) => {
      // 操作可能抛出错误
      await riskyOperation();
    }, {
      commandName: "风险操作"
    });
  } catch (error) {
    // executeAsModal 内部的错误会冒泡到这里
    if (error.number === 9) {
      // 错误码 9：用户取消了操作
      console.log("用户取消");
    } else {
      console.error("操作失败:", error.message);
      // 向用户显示错误
      await app.showAlert(`操作失败: ${error.message}`);
    }
  }
}
```

### modalBehavior 选项

当已经在一个 `executeAsModal` 上下文中时，可以控制嵌套行为：

```javascript
// 场景：某个工具函数不知道自己是否在 modal 上下文中被调用
async function utilityFunction() {
  await app.activeDocument.executeAsModal(async (executionContext) => {
    await doWork();
  }, {
    commandName: "工具操作",
    // "fail"（默认）：如果已在 modal 中，抛出错误
    // "wait"：等待当前 modal 结束后再执行
    // "execute"：直接在当前 modal 上下文中执行（不创建新的 modal）
    modalBehavior: "execute"
  });
}
```

| modalBehavior | 行为 | 适用场景 |
|---|---|---|
| `"fail"` | 已在 modal 中时抛出错误（默认） | 明确知道调用层级时 |
| `"wait"` | 等待当前 modal 结束 | 独立的并发操作 |
| `"execute"` | 复用当前 modal 上下文 | 工具函数/可复用代码 |

---

## 常见陷阱

### 陷阱 1：在 executeAsModal 外调用 PS API

```javascript
// ❌ 错误：直接在按钮点击事件中调用 PS API
document.getElementById("btn").addEventListener("click", async () => {
  // 这会报错！
  const doc = app.activeDocument;
  await doc.createLayer({ name: "test" }); // Error!
});

// ✅ 正确：包裹在 executeAsModal 中
document.getElementById("btn").addEventListener("click", async () => {
  await app.activeDocument.executeAsModal(async () => {
    const doc = app.activeDocument;
    await doc.createLayer({ name: "test" }); // OK
  }, { commandName: "创建图层" });
});
```

### 陷阱 2：嵌套 executeAsModal 导致死锁

```javascript
// ❌ 错误：嵌套 executeAsModal（默认 modalBehavior: "fail"）
await app.activeDocument.executeAsModal(async () => {
  // 这里再次调用 executeAsModal 会抛出错误
  await app.activeDocument.executeAsModal(async () => {
    await doWork();
  }, { commandName: "内层操作" }); // Error: Already in modal!
}, { commandName: "外层操作" });

// ✅ 正确：使用 modalBehavior: "execute"
async function reusableHelper() {
  await app.activeDocument.executeAsModal(async () => {
    await doWork();
  }, {
    commandName: "辅助操作",
    modalBehavior: "execute"  // 如果已在 modal 中，直接执行
  });
}

await app.activeDocument.executeAsModal(async () => {
  await reusableHelper(); // 现在可以安全调用
}, { commandName: "主操作" });
```

### 陷阱 3：异步操作逃逸

```javascript
// ❌ 错误：在 executeAsModal 回调中启动了不等待的异步操作
await app.activeDocument.executeAsModal(async () => {
  // 这个 Promise 没有被 await，会在 modal 结束后继续执行
  fetch("https://api.example.com/data").then(async (res) => {
    const data = await res.json();
    // ❌ 此时 modal 已经结束，这里调用 PS API 会报错！
    await app.activeDocument.createLayer({ name: data.name });
  });
}, { commandName: "操作" });

// ✅ 正确：等待所有异步操作
await app.activeDocument.executeAsModal(async () => {
  const res = await fetch("https://api.example.com/data");
  const data = await res.json();
  await app.activeDocument.createLayer({ name: data.name }); // OK
}, { commandName: "操作" });
```

### 陷阱 4：忘记处理"无活动文档"情况

```javascript
// ❌ 错误：没有检查是否有打开的文档
async function myOperation() {
  await app.activeDocument.executeAsModal(async () => {
    // 如果没有打开文档，app.activeDocument 为 null，这里会崩溃
  }, { commandName: "操作" });
}

// ✅ 正确：先检查
async function myOperation() {
  if (!app.activeDocument) {
    await app.showAlert("请先打开一个文档");
    return;
  }
  await app.activeDocument.executeAsModal(async () => {
    // 安全
  }, { commandName: "操作" });
}
```

---

## 与 batchPlay 的关系

`executeAsModal` 是**操作锁**，`batchPlay` 是**低级操作 API**。两者经常配合使用：

```javascript
const { app } = require("photoshop");
const { batchPlay } = require("photoshop").action;

await app.activeDocument.executeAsModal(async () => {
  // batchPlay 必须在 executeAsModal 内调用
  await batchPlay(
    [
      {
        _obj: "make",
        _target: [{ _ref: "layer" }],
        layerID: 1,
        name: "新图层"
      }
    ],
    { synchronousExecution: false }
  );
}, { commandName: "通过 batchPlay 创建图层" });
```

**选择原则**：
- 优先使用高级 API（`Document`、`Layer` 等），代码更清晰
- 高级 API 不支持的操作（如某些滤镜、调整图层）才用 `batchPlay`
- 两者都必须在 `executeAsModal` 内使用

---

## 完整示例：带进度和错误处理的批量操作

```javascript
const { app } = require("photoshop");

async function batchRenameLayersWithPrefix(prefix) {
  if (!app.activeDocument) {
    await app.showAlert("请先打开一个文档");
    return;
  }

  const layers = app.activeDocument.layers;
  
  try {
    await app.activeDocument.executeAsModal(async (executionContext) => {
      const total = layers.length;
      
      for (let i = 0; i < total; i++) {
        // 检查取消
        if (executionContext.isCancelled) {
          console.log(`操作在第 ${i} 个图层时被取消`);
          return;
        }
        
        // 报告进度
        executionContext.reportProgress({
          value: i / total,
          commandName: `重命名图层 ${i + 1}/${total}`
        });
        
        // 执行操作
        const layer = layers[i];
        layer.name = `${prefix}_${layer.name}`;
      }
    }, {
      commandName: `批量添加前缀 "${prefix}"`
    });
    
    console.log("批量重命名完成");
  } catch (error) {
    if (error.number === 9) {
      console.log("用户取消了操作");
    } else {
      console.error("重命名失败:", error);
      await app.showAlert(`操作失败: ${error.message}`);
    }
  }
}

// 调用
batchRenameLayersWithPrefix("2024");
```

---

## 参考资料

- [Adobe 官方文档 - executeAsModal](https://developer.adobe.com/photoshop/uxp/2022/ps_reference/media/executeasmodal/)
- [Adobe 官方文档 - ExecutionContext](https://developer.adobe.com/photoshop/uxp/2022/ps_reference/media/executeasmodal/#executioncontext)
- 相关概念：[[batchPlay]]、[[uxp-plugin-lifecycle]]
