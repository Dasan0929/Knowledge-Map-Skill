# 学习者背景、递归与移交

## Memory 输入

只读取用户提供、当前对话已知或宿主实际接入的来源，不自动搜索个人文件充当记忆。选择与本次学习有关的最小信息。没有记忆也可运行；memory_sources 与 prior_knowledge 用空列表，缺失信息只在影响路径时澄清。

context.learner 中，prior_knowledge 为 `{content, basis}`，basis 仅为 self_report / observed / assumed：用户自述、已有回答或测验记录支持、暂定假设。observed 不等于自动证明掌握；若需追溯，在 content 中简述实际依据。偏好放 preferences，不转成能力结论。本 skill 不写回学生画像，不提供基于几个问题的正式能力评级。

预览只显示目标和学习内容，不把完整学习者记忆渲染到画布。context 中仅保留有关摘要和实际来源引用，不复制原始个人记录。

## 父子地图

目录约定：

```text
主题/
  map.json
  context.json
  learning-map.canvas
  learning-map.html
  history/                         # 修改时保留旧有效版本
  submaps/
    node_2/
      map.json
      context.json
      learning-map.canvas
      learning-map.html
```

root 的 context.parent 为 null。子图 kind 为 subtopic，parent 为 `{map_path, node_id, node_fingerprint}`。路径相对于子图 context 所在目录；新建子图时父图必须 locked；之后父图进入协商但该节点语义未变时，可保留既有子图索引，不能据此继续新的展开。target 必须等于父节点 content，closure_goal 必须等于父节点 core_question，防止递归漂移。

node_fingerprint 是父节点 id / content / core_question / prerequisites 的规范 JSON SHA-256，工具 `node_fingerprint()` 可计算。学习状态变化不使子主题内容失效；内容、问题或依赖改变则会检测到旧子图。不要通过改指纹掩盖不匹配，应重新审核子图。

父图 children 列表中的每项是 `{node_id, map_path}`，指向子图的 map.json，路径相对于父 context。它只是文件索引，不是嵌套知识节点。子图生成后登记，再重建父预览；递归目录可以继续采用相同结构。不得指向自己或祖先形成文件关系循环。

移除父节点时也移除其登记项，旧子图文件可留在历史位置但不再作为当前入口。语义改变的父节点需要重审相关子图；构建工具拒绝将其当作有效当前入口。不要覆盖或删除历史教学材料。

## 锁定与交接

交接以 map.json + context.json 为依据。下游读取 locked 版本，结合先修和学习记录选择节点；skipped 不代表 mastered，是否能跳过依赖仍须依据背景或明确的教学安排。`core_question` 是讲解与考核设计的依据，不是已经执行的测验结果。

后续模块可维护 learning / mastered 等学习状态；更新文件后重建视图。只有单独的学科讲解模块负责教学与测验。没有实际调用能力时只提供可读路径，不伪造 agent 调用成功。

学习者状态与知识结构相互分离。单纯更新学习状态不会改变路线语义；路线内容变化需重新协商。地图锁定可幂等处理，不因学生开始学习就解锁。

## 旧版本迁移

v0.2 节点 title 改为 content 时必须补充范围说明，不能仅机械换键后宣称闭环已成立。保留同义任务 ID，迁移后重新进入 pending_confirm；新增 context，并生成可视化文件。旧地图和已提供的确认不自动批准新内容。
