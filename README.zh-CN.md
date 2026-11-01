# csv-to-ics

[English](README.md)

把课程大纲变成日历事件，可导入 Google 日历、Apple 日历或 Outlook。

工作流程：

1. 把课程大纲和[提示词](prompts/syllabus_to_csv.md)一起交给 LLM（ChatGPT、Claude 等），让它生成一份 CSV，列出所有讲座、小测、考试和截止日期。
2. 对 CSV 运行 `csv_to_ics.py`，每个 CSV 生成一个 `.ics` 文件。
3. 把 `.ics` 文件导入日历应用。

## 环境要求

Python 3.10 及以上。

## 安装

```sh
git clone https://github.com/XingjianWang001/csv-to-ics.git
cd csv-to-ics
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 用法

```sh
# 转换单个文件，结果写到 ./output/demo1001.ics
python csv_to_ics.py examples/demo1001.csv

# 转换目录下（含子目录）所有 .csv，输出到另一个目录
python csv_to_ics.py input -o output

# 指定定时事件使用的时区
python csv_to_ics.py input --tz America/New_York

# 转换无错误后，把 CSV 移到 input/processed/
python csv_to_ics.py input --move-processed
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `input` | （必填） | 一个 `.csv` 文件，或包含 `.csv` 的目录。会跳过 `processed/` 子目录。 |
| `-o`, `--output` | `./output` | `.ics` 输出目录，保留输入目录的子目录结构。 |
| `--tz` | `America/Chicago` | 带时间的行所用的 [IANA 时区](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)。 |
| `--move-processed` | 关闭 | CSV 转换无错误后，移到输入目录下的 `processed/`。 |

每个日历以 CSV 文件名命名（例如 `demo1001`），支持的日历应用导入时会显示这个名字。

## CSV 格式

第一行必须是下面的表头。只有 `Subject` 和 `Start Date` 是必填的，其他列可以留空或省略。

```csv
Subject,Start Date,Start Time,End Date,End Time,Description,Alarm,Categories
```

| 列 | 格式 | 说明 |
| --- | --- | --- |
| Subject | 文本 | 事件标题，如 `CSCI4611 Homework 1 Due` |
| Start Date | `YYYY-MM-DD` | |
| Start Time | `HH:MM`（24 小时制） | 留空表示全天 |
| End Date | `YYYY-MM-DD` | 默认等于 Start Date |
| End Time | `HH:MM`（24 小时制） | |
| Description | 文本 | |
| Alarm | 分钟数 | 提前多少分钟提醒，如 `1440` 即提前一天 |
| Categories | 逗号分隔 | 如 `Quiz, Online` |

每一行如何变成日历事件：

| Start Time | End Time | 结果 | 典型用途 |
| --- | --- | --- | --- |
| 有 | 有 | 从开始到结束的事件 | 讲座、考试 |
| 有 | 空 | 时间点事件 | "作业 23:59 截止" |
| 空 | 空 | 全天事件，从 Start Date 到 End Date | 没有具体时间的截止日、假期 |

全天事件的提醒从当天 0 点往前倒推计算。

示例见 [examples/demo1001.csv](examples/demo1001.csv) 及其生成的 [`.ics`](examples/demo1001.ics)。

### 错误处理

某一行有问题（日期格式错误、结束早于开始、重复等）时，会打印文件名、行号和原因，跳过这一行，其余行照常转换。只要有任何一行出错，退出码就是 1；使用 `--move-processed` 时，这个 CSV 也不会被移走，方便修正后重新运行。

### 重新导入

每个事件的 UID 由 Subject、Start Date 和 Start Time 计算得出，每次转换都相同。很多日历应用在导入相同 UID 的事件时会更新原事件，而不是重复添加。但各应用的行为不一样，比如 Google 日历可能会忽略已经存在的事件。如果修改了事件的标题或开始时间，它会得到新的 UID，作为新事件出现。

## 开发

```sh
pip install -r requirements-dev.txt
pytest
```

## 许可证

[MIT](LICENSE)
