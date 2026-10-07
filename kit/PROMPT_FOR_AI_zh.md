# 给 AI 助手的提示词

复制下面整段给你的 AI 助手（Codex、Claude 等）。把尖括号里的内容换成你自己的。

```text
请用 GeoT2V 视频标注工具包，把我生成的视频做成一个在线标注网页。

工具包：git clone --depth 1 https://github.com/Sosekie/geot2v-video-labeling.git ，用里面的 kit/。先完整读一遍 kit/README_zh.md。

我的视频：<二选一：
  A. 按 GeoT2V 交接包生成的：工作目录 $CVG_WORK=<路径>，任务表 <路径>/tasks/task_subset.csv；
  B. 一个视频文件夹 <路径>，提示词在 <文件>。>

要求：
1. 用 kit/build_site.py 建站，不要改 kit/template.html 里的题目和选项。
   - site-id 用 <batch01>；
   - --send-to-zh "<收结果的人>"，--send-to-en "<who collects results>"；
   - 按 model_id,family 分层抽样，每层 <4> 段，总数控制在 60–120 段。
2. 建好后运行 python serve.py，在本机打开 http://127.0.0.1:8765 检查：视频能播放，能答题，播完一遍后能保存。
3. 在我的 GitHub 账号下新建公开仓库 <video-voting-batch01>，只推送建好的网站文件夹。
   - 推送前后都确认 manifest_hidden.json 和 votes.json 不在仓库里；
   - 开启 GitHub Pages（main 分支，根目录），把网址告诉我。
4. manifest_hidden.json 留在本机，告诉我它的路径；以后比对结果要用它。
5. 不要删除或改动原始视频，不要改生成代码，不要重新生成任何视频。
```
