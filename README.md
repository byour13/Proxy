# nodes-sub：一份节点 txt，双端订阅（Loon + Clash Verge）

把节点 txt 放进 `input/`，跑一个脚本，生成两种格式的订阅文件推到 GitHub，
Loon 和 Clash Verge 各自订阅一个链接，随时更新。

```
input/*.txt  →  build.py  →  output/loon.txt   （base64 通用订阅 → Loon）
                          →  output/clash.yaml （Clash YAML → Clash Verge）
```

## 仓库结构

```
.
├── build.py                # 转换脚本（纯标准库，零依赖）
├── input/                  # 放节点 txt（可放多个，自动合并去重）
├── output/
│   ├── loon.txt            # base64 通用订阅
│   ├── clash.yaml          # Clash 配置（仅节点 + 自动测速组）
│   ├── nodes.loon.txt      # Loon 原生节点行（手动粘贴 / 排查用）
│   └── status.json         # 节点数、更新时间、协议分布
└── README.md
```

## 一、生成

把 txt 丢进 `input/`，然后：

```bash
# 默认读 input/ 目录
python build.py

# 或者直接指定文件 / 目录（路径带空格要加引号）
python build.py --input "C:\Users\admin\Downloads\Telegram Desktop\11.txt"
python build.py --input ./input --prefix TG- --exclude "过期|官网"
```

输出示例：

```
[INFO] 11.txt: 5 个节点（重复 6，不支持 0，异常 0）
[OK] 共 5 个节点 → output/
[分布] {'anytls': 4, 'vmess': 1}
```

### 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--input / -i` | `./input` | 文件或目录，可重复传多次 |
| `--out / -o` | `output` | 输出目录 |
| `--prefix` | `TG-` | 节点名前缀，方便两端圈组 |
| `--group` | `TG节点` | Clash 策略组名 |
| `--interval` | 300 | 测速间隔（秒） |
| `--tolerance` | 50 | 延迟差多少才切换（毫秒） |
| `--include` | 空 | 只保留名称匹配该正则的节点 |
| `--exclude` | 空 | 剔除名称匹配该正则的节点 |

同一份文件里重复的节点（同 `服务器:端口:凭证`）会自动去掉，多个文件之间也会去重。

## 二、推送

```bash
git add input output
git commit -m "chore: 更新节点"
git push
```

> `input/` 里的 txt 要不要一起提交由你决定。提交的话仓库会有两份相同信息；
> 不提交就把 `input/` 加进 `.gitignore`，只保留 `output/`。

## 三、订阅地址

假设仓库是 `用户名/nodes-sub`，分支 `main`：

| 客户端 | 地址 |
|---|---|
| Loon | `https://cdn.jsdelivr.net/gh/用户名/nodes-sub@main/output/loon.txt` |
| Clash Verge | `https://cdn.jsdelivr.net/gh/用户名/nodes-sub@main/output/clash.yaml` |

优先用 jsDelivr（国内可访问）。备选 `raw.githubusercontent.com/用户名/nodes-sub/main/output/loon.txt`，国内可能打不开。

**缓存问题**：jsDelivr 对 `@main` 有约 12 小时缓存。更新后想立刻生效，在地址后加版本参数
`?v=2`、`?v=3`（数字递增即可绕过缓存），客户端里改一次订阅地址就行。

## 四、Loon 配置

```ini
[Remote Proxy]
TG = https://cdn.jsdelivr.net/gh/用户名/nodes-sub@main/output/loon.txt,enabled=true

[Proxy Group]
TG节点 = url-test, node-filter = ^TG-, url = http://www.gstatic.com/generate_204, interval = 300, tolerance = 50
Telegram = select, TG节点, DIRECT
```

`node-filter = ^TG-` 只圈出这批节点，不会把机场主力节点混进来。

## 五、Clash Verge 配置

配置页 → 新建 → 从 URL 导入 → 粘贴 `clash.yaml` 的地址 → 导入并启用。

生成的文件内容：

- `proxies`：全部节点
- `proxy-groups`：一个 `TG节点`（url-test 自动测速）
- `rules`：仅 `GEOIP,CN,DIRECT` + `MATCH,TG节点`

**注意**：这是一个完整配置文件，导入会替换当前配置。想保留原有机场配置的话，
可以用 Verge 的配置合并功能把 `proxies` 部分并进去，或者干脆手动复制节点。

如果订阅一直更新失败，在 Verge 设置里打开「更新订阅时使用系统代理」。

## 六、常见问题

| 现象 | 原因 / 处理 |
|---|---|
| Loon 订阅成功但看不到节点 | Loon 版本低于 3.3.9 Build 945，AnyTLS 不支持 |
| Clash Verge 报 `unsupported proxy type: anytls` | 内核太旧，需 mihomo 1.19+；Verge 设置里检查内核版本并升级 |
| 浏览器打开链接 404 | 仓库私有（raw 需 token）、分支不是 `main`、路径不对 |
| 链接内容还是旧的 | jsDelivr 缓存，加 `?v=2` 绕过 |
| 节点测速全超时 | 这类免费节点存活率低，属正常；可加大 `--interval` 或换批次 |
| 名字里有逗号导致行错乱 | 脚本已自动把 `,` 替换成空格 |

## 七、安全提醒

- 仓库必须**公开**，否则两个客户端都拉不到（订阅无法带 token 请求头）。
- 这些节点全是 `skip-cert-verify=true`，只适合一般浏览，别登录网银 / 主邮箱。
- 别把机场订阅链接、Telegram 凭证等敏感信息提交进仓库。

## 八、后续可加：自动从 Telegram 频道拉取

目前是「拿到 txt → 跑脚本 → 推送」的手动流程。想全自动，可以加一个
GitHub Actions：定时用 Telethon 读取频道、把最新 txt 落到 `input/`、再跑 `build.py`
并自动 commit。这部分需要 Telegram 的 `api_id/api_hash/session` 存到仓库 Secrets，
等你要加的时候再说。
