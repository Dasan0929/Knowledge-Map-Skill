# v0.3 状态、文件与执行协议

## 唯一内容来源

map.json 顶层恰好 topic / map_status / nodes。每个节点恰好 id / content / core_question / prerequisites / status。禁止 children、坐标、标题等额外节点字段。content 首行作为卡片短标题，其余作为范围说明；只写一段也可渲染。

map_status：pending_confirm / locked。status：todo / learning / mastered / skipped。id 为稳定非空标识，默认 node_1 等；增删或换序不重编号。prerequisites 是本图内 ID 列表，含义“当前节点需要这些前置”，不允许自引、重复、悬空或循环。数组顺序须满足前置。顶层 5–8 节点；子层 2–5。Generic Schema 允许 2–8，具体上下限由 context.kind 和验证工具联动检查。

context.json 包含版本、稳定 map_id、revision、kind、target、closure_goal、scope、assumptions、learner、memory_sources、parent、children。详见相邻 schema。topic 为简短主题名，target 为学习请求的具体范围，scope 分 included / excluded。新增语义版本 revision 加一；仅锁定不加一，子图索引更新不改变内容版本。不要把状态数据塞进自定义聊天标签。

同一个 content 的任务未变化时保留 ID；若全新任务替换旧任务，分配新 ID。新生成节点 todo，已有状态仅按有依据的操作保留。REFINE 可重置实质变化的任务为 todo，但不得自己设为 mastered。

## 运行（Python 3，标准库，无安装依赖）

以下相对脚本路径均相对于 skill 根目录，map 参数则用真实输出路径：

```sh
python3 scripts/validate_map.py /path/to/topic/map.json
python3 scripts/build_canvas.py /path/to/topic/map.json
```

自动从 map.json 同目录读取 context.json，并先构建已登记的有效子地图，输出 `learning-map.canvas` 和 `learning-map.html`。重新构建会读取已有 Canvas 的稳定卡片位置；当前 rank 的纵向层次重新计算，允许改变依赖的卡片移动。

首次生成可附加 `--mode INIT` 校验所有节点均 todo、地图待确认。修改时先保存旧 map 和 context 到 history，再使用：

```sh
python3 scripts/validate_map.py /path/to/topic/map.json --mode REFINE --previous /path/to/topic/history/r1-map.json --previous-context /path/to/topic/history/r1-context.json
```

锁定时先保存当前 map，用以下命令验证锁定没有顺手改内容：

```sh
python3 scripts/validate_map.py /path/to/topic/map.json --mode LOCK --previous /path/to/topic/history/before-lock-map.json
python3 scripts/build_canvas.py /path/to/topic/map.json
```

工具验证状态变化，无法证明用户是否真的确认：必须依据原始用户指令判断。先合法校验再构建；失败返回非零状态，不以输出文件存在冒充新版本成功。

## 视图规范

Canvas 节点 ID 由 map_id 与知识节点 ID 确定性映射为 16 位十六进制；边 ID 同样稳定。知识 ID 不受展示重排影响。画布增加一个非学习性的主题／目标说明卡，不计入知识节点数量。

连线从前置指向后续，与 prerequisites 存储方向不同。画布中的箭头只表示学习依赖。HTML 与 Canvas 使用同一份构建数据，卡片高度按文本估算并留余量，详细文字可点选查看。脚本检查实际卡片边界不重叠；文字是否可读仍需查看渲染。

HTML 内嵌数据，不依赖 fetch、CDN 或网络服务；可直接打开本地文件。点选后展示完整内容和前置，支持缩放与平移。子图存在且有效时卡片显示进入入口。JSON 中的任何内容作为文本展示，不执行 HTML。拖动视口不修改 JSON 或 Canvas。

Canvas 可在 Obsidian 手工编辑，但 v0.3 无内容双向同步。下次重建会依照 map.json 重写文案和关系，仅尽量保留横向布局。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

测试覆盖非法状态、依赖图、流转、子图父关系、稳定 ID、布局、输出一致性和安全文本嵌入；不以这些测试声称学生已形成闭环。缺乏可用浏览器工具时注明未完成实际视觉检查。
