# Graph Report - D:/home  (2026-05-13)

## Corpus Check
- Corpus is ~7,991 words - fits in a single context window. You may not need a graph.

## Summary
- 71 nodes · 102 edges · 15 communities detected
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Scheduler Base|Scheduler Base]]
- [[_COMMUNITY_News Spider|News Spider]]
- [[_COMMUNITY_Configuration|Configuration]]
- [[_COMMUNITY_Settings|Settings]]
- [[_COMMUNITY_Database|Database]]
- [[_COMMUNITY_Singleton Pattern|Singleton Pattern]]
- [[_COMMUNITY_Main Entry|Main Entry]]
- [[_COMMUNITY_Graphify Script|Graphify Script]]
- [[_COMMUNITY_API Init|API Init]]
- [[_COMMUNITY_Bin Module|Bin Module]]
- [[_COMMUNITY_Bin Main|Bin Main]]
- [[_COMMUNITY_Bin Init|Bin Init]]
- [[_COMMUNITY_Config Init|Config Init]]
- [[_COMMUNITY_Scheduler Init|Scheduler Init]]
- [[_COMMUNITY_Systems Init|Systems Init]]

## God Nodes (most connected - your core abstractions)
1. `NewsSpider` - 14 edges
2. `Conf` - 10 edges
3. `IntervalTask` - 7 edges
4. `CronTask` - 7 edges
5. `DateTask` - 7 edges
6. `ScheduleTask` - 6 edges
7. `tasks_load_from_inputs()` - 5 edges
8. `schedule_tasks_load()` - 4 edges
9. `FantomConfigParser` - 4 edges
10. `ScriptSingle` - 4 edges

## Surprising Connections (you probably didn't know these)
- `NewsSpider` --uses--> `ScriptSingle`  [INFERRED]
  D:\home\apps\api\bin\news_spider.py → D:\home\apps\api\systems\single.py
- `IntervalTask` --uses--> `Conf`  [INFERRED]
  D:\home\apps\api\scheduler\scheduler.py → D:\home\apps\api\systems\conf.py
- `CronTask` --uses--> `Conf`  [INFERRED]
  D:\home\apps\api\scheduler\scheduler.py → D:\home\apps\api\systems\conf.py
- `DateTask` --uses--> `Conf`  [INFERRED]
  D:\home\apps\api\scheduler\scheduler.py → D:\home\apps\api\systems\conf.py
- `schedule_tasks_load()` --calls--> `home()`  [INFERRED]
  D:\home\apps\api\scheduler\scheduler.py → D:\home\apps\api\systems\sys.py

## Communities

### Community 0 - "Scheduler Base"
Cohesion: 0.23
Nodes (7): ScheduleTask, CronTask, DateTask, IntervalTask, schedule_tasks_load(), tasks_load_from_inputs(), ScheduleTask

### Community 1 - "News Spider"
Cohesion: 0.33
Nodes (1): NewsSpider

### Community 2 - "Configuration"
Cohesion: 0.25
Nodes (3): Conf, FantomConfigParser, object

### Community 3 - "Settings"
Cohesion: 0.29
Nodes (5): BaseSettings, Config, load_config(), Settings, home()

### Community 4 - "Database"
Cohesion: 0.29
Nodes (6): get_db(), get_sort_end(), query_sort_end(), 查询数据库中最新的新闻的realSort作为sortEnd, 查询数据库中最新的新闻的realSort作为sortEnd, 连接到MongoDB数据库并返回数据库对象

### Community 5 - "Singleton Pattern"
Cohesion: 0.29
Nodes (3): ClassSingle, ScriptSingle, type

### Community 6 - "Main Entry"
Cohesion: 1.0
Nodes (0): 

### Community 7 - "Graphify Script"
Cohesion: 1.0
Nodes (0): 

### Community 8 - "API Init"
Cohesion: 1.0
Nodes (0): 

### Community 9 - "Bin Module"
Cohesion: 1.0
Nodes (0): 

### Community 10 - "Bin Main"
Cohesion: 1.0
Nodes (0): 

### Community 11 - "Bin Init"
Cohesion: 1.0
Nodes (0): 

### Community 12 - "Config Init"
Cohesion: 1.0
Nodes (0): 

### Community 13 - "Scheduler Init"
Cohesion: 1.0
Nodes (0): 

### Community 14 - "Systems Init"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **3 isolated node(s):** `连接到MongoDB数据库并返回数据库对象`, `查询数据库中最新的新闻的realSort作为sortEnd`, `查询数据库中最新的新闻的realSort作为sortEnd`
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Main Entry`** (2 nodes): `main.py`, `home()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Graphify Script`** (1 nodes): `run_graphify.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `API Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Bin Module`** (1 nodes): `an.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Bin Main`** (1 nodes): `main.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Bin Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Config Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Scheduler Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Systems Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `NewsSpider` connect `News Spider` to `Configuration`, `Settings`, `Singleton Pattern`?**
  _High betweenness centrality (0.370) - this node is a cross-community bridge._
- **Why does `Conf` connect `Configuration` to `Scheduler Base`?**
  _High betweenness centrality (0.253) - this node is a cross-community bridge._
- **Why does `ScriptSingle` connect `Singleton Pattern` to `News Spider`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `Conf` (e.g. with `IntervalTask` and `CronTask`) actually correct?**
  _`Conf` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `IntervalTask` (e.g. with `ScheduleTask` and `Conf`) actually correct?**
  _`IntervalTask` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `CronTask` (e.g. with `ScheduleTask` and `Conf`) actually correct?**
  _`CronTask` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `DateTask` (e.g. with `ScheduleTask` and `Conf`) actually correct?**
  _`DateTask` has 2 INFERRED edges - model-reasoned connections that need verification._