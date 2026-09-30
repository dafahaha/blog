# 给微软 TextWorld 修了个 bug：一行正则，和它背后的多命令解析

> 相关 PR：[microsoft/TextWorld#377](https://github.com/microsoft/TextWorld/pull/377)，已合并。
> 改动很小，两个文件，核心是一行正则。但定位它的过程比改它有意思得多，记一下。

## 起因

TextWorld 是微软做的一个文本游戏环境，常被拿来当强化学习 / 具身智能的 benchmark——agent 接收一段自然语言描述的房间状态，输出 "go north"、"take key" 这种命令，环境再返回新的状态。

我当时在翻它的 wrapper 代码，顺手在一个真实游戏里，把两条命令用句号拼在一行喂了进去：

```python
game_state, _, _ = env.step("go east. go west.")
```

然后环境直接炸了，抛了个 `ValueError`：

```
ValueError: invalid literal for int() with base 10: '...</moves>\n\n<score>...'
```

单条命令完全正常，两条拼一起就崩。这是个很典型的"边界输入"问题——正常路径大家都测，把多条命令塞一行这种用法，没人覆盖到。

## 先搞清楚 Inform7 到底吐了什么

TextWorld 底层用的是 Inform 7 这个交互式小说引擎。为了让程序能解析游戏状态，引擎在正常的文本反馈之外，会额外打印一批带标签的结构化信息，大概长这样：

```
This is room. You can see a chest here.

<extras>
<score>
0
</score>
<moves>
1
</moves>
</extras>
```

TextWorld 要做的，就是把 `<score>`、`<moves>` 这些标签里的内容抠出来，转成整数存到 `game_state` 上。

关键点在这：**当你一行喂了两条命令，Inform7 会老老实实地把这组标签打印两遍**，每个命令对应一份：

```
<score>
0
</score>
<moves>
1
</moves>
... 中间是普通文本反馈 ...
<score>
0
</score>
<moves>
2
</moves>
```

而我们最终想要的，显然是**最后一条命令**执行完的状态（moves 应该等于 2）。

## 根因：贪婪匹配把两个块缝成了一个

解析标签的代码在 `textworld/envs/wrappers/tw_inform7.py` 的 `_detect_extra_infos` 里，原来长这样：

```python
regex = re.compile(r"<{tag}>\n(.*)</{tag}>".format(tag=tag), re.DOTALL)
match = re.search(regex, text)
if match:
    _, cleaned_text = _detect_i7_events_debug_tags(match.group(1))
    matches[tag] = cleaned_text.strip()
    text = re.sub(regex, "", text)
```

问题就出在这个正则上。两个地方叠加：

1. `(.*)` 是**贪婪**匹配，它会尽可能多地吃字符；
2. `re.DOTALL` 让 `.` 连换行符也能匹配。

于是当文本里有两个 `<score>` 块时，`<score>\n(.*)</score>` 的匹配方式是：从**第一个** `<score>` 开始，`(.*)` 一路吃到**最后一个** `</score>` 才肯停。中间本该是"块结束 → 普通文本 → 块开始"的那一段，包括 `</score>`、`<moves>...</moves>` 这些，全被当成 score 的内容吞了进去。

后面 `_gather_infos` 拿到这一大坨东西，照着老逻辑 `int(...)` 一转，里面混着 `<moves>` 标签和换行，自然就 `ValueError` 了。报错信息里那串 `...</moves>...<score>...`，其实就是贪婪匹配的"犯罪现场"。

这也是正则解析结构化文本的一个经典坑：**只要你假设"这个标签只出现一次"，贪婪写法在出现第二次时就会悄悄出错**，而且不会报错，只会给你一段意料之外的内容。

## 修复：非贪婪 + 取最后一块

改动其实就三处。

第一，把贪婪的 `.*` 改成非贪婪的 `.*?`，这样每个标签块会被独立、完整地匹配，不会再跨块：

第二，原来是 `re.search` 只拿到第一个匹配，现在用 `findall` 拿到所有块，然后**显式取最后一个** `all_matches[-1]`——对应多命令场景下最后一条命令的状态，这正是我们要报告给 agent 的结果：

```python
regex = re.compile(r"<{tag}>\n(.*?)</{tag}>".format(tag=tag), re.DOTALL)
all_matches = regex.findall(text)
if all_matches:
    _, cleaned_text = _detect_i7_events_debug_tags(all_matches[-1])
    matches[tag] = cleaned_text.strip()
    text = regex.sub("", text)
```

顺带把 `re.sub(regex, "", text)` 换成了 `regex.sub("", text)`，复用同一个编译好的正则，没什么特别的，就是少传一遍参数。

第三处是在不远处的 `_gather_infos`，原来有个裸 `except:`：

```python
try:
    self.state[info] = int(self.state[info].strip())
except:
    self.state[info] = int(self.state[info].strip().split("\n")[0])
```

裸 `except` 会把 `KeyboardInterrupt`、`SystemExit` 这种也一并吞掉，是 PEP 8 明确不推荐的。这里真正想兜的只是"内容不是合法整数"，所以收窄成 `except ValueError`。

## 测试：别只证明它不崩了

光改解析逻辑不够，得有个测试把这个行为钉死，否则以后谁重构一下可能又回去了。我在 `test_tw_inform7.py` 里加了一个：

```python
def test_multiple_commands(self):
    # 一行多命令不能崩，而且报告的应该是最后一条命令的状态
    for env in [self.env_z8]:
        env.reset()
        game_state, _, _ = env.step("go east. go west.")
        assert game_state.moves == 2
```

这里我特意没只断言"不抛异常"，而是断言 `moves == 2`。区别在于：如果哪天真的退回成"只取第一个块"，代码照样不崩，但 moves 会变成 1，这个测试依然能抓住它。**测"取的是最后一块"比测"没崩"更接近这个 bug 的本质。**

## Review 过程：维护者真正在意什么

这个 PR 来回了几轮，几个点让我印象挺深。

Marc-Alexandre Côté（TextWorld 的作者）没有直接说"你这正则写错了"，而是先让我**把 Inform7 实际输出的原始 observation 贴出来**。确认了"每个命令打印一组标签、要取最后一组"这个事实之后，他才认可非贪婪 + 取最后一块的方向。换句话说，他先要证据，再看方案。

中间他还提了两个要求：一个是前面说的裸 `except` 要按 PEP 8 收窄；另一个是测试文件的位置——我一开始把测试放在了顶层的 `tests/` 目录，但 TextWorld 的约定是 wrapper 的测试跟着 wrapper 走，应该放在 `textworld/envs/wrappers/tests/` 下面。我挪过去之后，还顺手解决了一个旧的 CI 失败：顶层有个同名测试模块，跟新位置的冲突了。

等所有 check 变绿、CLA 签完，他就合并了。

## 几点收尾的体会

- **报错信息要读全。** 一开始那个 `int()` 报错，最有价值的不是 `ValueError` 本身，而是它里面那串 `...</moves>...<score>...`——它直接告诉你，本应干净的数字里混进了别的标签，顺着这个去想"为什么两个块会缝在一起"，比盯着 `int()` 看快得多。
- **处理"可能重复出现"的结构，默认就该警惕贪婪匹配。** `.*?` + `findall` 是更安全的直觉。
- **测试要钉住正确的语义（取最后一块），而不是钉住现象（没崩）。**
- **给成熟项目提 PR，代码只是一部分。** 维护者会看你有没有先把事实搞清楚、有没有遵守项目的约定（目录结构、代码风格、CLA）。这些做到位，改动再小也会被认真对待。

这个 bug 不复杂，但它是那种"真实用户在真实用法下会踩到"的问题——能把这种小而确定的东西修干净，我觉得比硬凑一个大而无当的 feature 实在。
