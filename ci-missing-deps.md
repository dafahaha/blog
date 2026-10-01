# 本地能跑、CI 却挂了：一个没写进 requirements 的 numpy，和它的 import 链

> 相关提交：[dafahaha/transit-truth · 6ebaa22](https://github.com/dafahaha/transit-truth/commit/6ebaa22)，`fix(ci): declare numpy/scipy deps missing from clean install`。
> 改动也就两行依赖，但它暴露的问题特别典型：你本机跑得欢，不代表干净环境跑得动。记一下。

## 起因：CI #30 红了

我在做 transit-truth——一个 AI API 中转站验真器，跑一些统计探针去判断你买的"gpt-4o"到底是不是真的。CI 配的是 Python 3.10 / 3.11 / 3.12 三矩阵，步骤很朴素：

```bash
cd backend
pip install -r requirements.txt
pip install pytest
python -c "from app.main import app"
```

本来只是想在合并前确认一下"在干净机器上能 import 起来"。结果 CI #30 直接红了，日志末尾是这么一段：

```
File "<string>", line 1, in <module>
  File "app\main.py", line 14, in <module>
    from .api.audit import router as audit_router
  File "app\api\audit.py", line 4, in <module>
    from ..core.auditor import AuditEngine
  File "app\core\auditor.py", line 16, in <module>
    from .fingerprint import ModelFingerprinter
  File "app\core\fingerprint.py", line 37, in <module>
    from .statistical_analyzer import StatisticalAnalyzer
  File "app\core\statistical_analyzer.py", line 24, in <module>
    import numpy as np
ModuleNotFoundError: No module named 'numpy'
```

## 离谱的地方：我本地明明能跑

最别扭的是，这个 `python -c "from app.main import app"` 我在本地跑过一百遍，从来没失败过。

我本地用的是 anaconda 的 Python，环境里 numpy、scipy、pandas、matplotlib 全都躺着——毕竟平时写数据分析脚本就在这个环境里。所以我写 `import numpy as np` 的时候，它当然能 import 成功，我从头到尾没觉得这是个"外部依赖"，只把它当成"环境里本来就有的东西"。

而 CI 呢？它拿的是 GitHub Actions 上一个干干净净的 Python 镜像，只做了 `pip install -r requirements.txt`。我翻出那份 requirements 一看：

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
httpx>=0.25.0
pydantic>=2.5.0
tiktoken>=0.5.0
```

好家伙，numpy 和 scipy 一个字都没提。

根因一句话就能说清：**依赖只在我本机恰好存在，却从没被写进声明。** anaconda 帮我"隐式"提供了它们，CI 机器没人替我提供，于是当场炸。

## 在干净环境里复现一次

读 CI 日志不如自己复现一遍。我新建了一个空 venv，只装 requirements 里那几个包，然后试着 import：

```powershell
python -m venv ttclean
.\ttclean\Scripts\pip install fastapi "uvicorn[standard]" httpx tiktoken pydantic
cd backend
..\ttclean\Scripts\python -c "from app.main import app"
```

报错和 CI 一模一样：`ModuleNotFoundError: No module named 'numpy'`。这就把问题从"CI 又抽风了"坐实成了"我漏声明了"。

接着我做了件挺有收获的事——只补 numpy，不补 scipy：

```
File "app\core\statistical_analyzer.py", line 25, in <module>
    from scipy import stats
ModuleNotFoundError: No module named 'scipy'
```

原来缺的是两个。它们就挨在 `statistical_analyzer.py` 的第 24、25 行：

```python
import numpy as np
from scipy import stats
```

这个文件是做统计检验的核心——拿探针返回的分布去和"理论上应该长这样"的参考分布比，用的就是 scipy 的 Mann-Whitney U 那一套。代码里确实用得到，不是手滑 import 的，所以补声明是对的。

## 为什么 import 阶段就炸，而不是跑到一半

一开始我有点奇怪：我又没真的跑审计，只是 `import app.main`，怎么就把 numpy 拖下水了？

顺着 traceback 看 import 链就明白了：

```
app.main
  → app.api.audit        (挂路由时就要 import 这个模块)
    → app.core.auditor
      → app.core.fingerprint
        → app.core.statistical_analyzer   ← 这里顶层 import numpy
```

`import numpy` 是写在模块顶层的，不是包在某个函数里。Python 的规则是**import 一个模块时，它顶层的所有 import 都必须立刻满足**。所以只要有人 import 了 `statistical_analyzer`（哪怕根本不调用里面的函数），numpy 就必须在场。这条链上每个模块都在顶层互相 import，于是"起个服务"和"用 numpy"被绑死在了一起。

这也解释了为什么我本地没感觉：anaconda 环境里 numpy 一直在，import 链顺顺当当；干净环境里链一拉到底，第一块缺的砖就露出来了。

## 修：requirements 和 pyproject 都要写

修法很直接，把两个包补进依赖声明。但这里有个小坑：这个仓库有**两处**依赖声明，CI 用的是 `requirements.txt`，打包用的是 `pyproject.toml`，得对齐：

```
numpy>=1.24.0
scipy>=1.11.0
```

补完再回到那个干净 venv：先装 numpy、再装 scipy，最后 `python -c "from app.main import app"`——这次它安静地起完了整个 app，没再吐 traceback。

顺带一提，修这个 CI 的前一个 commit 是 `c9586e7`，message 是 `fix: remove BOM from pyproject.toml breaking tomllib parse in CI`。说起来是同一类病：我在 Windows 上保存 pyproject 时带了 BOM，本地的 pip 宽容地忽略了，Linux CI 上的 `tomllib` 却严格到读不了这个文件。一个是"本机恰好装了"，一个是"本机恰好宽容"——都是把"我这台机器的状态"误当成了"代码本身的状态"。

## 几点体会

- **判断依赖该写什么，要以干净环境为准，不是以你的机器为准。** anaconda 是个大杂货铺，它里面有的包不等于你的项目需要它。
- **import 时炸的依赖，比运行时炸的更隐蔽。** 你不触发那条代码路径就永远发现不了；好在 CI 的第一步 `python -c "import app"` 正好把这种问题提前炸了出来，这一步我觉得加得值。
- **requirements.txt 和 pyproject.toml 是两份真相，必须手动对齐。** CI 读一份、打包读另一份，漏一处就是另一个环境再炸一次。
- **看到 traceback 别只看最后一行。** 那个 import 链从 `main.py` 一路串到 `statistical_analyzer.py`，它本身就告诉你"问题不在 main，在链尾那个统计模块"，顺着翻过去就是。
- **别假设 CI 机器和你一样。** 操作系统、Python 版本、有没有预装科学计算栈、文件编码宽容度——每一个差异都可能在你本地看不出、在 CI 上现形。

这种 bug 没有技术含量，但它太常见了：本地绿、CI 红，一半以上都是"我以为它本来就有"。修干净它，比硬凑一个花里胡哨的新功能更让我安心。
