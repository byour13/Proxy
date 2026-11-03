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
├── update.py               # 一键更新：生成 + 提交 + 推送 + 清缓存（日常就用它）
├── update.bat              # Windows 双击入口，等于运行 update.py
├── build.py                # 转换脚本（纯标准库，零依赖）
├── input/                  # 放节点 txt（可放多个，自动合并去重）
├── output/
│   ├── loon.txt            # base64 通用订阅
│   ├── clash.yaml          # Clash 配置（仅节点 + 自动测速组）
│   ├── nodes.loon.txt      # Loon 原生节点行（手动粘贴 / 排查用）
│   └── status.json         # 节点数、更新时间、协议分布
└── README.md
```

## 日常更新：一条命令

**把新的 txt 丢进 `input/`，然后运行 `update.py` 就行**，它会自动完成：生成 → 判断有没有变化 → 提交 → 推送 → 通知 jsDelivr 清缓存。

```bash
python update.py
```

Windows 上也可以直接双击 `update.bat`。

它做的检查：

| 情况 | 行为 |
|---|---|
| `input/` 里没有 txt | 直接报错退出，不动任何文件 |
| 节点内容与上次完全一致 | 跳过提交，不产生空提交（`--force` 可强制） |
| 生成失败（文件损坏等） | 中止，绝不推送半成品 |
| 推送缺凭证 | 提示先手动 `git push` 登录一次，之后就能自动推 |
| 推送成功 | 自动请求 `purge.jsdelivr.net` 清缓存，不必再手动加 `?v=` |

参数：

| 参数 | 说明 |
|---|---|
| `--latest` | 只用 `input/` 里最新的那个 txt，忽略更早的（避免旧节点越积越多） |
| `--gen-only` | 只生成订阅文件，不碰 git |
| `--no-push` | 生成并提交，但不推送 |
| `--force` | 节点没变化也照常提交推送 |
| `--prefix X` | 临时改节点名前缀（默认 `TG-`） |
| `--include R` / `--exclude R` | 按名称正则只保留 / 剔除节点 |

## 一、只生成（进阶）

不想推送、只想看看生成结果时，直接用 `build.py`：


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

## 二、手动推送（不用 update.py 时）

```bash
git add input output
git commit -m "chore: 更新节点"
git push
```

> 首次 `git push` 会弹 GitHub 登录窗口，登录一次之后系统会记住凭证，
> 之后 `update.py` 就能全自动推送了。

## 三、订阅地址

仓库地址：`https://github.com/byour13/Proxy`，分支 `main`。

| 客户端 | 地址 |
|---|---|
| Loon | `https://cdn.jsdelivr.net/gh/byour13/Proxy@main/output/loon.txt` |
| Clash Verge | `https://cdn.jsdelivr.net/gh/byour13/Proxy@main/output/clash.yaml` |

优先用 jsDelivr（国内可访问）。备选 `raw.githubusercontent.com/byour13/Proxy/main/output/loon.txt`，国内可能打不开。

**缓存问题**：jsDelivr 对 `@main` 有约 12 小时缓存。`update.py` 推送成功后会主动调用
`purge.jsdelivr.net` 清缓存，通常 1~2 分钟生效。如果没生效，再在地址后加版本参数
`?v=2`、`?v=3`（数字递增即可绕过缓存）。

## 四、Loon 配置

```ini
[Remote Proxy]
TG = https://cdn.jsdelivr.net/gh/byour13/Proxy@main/output/loon.txt,enabled=true

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
