# 视频标注网页工具包

这个文件夹能把一批生成视频做成盲标网页，界面和本仓库首页的标注台相同。几个人分别标完后，用 `compare_votes.py` 比对结果。

English summary: `build_site.py` turns a set of generated videos into a blind labeling page (same UI as this repository's root page), `serve.py` runs it locally and saves votes to `votes.json`, and `compare_votes.py` compares the exported labels of several raters.

## 需要什么
- **Python 3.8 以上**：只用标准库。
- **ffmpeg 和 ffprobe**：建议装上。没有的话，视频会原样复制，网页可能加载得很慢。
- **GitHub 账号**：只有要在线多人标注时才需要。

## 1. 拿到工具

```bash
git clone --depth 1 https://github.com/Sosekie/geot2v-video-labeling.git
cd geot2v-video-labeling/kit
```

## 2. 建网页（两种方式选一种）

**A. 视频按 GeoT2V 交接包的目录生成。** 视频在 `$CVG_WORK/outputs/video_refresh_v1/` 下面时，直接读任务表：

```bash
python build_site.py --cvg-work "$CVG_WORK" --task-csv "$CVG_PACKAGE/tasks/task_subset.csv" \
  --out ../../my_site --site-id batch01 \
  --sample-by model_id,family --per-stratum 4 \
  --send-to-zh "<收结果的人>" --send-to-en "<who collects results>"
```

- 任务表里还没生成的视频会自动跳过。
- `--sample-by model_id,family --per-stratum 4`：按"模型 × 运镜类型"分组，每组抽 4 段。不加这两个参数，就把全部视频放进去（最多 999 段）。
- 一次放 60–120 段比较合适，标一段大约要 10–15 秒。

**B. 其他视频。** 先写一个 CSV：
- 必填两列：`video`（mp4 路径）、`prompt`（提示词）；
- 可选列：`model_id`、`prompt_id`、`seed`、`family`。

```bash
python build_site.py --list videos.csv --out ../../my_site --site-id batch01
```

建好以后，`my_site/` 里有这些文件：

| 文件 | 用途 |
|---|---|
| `index.html` | 网页本身 |
| `videos/v001.mp4` … | 打乱、匿名、转码后的视频 |
| `manifest_public.json` | 评分人能看到的信息：编号、提示词、运镜类型 |
| `manifest_hidden.json` | 每个编号对应哪个模型、提示词和种子。**只留在自己电脑上，不要公开** |
| `serve.py` | 本机标注用，每次保存都写进 `votes.json` |

## 3. 先在本机看一遍

```bash
cd ../../my_site
python serve.py
```

打开 http://127.0.0.1:8765 。在本机标注时，结果直接存进 `my_site/votes.json`。

## 4. 发布到 GitHub Pages，多人在线标注
1. 在 GitHub 新建一个**公开**仓库，例如 `video-voting-batch01`，不要勾选自动生成 README。
2. 在 `my_site/` 里执行：

   ```bash
   git init
   git add .
   git commit -m "Labeling page"
   git branch -M main
   git remote add origin https://github.com/<你的账号>/video-voting-batch01.git
   git push -u origin main
   ```

3. 打开仓库的 Settings → Pages：Source 选 "Deploy from a branch"，分支选 `main`，目录选 `/ (root)`，保存。
4. 一两分钟后，网址就是 `https://<你的账号>.github.io/video-voting-batch01/`。

`.gitignore` 已经排除了 `manifest_hidden.json` 和 `votes.json`，它们不会被上传。推送后可以在 GitHub 网页上再确认一遍。

## 5. 标注和收结果
- 每人打开网址，在顶部填上名字，按数字键 1–5 作答。
- 每段要完整播完一遍才会保存。视频是噪声、花屏或黑屏时，第 1 题按 5（"画面坏了"），其余两题会自动填好。
- 标完点顶部的"复制全部结果（JSON）"，把内容存成 `名字.json`，发给收结果的人。

## 6. 比对结果

```bash
python compare_votes.py a.json b.json --hidden ../../my_site/manifest_hidden.json --out merged.csv
```

输出：
- 每题两人答案相同的比例，以及 kappa（扣除碰巧相同之后的一致程度，0.6 以上算较好）；
- 镜头题有分歧的片段编号；
- 每个模型各有多少段被判成"几乎不动"或"画面坏了"；
- `merged.csv`：每段一行，汇总所有人的答案。

## 题目（不要改）

| 题目 | 选项 |
|---|---|
| 第 1 题 镜头 | 几乎不动 / 原地转或变焦 / 真的在移动 / 说不准 / 画面坏了 |
| 第 2 题 画面里的东西（不算镜头运动） | 没有东西自己在动 / 有东西自己在动，而且合理 / 有不合理的变化 / 说不准 |
| 第 3 题 能当一个静态三维场景的拍摄吗 | 能 / 大体能 / 不能 / 说不准 |

题目一改，结果就没法和以前的标注对比了。

## 注意
- 公开仓库谁都能看到视频和提示词。不想公开的话，就只用第 3 步在本机标。
- GitHub 单个文件不能超过 100 MB。转码后每段通常只有 0.1–2 MB，整个仓库最好不超过 1 GB。
- 浏览器按 `--site-id` 分开保存标注。每批视频用不同的 site-id，避免互相覆盖。
